"""Guard and pure-function tests for ingest/fund/zeebe_tasks.py.

writer.py imports sync_cursor at module top level, so the db stub must be
injected before spec.loader.exec_module() runs.
Relative imports in the fund package require loading submodules in order
with proper __package__ set so Python resolves `.gleif` etc. correctly.
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

# ── package stubs (hierarchy required for relative imports) ──────────────────
if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg

for _pkg_key, _pkg_path in [
    ("kotodama.ingest", _py_src / "kotodama" / "ingest"),
    ("kotodama.ingest.fund", _py_src / "kotodama" / "ingest" / "fund"),
]:
    if _pkg_key not in sys.modules:
        _m = types.ModuleType(_pkg_key)
        _m.__path__ = [str(_pkg_path)]  # type: ignore[attr-defined]
        _m.__package__ = _pkg_key
        sys.modules[_pkg_key] = _m

# ── load fund submodules in dependency order ──────────────────────────────────
_fund_dir = _py_src / "kotodama" / "ingest" / "fund"

for _sub in ["ids", "types", "gleif", "sec_adv"]:
    _key = f"kotodama.ingest.fund.{_sub}"
    if _key not in sys.modules:
        _s = importlib.util.spec_from_file_location(_key, _fund_dir / f"{_sub}.py")
        _m2 = importlib.util.module_from_spec(_s)  # type: ignore[arg-type]
        _m2.__package__ = "kotodama.ingest.fund"
        sys.modules[_key] = _m2
        _s.loader.exec_module(_m2)  # type: ignore[union-attr]

# writer.py imports sync_cursor — inject stub during its load
_writer_key = "kotodama.ingest.fund.writer"
if _writer_key not in sys.modules:
    real_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _s = importlib.util.spec_from_file_location(_writer_key, _fund_dir / "writer.py")
        _m3 = importlib.util.module_from_spec(_s)  # type: ignore[arg-type]
        _m3.__package__ = "kotodama.ingest.fund"
        sys.modules[_writer_key] = _m3
        _s.loader.exec_module(_m3)  # type: ignore[union-attr]
    finally:
        if real_db is not None:
            sys.modules["kotodama.db_sync"] = real_db

# ── load zeebe_tasks ──────────────────────────────────────────────────────────
_MOD_NAME = "_fund_zeebe_tasks"
if _MOD_NAME not in sys.modules:
    _src = _fund_dir / "zeebe_tasks.py"
    real_db = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
        _mod.__package__ = "kotodama.ingest.fund"
        sys.modules[_MOD_NAME] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        if real_db is not None:
            sys.modules["kotodama.db_sync"] = real_db

F = sys.modules[_MOD_NAME]


# ─── task_fund_plan_sources ───────────────────────────────────────────────────

def test_plan_sources_bad_source_returns_error() -> None:
    result = asyncio.run(F.task_fund_plan_sources(sourceId="bad"))
    assert result["ok"] is False


def test_plan_sources_bad_source_error_mentions_source() -> None:
    result = asyncio.run(F.task_fund_plan_sources(sourceId="bad"))
    assert "bad" in result["error"]


def test_plan_sources_sec_adv_ok() -> None:
    result = asyncio.run(F.task_fund_plan_sources(sourceId="sec-adv"))
    assert result["ok"] is True


def test_plan_sources_sec_adv_has_shards() -> None:
    result = asyncio.run(F.task_fund_plan_sources(sourceId="sec-adv"))
    assert "shards" in result


def test_plan_sources_returns_dict() -> None:
    result = asyncio.run(F.task_fund_plan_sources(sourceId="bad"))
    assert isinstance(result, dict)


# ─── task_fund_fetch_raw ─────────────────────────────────────────────────────

def test_fetch_raw_always_ok() -> None:
    result = asyncio.run(F.task_fund_fetch_raw())
    assert result["ok"] is True


def test_fetch_raw_status_is_planned() -> None:
    result = asyncio.run(F.task_fund_fetch_raw())
    assert result["status"] == "planned"


def test_fetch_raw_returns_dict() -> None:
    result = asyncio.run(F.task_fund_fetch_raw())
    assert isinstance(result, dict)


def test_fetch_raw_artifact_is_none() -> None:
    result = asyncio.run(F.task_fund_fetch_raw())
    assert result["artifact"] is None


# ─── task_fund_persist_artifact ───────────────────────────────────────────────

def test_persist_artifact_no_uri_error() -> None:
    result = asyncio.run(F.task_fund_persist_artifact(artifactUri=""))
    assert result["ok"] is False


def test_persist_artifact_no_uri_error_message() -> None:
    result = asyncio.run(F.task_fund_persist_artifact(artifactUri=""))
    assert "artifactUri" in result["error"]


def test_persist_artifact_with_uri_ok() -> None:
    result = asyncio.run(F.task_fund_persist_artifact(artifactUri="s3://bucket/file.csv"))
    assert result["ok"] is True


def test_persist_artifact_with_uri_has_artifact() -> None:
    result = asyncio.run(F.task_fund_persist_artifact(artifactUri="s3://bucket/file.csv"))
    assert "artifact" in result


def test_persist_artifact_returns_dict() -> None:
    result = asyncio.run(F.task_fund_persist_artifact())
    assert isinstance(result, dict)


# ─── task_fund_normalize_manager ─────────────────────────────────────────────

def test_normalize_manager_bad_source_error() -> None:
    result = asyncio.run(F.task_fund_normalize_manager(sourceId="bad"))
    assert result["ok"] is False


def test_normalize_manager_bad_source_error_message() -> None:
    result = asyncio.run(F.task_fund_normalize_manager(sourceId="bad"))
    assert "bad" in result["error"]


def test_normalize_manager_sec_adv_empty_ok() -> None:
    result = asyncio.run(F.task_fund_normalize_manager(sourceId="sec-adv"))
    assert result["ok"] is True


def test_normalize_manager_returns_dict() -> None:
    result = asyncio.run(F.task_fund_normalize_manager(sourceId="bad"))
    assert isinstance(result, dict)


# ─── task_fund_normalize_lp ──────────────────────────────────────────────────

def test_normalize_lp_always_ok() -> None:
    result = asyncio.run(F.task_fund_normalize_lp())
    assert result["ok"] is True


def test_normalize_lp_investors_is_list() -> None:
    result = asyncio.run(F.task_fund_normalize_lp())
    assert isinstance(result["investors"], list)


def test_normalize_lp_returns_dict() -> None:
    result = asyncio.run(F.task_fund_normalize_lp())
    assert isinstance(result, dict)


# ─── task_fund_normalize_investment ──────────────────────────────────────────

def test_normalize_investment_always_ok() -> None:
    result = asyncio.run(F.task_fund_normalize_investment())
    assert result["ok"] is True


def test_normalize_investment_investees_is_list() -> None:
    result = asyncio.run(F.task_fund_normalize_investment())
    assert isinstance(result["investees"], list)


def test_normalize_investment_returns_dict() -> None:
    result = asyncio.run(F.task_fund_normalize_investment())
    assert isinstance(result, dict)


# ─── task_fund_enrich_entity ─────────────────────────────────────────────────

def test_enrich_entity_no_entity_error() -> None:
    result = asyncio.run(F.task_fund_enrich_entity(entity=None))
    assert result["ok"] is False


def test_enrich_entity_no_entity_error_message() -> None:
    result = asyncio.run(F.task_fund_enrich_entity(entity=None))
    assert "entity" in result["error"]


def test_enrich_entity_with_dict_ok() -> None:
    result = asyncio.run(F.task_fund_enrich_entity(entity={"name": "TestFund"}))
    assert result["ok"] is True


def test_enrich_entity_returns_dict() -> None:
    result = asyncio.run(F.task_fund_enrich_entity())
    assert isinstance(result, dict)


# ─── task_fund_compute_returns ───────────────────────────────────────────────

def test_compute_returns_always_ok() -> None:
    result = asyncio.run(F.task_fund_compute_returns())
    assert result["ok"] is True


def test_compute_returns_metrics_is_list() -> None:
    result = asyncio.run(F.task_fund_compute_returns())
    assert isinstance(result["metrics"], list)


def test_compute_returns_has_warning() -> None:
    result = asyncio.run(F.task_fund_compute_returns())
    assert "warning" in result


def test_compute_returns_dict() -> None:
    result = asyncio.run(F.task_fund_compute_returns())
    assert isinstance(result, dict)


# ─── task_fund_write_graph ───────────────────────────────────────────────────

def test_write_graph_dry_run_ok() -> None:
    result = asyncio.run(F.task_fund_write_graph(dryRun=True))
    assert result["ok"] is True


def test_write_graph_dry_run_flag_set() -> None:
    result = asyncio.run(F.task_fund_write_graph(dryRun=True))
    assert result["dryRun"] is True


def test_write_graph_no_rw_healthy_error() -> None:
    result = asyncio.run(F.task_fund_write_graph(dryRun=False, rwHealthy=False))
    assert result["ok"] is False


def test_write_graph_no_rw_healthy_degraded() -> None:
    result = asyncio.run(F.task_fund_write_graph(dryRun=False, rwHealthy=False))
    assert result.get("degraded") is True


def test_write_graph_returns_dict() -> None:
    result = asyncio.run(F.task_fund_write_graph(dryRun=True))
    assert isinstance(result, dict)


# ─── task_fund_verify_coverage ───────────────────────────────────────────────

def test_verify_coverage_zero_written_ok() -> None:
    result = asyncio.run(F.task_fund_verify_coverage(recordsWritten=0, recordsPrepared=0))
    assert result["ok"] is True


def test_verify_coverage_written_exceeds_prepared_fail() -> None:
    result = asyncio.run(F.task_fund_verify_coverage(recordsWritten=10, recordsPrepared=5))
    assert result["ok"] is False


def test_verify_coverage_matching_counts_ok() -> None:
    result = asyncio.run(F.task_fund_verify_coverage(recordsWritten=5, recordsPrepared=10))
    assert result["ok"] is True


def test_verify_coverage_returns_dict() -> None:
    result = asyncio.run(F.task_fund_verify_coverage())
    assert isinstance(result, dict)


def test_verify_coverage_has_written_key() -> None:
    result = asyncio.run(F.task_fund_verify_coverage(recordsWritten=3, recordsPrepared=5))
    assert "recordsWritten" in result
