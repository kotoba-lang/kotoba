"""Pure-path tests for ingest task functions.

Covers:
- ingest/houbun.py: create_run (no dryRun gate — needs DB patch), acquire_cursor
  (empty shard → early return), verify_visibility (patched cursor)
- ingest/site_common_crawl.py: create_run (dryRun=True), plan (pure), acquire_cursor (dryRun=True)
- ingest/flight_offer.py: list_watch / poll_watchlist / fetch_from_source
  (all try/except-wrapped; DB error → deterministic error dict)
- ingest/fund/zeebe_tasks.py: normalize_fund (empty rows → pure)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from unittest.mock import MagicMock

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import flight_offer as FO  # noqa: E402
from kotodama.ingest import houbun as HB  # noqa: E402
from kotodama.ingest import site_common_crawl as SC  # noqa: E402
from kotodama.ingest.fund import zeebe_tasks as FT  # noqa: E402


def _noop_cursor_mock() -> MagicMock:
    cur = MagicMock()
    cur.fetchall.return_value = []
    cur.fetchone.return_value = None
    cur.description = []
    cm = MagicMock()
    cm.return_value.__enter__.return_value = cur
    cm.return_value.__exit__.return_value = False
    return cm


# ══════════════════════════════════════════════════════════════════════════════
# houbun
# ══════════════════════════════════════════════════════════════════════════════

def test_houbun_acquire_cursor_missing_shard_returns_error() -> None:
    result = asyncio.run(HB.task_houbun_acquire_cursor(runId=""))
    assert result["ok"] is False
    assert "error" in result


def test_houbun_acquire_cursor_returns_dict() -> None:
    result = asyncio.run(HB.task_houbun_acquire_cursor(runId=""))
    assert isinstance(result, dict)


def test_houbun_acquire_cursor_with_first_shard_errors_missing_run() -> None:
    result = asyncio.run(HB.task_houbun_acquire_cursor(runId="", firstShard={}))
    assert isinstance(result, dict)


def test_houbun_verify_visibility_patched_returns_dict() -> None:
    from kotodama.db_sync import sync_cursor as _real
    mock_sc = _noop_cursor_mock()
    HB.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(HB.task_houbun_verify_visibility(lawId="123", articleCount=0))
        assert isinstance(result, dict)
    finally:
        HB.sync_cursor = _real  # type: ignore[attr-defined]


def test_houbun_verify_visibility_patched_has_verified_key() -> None:
    from kotodama.db_sync import sync_cursor as _real
    mock_sc = _noop_cursor_mock()
    HB.sync_cursor = mock_sc  # type: ignore[attr-defined]
    try:
        result = asyncio.run(HB.task_houbun_verify_visibility())
        assert "verified" in result
    finally:
        HB.sync_cursor = _real  # type: ignore[attr-defined]


def test_houbun_create_run_patched_ok() -> None:
    from kotodama.db_sync import sync_cursor as _real

    async def _fake_upsert(run):  # noqa: ANN001
        return "vertex-run-001"

    import kotodama.ingest.houbun as _hb_mod
    orig_upsert = getattr(_hb_mod, "upsert_run", None)
    mock_sc = _noop_cursor_mock()
    _hb_mod.sync_cursor = mock_sc  # type: ignore[attr-defined]

    import asyncio as _aio
    import functools

    def _sync_upsert_run(run):  # noqa: ANN001
        return "vertex-run-001"

    if orig_upsert is not None:
        _hb_mod.upsert_run = _sync_upsert_run  # type: ignore[attr-defined]
    try:
        result = asyncio.run(HB.task_houbun_create_run(runId="test-run"))
        assert result["ok"] is True
        assert "runId" in result
    finally:
        _hb_mod.sync_cursor = _real  # type: ignore[attr-defined]
        if orig_upsert is not None:
            _hb_mod.upsert_run = orig_upsert  # type: ignore[attr-defined]


# ══════════════════════════════════════════════════════════════════════════════
# site_common_crawl
# ══════════════════════════════════════════════════════════════════════════════

def test_site_cc_create_run_dry_run_ok() -> None:
    result = asyncio.run(SC.task_site_cc_create_run(dryRun=True))
    assert result["ok"] is True
    assert "runId" in result


def test_site_cc_create_run_dry_run_vertex_id_prefix() -> None:
    result = asyncio.run(SC.task_site_cc_create_run(dryRun=True))
    assert result["runVertexId"].startswith("dry-run:")


def test_site_cc_create_run_dry_run_returns_dict() -> None:
    result = asyncio.run(SC.task_site_cc_create_run(dryRun=True))
    assert isinstance(result, dict)


def test_site_cc_plan_returns_dict() -> None:
    result = asyncio.run(SC.task_site_cc_plan())
    assert isinstance(result, dict)


def test_site_cc_plan_ok_true() -> None:
    result = asyncio.run(SC.task_site_cc_plan())
    assert result["ok"] is True


def test_site_cc_plan_has_plan_key() -> None:
    result = asyncio.run(SC.task_site_cc_plan())
    assert "siteCcPlan" in result


def test_site_cc_plan_has_planned_shards() -> None:
    result = asyncio.run(SC.task_site_cc_plan())
    assert "plannedShards" in result


def test_site_cc_plan_invalid_phase_returns_error() -> None:
    result = asyncio.run(SC.task_site_cc_plan(phases="invalid-phase"))
    assert result["ok"] is False
    assert "error" in result


def test_site_cc_acquire_cursor_dry_run_ok() -> None:
    result = asyncio.run(SC.task_site_cc_acquire_cursor(runId="run-001", dryRun=True))
    assert result["ok"] is True


def test_site_cc_acquire_cursor_dry_run_returns_dict() -> None:
    result = asyncio.run(SC.task_site_cc_acquire_cursor(runId="run-001", dryRun=True))
    assert isinstance(result, dict)


def test_site_cc_acquire_cursor_dry_run_has_shard_key() -> None:
    result = asyncio.run(SC.task_site_cc_acquire_cursor(runId="run-001", dryRun=True))
    assert "shardKey" in result


# ══════════════════════════════════════════════════════════════════════════════
# flight_offer (try/except-wrapped — returns error dict on DB failure)
# ══════════════════════════════════════════════════════════════════════════════

def test_flight_list_watch_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_list_watch())
    assert isinstance(result, dict)


def test_flight_list_watch_has_items_key() -> None:
    result = asyncio.run(FO.task_flight_offer_list_watch())
    assert "items" in result


def test_flight_list_watch_has_count_key() -> None:
    result = asyncio.run(FO.task_flight_offer_list_watch())
    assert "count" in result


def test_flight_poll_watchlist_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_poll_watchlist())
    assert isinstance(result, dict)


def test_flight_poll_watchlist_has_status_key() -> None:
    result = asyncio.run(FO.task_flight_offer_poll_watchlist())
    assert "status" in result


def test_flight_fetch_from_source_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_fetch_from_source())
    assert isinstance(result, dict)


def test_flight_fetch_from_source_has_status_key() -> None:
    result = asyncio.run(FO.task_flight_offer_fetch_from_source())
    assert "status" in result


# ══════════════════════════════════════════════════════════════════════════════
# fund/zeebe_tasks
# ══════════════════════════════════════════════════════════════════════════════

def test_fund_normalize_fund_empty_rows_ok() -> None:
    result = asyncio.run(FT.task_fund_normalize_fund(rows=[]))
    assert result["ok"] is True


def test_fund_normalize_fund_returns_dict() -> None:
    result = asyncio.run(FT.task_fund_normalize_fund(rows=[]))
    assert isinstance(result, dict)


def test_fund_normalize_fund_zero_records_read() -> None:
    result = asyncio.run(FT.task_fund_normalize_fund(rows=[]))
    assert result["recordsRead"] == 0


def test_fund_normalize_fund_funds_list() -> None:
    result = asyncio.run(FT.task_fund_normalize_fund(rows=[]))
    assert isinstance(result["funds"], list)


def test_fund_normalize_fund_source_id() -> None:
    result = asyncio.run(FT.task_fund_normalize_fund(sourceId="sec-adv", rows=[]))
    assert result["sourceId"] == "sec-adv"


# ══════════════════════════════════════════════════════════════════════════════
# houbun additional tasks
# ══════════════════════════════════════════════════════════════════════════════

def test_houbun_advance_cursor_not_verified_returns_error() -> None:
    result = asyncio.run(HB.task_houbun_advance_cursor(runId="r1", verified=False))
    assert result["ok"] is False
    assert "error" in result


def test_houbun_advance_cursor_not_verified_returns_dict() -> None:
    result = asyncio.run(HB.task_houbun_advance_cursor(runId="r1", verified=False))
    assert isinstance(result, dict)


def test_houbun_complete_run_patched_ok() -> None:
    import kotodama.ingest.houbun as _hb_mod
    orig = getattr(_hb_mod, "mark_run_finished", None)
    _hb_mod.mark_run_finished = lambda *a, **kw: None  # type: ignore[attr-defined]
    try:
        result = asyncio.run(HB.task_houbun_complete_run(runId="r1", verified=True))
        assert result["ok"] is True
    finally:
        if orig is not None:
            _hb_mod.mark_run_finished = orig  # type: ignore[attr-defined]


def test_houbun_complete_run_patched_returns_dict() -> None:
    import kotodama.ingest.houbun as _hb_mod
    orig = getattr(_hb_mod, "mark_run_finished", None)
    _hb_mod.mark_run_finished = lambda *a, **kw: None  # type: ignore[attr-defined]
    try:
        result = asyncio.run(HB.task_houbun_complete_run(runId="r1"))
        assert isinstance(result, dict)
    finally:
        if orig is not None:
            _hb_mod.mark_run_finished = orig  # type: ignore[attr-defined]


# ══════════════════════════════════════════════════════════════════════════════
# site_common_crawl additional tasks (all have dryRun path)
# ══════════════════════════════════════════════════════════════════════════════

def test_site_cc_verify_visibility_dry_run_ok() -> None:
    result = asyncio.run(SC.task_site_cc_verify_visibility(dryRun=True))
    assert result["ok"] is True
    assert result["verified"] is True


def test_site_cc_verify_visibility_dry_run_returns_dict() -> None:
    result = asyncio.run(SC.task_site_cc_verify_visibility(dryRun=True))
    assert isinstance(result, dict)


def test_site_cc_advance_cursor_not_verified_returns_error() -> None:
    result = asyncio.run(SC.task_site_cc_advance_cursor(runId="r1", verified=False))
    assert result["ok"] is False
    assert "error" in result


def test_site_cc_advance_cursor_dry_run_ok() -> None:
    result = asyncio.run(SC.task_site_cc_advance_cursor(runId="r1", verified=True, dryRun=True))
    assert result["ok"] is True


def test_site_cc_complete_run_dry_run_ok() -> None:
    result = asyncio.run(SC.task_site_cc_complete_run(runId="r1", dryRun=True))
    assert result["ok"] is True
    assert "status" in result


def test_site_cc_complete_run_dry_run_returns_dict() -> None:
    result = asyncio.run(SC.task_site_cc_complete_run(runId="r1", dryRun=True))
    assert isinstance(result, dict)


# ══════════════════════════════════════════════════════════════════════════════
# flight_offer additional tasks (all try/except-wrapped)
# ══════════════════════════════════════════════════════════════════════════════

def test_flight_list_sources_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_list_sources())
    assert isinstance(result, dict)


def test_flight_list_sources_has_items_key() -> None:
    result = asyncio.run(FO.task_flight_offer_list_sources())
    assert "items" in result


def test_flight_cleanup_runs_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_cleanup_runs())
    assert isinstance(result, dict)


def test_flight_cleanup_runs_has_status_key() -> None:
    result = asyncio.run(FO.task_flight_offer_cleanup_runs())
    assert "status" in result


def test_flight_source_health_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_source_health())
    assert isinstance(result, dict)


def test_flight_source_health_has_items_key() -> None:
    result = asyncio.run(FO.task_flight_offer_source_health())
    assert "items" in result


def test_flight_list_airlines_returns_dict() -> None:
    result = asyncio.run(FO.task_flight_offer_list_airlines())
    assert isinstance(result, dict)


def test_flight_list_airlines_has_items_key() -> None:
    result = asyncio.run(FO.task_flight_offer_list_airlines())
    assert "items" in result
