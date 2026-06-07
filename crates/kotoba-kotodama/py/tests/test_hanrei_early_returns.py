"""Tests for early-return paths in primitives/hanrei.py.

All async task functions validate inputs before accessing DB.
These tests hit only the guard clauses, so no DB, HTTP, or mocking needed.
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

# Stub kotodama.db_sync
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

_MOD_NAME = "_hanrei_early_returns"
if _MOD_NAME not in sys.modules:
    _src = _py_src / "kotodama" / "primitives" / "hanrei.py"
    _spec = importlib.util.spec_from_file_location(_MOD_NAME, _src)
    _mod = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
    sys.modules[_MOD_NAME] = _mod
    _spec.loader.exec_module(_mod)  # type: ignore[union-attr]

H = sys.modules[_MOD_NAME]


# ─── task_hanrei_collect_cases — unknown court ───────────────────────────────

def test_collect_cases_unknown_court_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases(court="nonexistent_court_xyz"))
    assert "error" in result


def test_collect_cases_unknown_court_zero_jobs() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases(court="nonexistent_court_xyz"))
    assert result.get("jobs") == 0


def test_collect_cases_unknown_court_error_mentions_court() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases(court="bogus"))
    assert "bogus" in result["error"]


def test_collect_cases_unknown_court_result_is_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases(court="xyz"))
    assert isinstance(result, dict)


# ─── task_hanrei_collect_case_detail — missing URL ───────────────────────────

def test_collect_case_detail_empty_url_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_case_detail(detailUrl=""))
    assert "error" in result


def test_collect_case_detail_missing_url_error_mentions_detail_url() -> None:
    result = asyncio.run(H.task_hanrei_collect_case_detail(detailUrl=""))
    assert "detailUrl" in result["error"]


def test_collect_case_detail_default_no_url_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_case_detail())
    assert "error" in result


def test_collect_case_detail_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_case_detail())
    assert isinstance(result, dict)


# ─── task_hanrei_collect_cases_batch — empty/invalid list ────────────────────

def test_collect_cases_batch_empty_list_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases_batch(detailUrls=[]))
    assert "error" in result


def test_collect_cases_batch_empty_list_zero_jobs() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases_batch(detailUrls=[]))
    assert result.get("jobs") == 0


def test_collect_cases_batch_none_input_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases_batch(detailUrls=None))
    assert "error" in result


def test_collect_cases_batch_non_http_urls_filtered_out() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases_batch(
        detailUrls=["ftp://bad.com", "not-a-url"]
    ))
    assert "error" in result  # all URLs filtered → empty


def test_collect_cases_batch_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_cases_batch())
    assert isinstance(result, dict)


# ─── task_hanrei_collect_jurisdiction_cases — missing iso3 ───────────────────

def test_collect_jurisdiction_cases_empty_iso3_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_cases(iso3=""))
    assert "error" in result


def test_collect_jurisdiction_cases_empty_iso3_error_mentions_iso3() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_cases(iso3=""))
    assert "iso3" in result["error"]


def test_collect_jurisdiction_cases_default_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_cases())
    assert "error" in result


def test_collect_jurisdiction_cases_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_cases())
    assert isinstance(result, dict)


# ─── task_hanrei_collect_jurisdiction_legislation — missing iso3 ─────────────

def test_collect_jurisdiction_legislation_empty_iso3_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_legislation(iso3=""))
    assert "error" in result


def test_collect_jurisdiction_legislation_default_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_legislation())
    assert "error" in result


def test_collect_jurisdiction_legislation_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_legislation())
    assert isinstance(result, dict)


# ─── task_hanrei_collect_jurisdiction_gazette — missing iso3 ─────────────────

def test_collect_jurisdiction_gazette_empty_iso3_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_gazette(iso3=""))
    assert "error" in result


def test_collect_jurisdiction_gazette_default_returns_error() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_gazette())
    assert "error" in result


def test_collect_jurisdiction_gazette_returns_dict() -> None:
    result = asyncio.run(H.task_hanrei_collect_jurisdiction_gazette())
    assert isinstance(result, dict)
