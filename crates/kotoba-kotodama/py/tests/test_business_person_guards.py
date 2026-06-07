"""Guard and pure-path tests for primitives/business_person.py."""

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

# ── load business_person ──────────────────────────────────────────────────────
_MOD_NAME = "_business_person_guards"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "business_person.py"
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

BP = sys.modules[_MOD_NAME]


# ─── task_business_person_plan_public_role_sources — pure ─────────────────────

def test_plan_sources_always_ok() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources())
    assert result["ok"] is True


def test_plan_sources_has_source_id() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources())
    assert "sourceId" in result


def test_plan_sources_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources())
    assert isinstance(result, dict)


def test_plan_sources_public_only() -> None:
    result = asyncio.run(BP.task_business_person_plan_public_role_sources())
    assert result["publicOnly"] is True


# ─── task_business_person_fetch_public_source — guard: fetch disabled ─────────

def test_fetch_source_fetch_disabled_not_fetched() -> None:
    result = asyncio.run(BP.task_business_person_fetch_public_source(fetch=False))
    assert result["fetched"] is False


def test_fetch_source_fetch_disabled_ok() -> None:
    result = asyncio.run(BP.task_business_person_fetch_public_source(fetch=False))
    assert result["ok"] is True


def test_fetch_source_no_url_not_fetched() -> None:
    result = asyncio.run(BP.task_business_person_fetch_public_source(sourceUrl=""))
    assert result["fetched"] is False


def test_fetch_source_invalid_url_scheme_error() -> None:
    result = asyncio.run(BP.task_business_person_fetch_public_source(
        sourceUrl="ftp://example.com", fetch=True
    ))
    assert result["ok"] is False


def test_fetch_source_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_fetch_public_source(fetch=False))
    assert isinstance(result, dict)


# ─── task_business_person_prepare_source_request — pure guards ───────────────

def test_prepare_request_fetch_false_returns_ok() -> None:
    result = asyncio.run(BP.task_business_person_prepare_source_request(fetch=False))
    assert result["ok"] is True


def test_prepare_request_fetch_false_not_prepared() -> None:
    result = asyncio.run(BP.task_business_person_prepare_source_request(fetch=False))
    assert result["requestPrepared"] is False


def test_prepare_request_no_url_not_prepared() -> None:
    result = asyncio.run(BP.task_business_person_prepare_source_request(fetch=True))
    assert result["requestPrepared"] is False


def test_prepare_request_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_prepare_source_request(fetch=False))
    assert isinstance(result, dict)


# ─── task_business_person_advance_source_cursor — pure ───────────────────────

def test_advance_cursor_always_ok() -> None:
    result = asyncio.run(BP.task_business_person_advance_source_cursor())
    assert result["ok"] is True


def test_advance_cursor_has_pages_fetched() -> None:
    result = asyncio.run(BP.task_business_person_advance_source_cursor(pagesFetched=3))
    assert result["pagesFetched"] == 4


def test_advance_cursor_no_next_url_no_continue() -> None:
    result = asyncio.run(BP.task_business_person_advance_source_cursor())
    assert result["hasNextPage"] is False


def test_advance_cursor_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_advance_source_cursor())
    assert isinstance(result, dict)


# ─── task_business_person_schedule_next_page — pure ──────────────────────────

def test_schedule_next_page_no_next_not_scheduled() -> None:
    result = asyncio.run(BP.task_business_person_schedule_next_page(hasNextPage=False))
    assert result["nextPageScheduled"] is False


def test_schedule_next_page_no_next_ok() -> None:
    result = asyncio.run(BP.task_business_person_schedule_next_page(hasNextPage=False))
    assert result["ok"] is True


def test_schedule_next_page_with_url_scheduled() -> None:
    result = asyncio.run(BP.task_business_person_schedule_next_page(
        hasNextPage=True, nextSourceUrl="https://example.com/page2"
    ))
    assert result["nextPageScheduled"] is True


def test_schedule_next_page_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_schedule_next_page())
    assert isinstance(result, dict)


# ─── task_business_person_normalize_public_roles — pure ──────────────────────

def test_normalize_roles_no_rows_empty_list() -> None:
    result = asyncio.run(BP.task_business_person_normalize_public_roles())
    assert result["roles"] == []


def test_normalize_roles_always_ok() -> None:
    result = asyncio.run(BP.task_business_person_normalize_public_roles())
    assert result["ok"] is True


def test_normalize_roles_zero_prepared() -> None:
    result = asyncio.run(BP.task_business_person_normalize_public_roles())
    assert result["recordsPrepared"] == 0


def test_normalize_roles_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_normalize_public_roles())
    assert isinstance(result, dict)


# ─── task_business_person_write_graph — pure guards ──────────────────────────

def test_write_graph_dry_run_ok() -> None:
    result = asyncio.run(BP.task_business_person_write_graph(dryRun=True))
    assert result["ok"] is True


def test_write_graph_dry_run_flag_set() -> None:
    result = asyncio.run(BP.task_business_person_write_graph(dryRun=True))
    assert result["dryRun"] is True


def test_write_graph_not_healthy_error() -> None:
    result = asyncio.run(BP.task_business_person_write_graph(dryRun=False, rwHealthy=False))
    assert result["ok"] is False


def test_write_graph_not_healthy_degraded() -> None:
    result = asyncio.run(BP.task_business_person_write_graph(dryRun=False, rwHealthy=False))
    assert result.get("degraded") is True


def test_write_graph_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_write_graph(dryRun=True))
    assert isinstance(result, dict)


# ─── task_business_person_verify_coverage — pure math ────────────────────────

def test_verify_coverage_zero_ok() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage())
    assert result["ok"] is True


def test_verify_coverage_visible_exceeds_prepared_fail() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage(
        recordsPrepared=5, recordsVisible=10
    ))
    assert result["ok"] is False


def test_verify_coverage_has_prepared_key() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage(recordsPrepared=3))
    assert result["recordsPrepared"] == 3


def test_verify_coverage_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_verify_coverage())
    assert isinstance(result, dict)


# ─── task_business_person_compute_influence_scores — pure ────────────────────

def test_compute_influence_no_persons_empty_scores() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores())
    assert result["scores"] == []


def test_compute_influence_zero_count() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores())
    assert result["scoresCount"] == 0


def test_compute_influence_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_compute_influence_scores())
    assert isinstance(result, dict)


# ─── task_business_person_write_influence_scores — empty scores early-return ──

def test_write_influence_scores_empty_ok() -> None:
    result = asyncio.run(BP.task_business_person_write_influence_scores(scores=None))
    assert result["ok"] is True


def test_write_influence_scores_empty_zero_written() -> None:
    result = asyncio.run(BP.task_business_person_write_influence_scores(scores=None))
    assert result["recordsWritten"] == 0


def test_write_influence_scores_returns_dict() -> None:
    result = asyncio.run(BP.task_business_person_write_influence_scores())
    assert isinstance(result, dict)
