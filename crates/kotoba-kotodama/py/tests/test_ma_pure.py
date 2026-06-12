"""Pure-function tests for primitives/ma.py.

Most task_* functions in ma.py compute deterministic outputs with no
DB/HTTP/LLM. task_ma_write_graph is tested via the dryRun=True path.
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

# ── db_sync stub (needed for module-level import) ─────────────────────────────
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

_MOD_NAME = "_ma_pure"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "ma.py"
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

M = sys.modules[_MOD_NAME]


# ─── task_ma_sales_origination_intake ────────────────────────────────────────

def test_sales_origination_returns_dict() -> None:
    result = asyncio.run(M.task_ma_sales_origination_intake())
    assert isinstance(result, dict)


def test_sales_origination_has_deal_id() -> None:
    result = asyncio.run(M.task_ma_sales_origination_intake())
    assert result["dealId"]


def test_sales_origination_status_complete() -> None:
    result = asyncio.run(M.task_ma_sales_origination_intake())
    assert result["status"] == "intake-complete"


def test_sales_origination_invalid_side_defaults_sell() -> None:
    result = asyncio.run(M.task_ma_sales_origination_intake(side="unknown"))
    assert result["side"] == "sell-side"


def test_sales_origination_buy_side() -> None:
    result = asyncio.run(M.task_ma_sales_origination_intake(side="buy-side"))
    assert result["side"] == "buy-side"


# ─── task_ma_target_screening_score ──────────────────────────────────────────

def test_screening_score_returns_dict() -> None:
    result = asyncio.run(M.task_ma_target_screening_score())
    assert isinstance(result, dict)


def test_screening_score_has_verdict() -> None:
    result = asyncio.run(M.task_ma_target_screening_score())
    assert "screeningVerdict" in result


def test_screening_score_verdict_valid() -> None:
    result = asyncio.run(M.task_ma_target_screening_score())
    assert result["screeningVerdict"] in {"advance", "hold-for-review"}


def test_screening_score_has_factors() -> None:
    result = asyncio.run(M.task_ma_target_screening_score())
    assert isinstance(result["screeningFactors"], list)


# ─── task_ma_investment_adviser_valuation ────────────────────────────────────

def test_valuation_returns_dict() -> None:
    result = asyncio.run(M.task_ma_investment_adviser_valuation())
    assert isinstance(result, dict)


def test_valuation_has_range() -> None:
    result = asyncio.run(M.task_ma_investment_adviser_valuation())
    assert "valuationRangeLowUsd" in result
    assert "valuationRangeHighUsd" in result


def test_valuation_low_le_high() -> None:
    result = asyncio.run(M.task_ma_investment_adviser_valuation(expectedValueUsd=10_000_000))
    assert result["valuationRangeLowUsd"] <= result["valuationRangeHighUsd"]


# ─── task_ma_buyer_matching_rank ─────────────────────────────────────────────

def test_buyer_matching_returns_dict() -> None:
    result = asyncio.run(M.task_ma_buyer_matching_rank())
    assert isinstance(result, dict)


def test_buyer_matching_has_matches() -> None:
    result = asyncio.run(M.task_ma_buyer_matching_rank())
    assert "matches" in result


def test_buyer_matching_default_candidates_populated() -> None:
    result = asyncio.run(M.task_ma_buyer_matching_rank())
    assert len(result["matches"]) > 0


# ─── task_ma_write_graph (dryRun=True) ───────────────────────────────────────

def test_write_graph_dry_run_ok() -> None:
    result = asyncio.run(M.task_ma_write_graph(dryRun=True))
    assert result["ok"] is True


def test_write_graph_dry_run_flag() -> None:
    result = asyncio.run(M.task_ma_write_graph(dryRun=True))
    assert result["dryRun"] is True


def test_write_graph_not_healthy_degraded() -> None:
    result = asyncio.run(M.task_ma_write_graph(dryRun=False, rwHealthy=False))
    assert result["ok"] is False
    assert result.get("degraded") is True


def test_write_graph_returns_dict() -> None:
    result = asyncio.run(M.task_ma_write_graph(dryRun=True))
    assert isinstance(result, dict)
