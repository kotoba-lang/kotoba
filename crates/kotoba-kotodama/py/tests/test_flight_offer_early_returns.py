"""Tests for early-return guard paths in ingest/flight_offer.py.

Tasks that delegate to _do_* helpers return error dicts before calling
sync_cursor when required route parameters are missing. These tests hit
only those pre-DB guard clauses.

For tasks that catch all exceptions and return error dicts (fetch,
check_drop), we also verify the exception-handler path via the stub.
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# Stub kotodama.db_sync — the sync_cursor will be called by tasks that
# actually reach DB; the early-return guards we test never call it.
_db_stub = types.ModuleType("kotodama.db_sync")
def _noop_cursor():
    class _C:
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def execute(self, *a, **kw): pass
        def fetchone(self): return None
        def fetchall(self): return []
        description = None
        rowcount = 0
    return _C()
_db_stub.sync_cursor = _noop_cursor  # type: ignore[attr-defined]
sys.modules.setdefault("kotodama.db_sync", _db_stub)
sys.modules.setdefault("kotodama", types.ModuleType("kotodama"))

_MOD_NAME = "_flight_offer_early"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "ingest" / "flight_offer.py"
    _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

FO = sys.modules[_MOD_NAME]


# ─── task_flight_offer_add_watch — missing required route args ────────────────

def test_add_watch_no_args_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_add_watch())
    assert result["status"] == "error"


def test_add_watch_no_args_error_mentions_required_fields() -> None:
    result = asyncio.run(FO.task_flight_offer_add_watch())
    assert "originIata" in result["error"] or "required" in result["error"]


def test_add_watch_no_origin_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_add_watch(
        destinationIata="NRT", outboundDate="2026-06-01"
    ))
    assert result["status"] == "error"


def test_add_watch_no_destination_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_add_watch(
        originIata="LAX", outboundDate="2026-06-01"
    ))
    assert result["status"] == "error"


def test_add_watch_no_outbound_date_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_add_watch(
        originIata="LAX", destinationIata="NRT"
    ))
    assert result["status"] == "error"


def test_add_watch_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_add_watch())
    assert isinstance(result, dict)


# ─── task_flight_offer_get_cheapest — missing route args ─────────────────────

def test_get_cheapest_no_origin_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_get_cheapest(
        destinationIata="NRT", outboundDate="2026-06-01"
    ))
    assert result["status"] == "error"
    assert result.get("found") is False


def test_get_cheapest_no_outbound_date_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_get_cheapest(
        originIata="LAX", destinationIata="NRT"
    ))
    assert result["status"] == "error"


def test_get_cheapest_no_args_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_get_cheapest())
    assert result["status"] == "error"


def test_get_cheapest_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_get_cheapest())
    assert isinstance(result, dict)


# ─── task_flight_offer_remove_watch — missing route args ─────────────────────

def test_remove_watch_no_args_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_remove_watch())
    assert result["status"] == "error"
    assert result.get("removed") is False


def test_remove_watch_no_origin_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_remove_watch(
        destinationIata="NRT", outboundDate="2026-06-01"
    ))
    assert result["status"] == "error"


def test_remove_watch_no_destination_returns_error() -> None:
    result = asyncio.run(FO.task_flight_offer_remove_watch(
        originIata="LAX", outboundDate="2026-06-01"
    ))
    assert result["status"] == "error"


def test_remove_watch_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_remove_watch())
    assert isinstance(result, dict)


# ─── task_flight_offer_fetch — exception-catch path (no creds = stub) ────────

def test_fetch_no_args_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_fetch())
    assert isinstance(result, dict)
    assert "status" in result


def test_fetch_no_args_has_offers_fetched() -> None:
    result = asyncio.run(FO.task_flight_offer_fetch())
    # stub mode or error — both have status key
    assert result.get("status") in ("ok", "error", "stub")


# ─── task_flight_offer_check_drop — exception-catch path ─────────────────────

def test_check_drop_no_args_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_check_drop())
    assert isinstance(result, dict)
    assert "status" in result
