"""Guard and pure-path tests for primitives/hanrei.py."""

from __future__ import annotations

import asyncio
import importlib.util
import sys
import types
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

# ── db_sync stub ─────────────────────────────────────────────────────────────
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

if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg

# ── load hanrei ───────────────────────────────────────────────────────────────
_MOD_NAME = "_hanrei_guards"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "hanrei.py"
    real_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
        sys.modules[_MOD_NAME] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        if real_db is not None:
            sys.modules["kotodama.db_sync"] = real_db

H = sys.modules[_MOD_NAME]


# ─── task_hanrei_collect_case_detail — pure guard ─────────────────────────────

def test_collect_case_detail_no_url_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_case_detail(detailUrl=""))
    assert "error" in result


def test_collect_case_detail_no_url_error_mentions_detailurl() -> None:
    result = asyncio.run(H.task_hanrei_collect_case_detail(detailUrl=""))
    assert "detailUrl" in result["error"]


def test_collect_case_detail_no_url_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_case_detail(detailUrl=""))
    assert isinstance(result, dict)


# ─── task_hanrei_collect_cases — pure guard for unknown court ─────────────────

def test_collect_cases_unknown_court_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases(court="nonexistent_court_xyz"))
    assert "error" in result


def test_collect_cases_unknown_court_zero_jobs() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases(court="nonexistent_court_xyz"))
    assert result["jobs"] == 0


def test_collect_cases_unknown_court_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases(court="nonexistent_court_xyz"))
    assert isinstance(result, dict)


# ─── task_hanrei_seed_cases — dryRun path is pure ────────────────────────────

def test_seed_cases_dry_run_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_seed_cases(dryRun=True))
    assert isinstance(result, dict)


def test_seed_cases_dry_run_flag_set() -> None:
    result = asyncio.run(H.task_hanrei_seed_cases(dryRun=True))
    assert result["dryRun"] is True


def test_seed_cases_dry_run_no_errors() -> None:
    result = asyncio.run(H.task_hanrei_seed_cases(dryRun=True))
    assert result["errors"] == 0


def test_seed_cases_dry_run_has_cases() -> None:
    result = asyncio.run(H.task_hanrei_seed_cases(dryRun=True))
    assert "cases" in result


def test_seed_cases_dry_run_seeded_positive() -> None:
    result = asyncio.run(H.task_hanrei_seed_cases(dryRun=True))
    assert result["seeded"] > 0


# ─── task_hanrei_register_court_profiles — noop cursor, exception-caught ──────

def test_register_court_profiles_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_register_court_profiles())
    assert isinstance(result, dict)


def test_register_court_profiles_has_registered_key() -> None:
    result = asyncio.run(H.task_hanrei_register_court_profiles())
    assert "registered" in result


def test_register_court_profiles_has_errors_key() -> None:
    result = asyncio.run(H.task_hanrei_register_court_profiles())
    assert "errors" in result


def test_register_court_profiles_has_profiles_list() -> None:
    result = asyncio.run(H.task_hanrei_register_court_profiles())
    assert isinstance(result["profiles"], list)


# ─── task_hanrei_register_jurisdictions — noop cursor, exception-caught ───────

def test_register_jurisdictions_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_register_jurisdictions())
    assert isinstance(result, dict)


def test_register_jurisdictions_has_registered_key() -> None:
    result = asyncio.run(H.task_hanrei_register_jurisdictions())
    assert "registered" in result


def test_register_jurisdictions_has_total_key() -> None:
    result = asyncio.run(H.task_hanrei_register_jurisdictions())
    assert "total" in result


def test_register_jurisdictions_total_positive() -> None:
    result = asyncio.run(H.task_hanrei_register_jurisdictions())
    assert result["total"] > 0


def test_register_jurisdictions_with_limit() -> None:
    result = asyncio.run(H.task_hanrei_register_jurisdictions(limit=10))
    assert result["limit"] == 10
