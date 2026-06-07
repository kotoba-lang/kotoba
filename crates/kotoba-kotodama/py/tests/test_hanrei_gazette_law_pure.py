"""Pure-path tests for hanrei.py gazette/legislation/egov/wikidata tasks.

These tasks wrap DB inserts in try/except, so with noop cursor they succeed.
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

if "kotodama" not in sys.modules:
    _pkg = types.ModuleType("kotodama")
    _pkg.__path__ = [str(_py_src / "kotodama")]  # type: ignore[attr-defined]
    _pkg.__package__ = "kotodama"
    sys.modules["kotodama"] = _pkg

_MOD_NAME = "_hanrei_gazette_law"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "hanrei.py"
    _prev = sys.modules.get("kotodama.db_sync")
    sys.modules["kotodama.db_sync"] = _db_stub
    try:
        _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
        _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
        sys.modules[_MOD_NAME] = _mod
        _spec.loader.exec_module(_mod)  # type: ignore[union-attr]
    finally:
        if _prev is not None:
            sys.modules["kotodama.db_sync"] = _prev

H = sys.modules[_MOD_NAME]


# ─── task_hanrei_collect_gazette ─────────────────────────────────────────────

def test_collect_gazette_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_gazette())
    assert isinstance(result, dict)


def test_collect_gazette_has_job_id() -> None:
    result = asyncio.run(H.task_hanrei_collect_gazette())
    assert result.get("jobId")


def test_collect_gazette_status_queued() -> None:
    result = asyncio.run(H.task_hanrei_collect_gazette())
    assert result.get("status") == "queued"


def test_collect_gazette_with_start_date() -> None:
    result = asyncio.run(H.task_hanrei_collect_gazette(startDate="2026-01-01"))
    assert "2026-01-01" in result.get("targetUrl", "")


def test_collect_gazette_with_date_range() -> None:
    result = asyncio.run(H.task_hanrei_collect_gazette(
        startDate="2026-01-01", endDate="2026-01-31",
    ))
    assert result.get("jobId")


# ─── task_hanrei_collect_legislation ─────────────────────────────────────────

def test_collect_legislation_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_legislation())
    assert isinstance(result, dict)


def test_collect_legislation_has_job_id() -> None:
    result = asyncio.run(H.task_hanrei_collect_legislation())
    assert result.get("jobId")


def test_collect_legislation_status_queued() -> None:
    result = asyncio.run(H.task_hanrei_collect_legislation())
    assert result.get("status") == "queued"


def test_collect_legislation_with_law_id() -> None:
    result = asyncio.run(H.task_hanrei_collect_legislation(lawId="123AC0000000089"))
    assert "123AC0000000089" in result.get("targetUrl", "")


def test_collect_legislation_with_query() -> None:
    result = asyncio.run(H.task_hanrei_collect_legislation(query="民法"))
    assert result.get("jobId")


# ─── task_hanrei_collect_egov_laws ────────────────────────────────────────────

def test_collect_egov_laws_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_egov_laws())
    assert isinstance(result, dict)


def test_collect_egov_laws_has_jobs_key() -> None:
    result = asyncio.run(H.task_hanrei_collect_egov_laws())
    assert "jobs" in result


def test_collect_egov_laws_has_errors_key() -> None:
    result = asyncio.run(H.task_hanrei_collect_egov_laws())
    assert "errors" in result


def test_collect_egov_laws_created_list() -> None:
    result = asyncio.run(H.task_hanrei_collect_egov_laws())
    assert isinstance(result["created"], list)


def test_collect_egov_laws_default_cats_creates_jobs() -> None:
    result = asyncio.run(H.task_hanrei_collect_egov_laws())
    assert result["jobs"] > 0


def test_collect_egov_laws_specific_category() -> None:
    result = asyncio.run(H.task_hanrei_collect_egov_laws(categories=[1]))
    assert isinstance(result, dict)


# ─── task_hanrei_collect_wikidata_courts ─────────────────────────────────────

def test_collect_wikidata_courts_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_wikidata_courts())
    assert isinstance(result, dict)


def test_collect_wikidata_courts_has_jobs_key() -> None:
    result = asyncio.run(H.task_hanrei_collect_wikidata_courts())
    assert "jobs" in result


def test_collect_wikidata_courts_has_errors_key() -> None:
    result = asyncio.run(H.task_hanrei_collect_wikidata_courts())
    assert "errors" in result


def test_collect_wikidata_courts_created_list() -> None:
    result = asyncio.run(H.task_hanrei_collect_wikidata_courts())
    assert isinstance(result["created"], list)


def test_collect_wikidata_courts_default_runs_all() -> None:
    result = asyncio.run(H.task_hanrei_collect_wikidata_courts())
    assert result["jobs"] > 0


def test_collect_wikidata_courts_filtered_by_query_id() -> None:
    result = asyncio.run(H.task_hanrei_collect_wikidata_courts(queries=["jp_all_courts"]))
    assert isinstance(result, dict)
