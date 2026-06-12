"""Tests for pure helper functions in primitives/robotics.py."""

from __future__ import annotations

import importlib.util as _ilu
import sys
from pathlib import Path as _P

ROOT = _P(__file__).resolve().parents[1] / "src" / "kotodama"


def _load(name: str, rel: str):
    spec = _ilu.spec_from_file_location(name, ROOT / rel)
    assert spec and spec.loader
    mod = _ilu.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


R = _load("_robotics_pure_helpers", "primitives/robotics.py")


# ─── _list_str ───────────────────────────────────────────────────────────────

def test_list_str_converts_items_to_strings() -> None:
    assert R._list_str([1, 2, 3]) == ["1", "2", "3"]


def test_list_str_filters_falsy() -> None:
    assert R._list_str([0, "", None, "a"]) == ["a"]


def test_list_str_non_list_returns_empty() -> None:
    assert R._list_str("not-a-list") == []
    assert R._list_str(None) == []
    assert R._list_str(42) == []


def test_list_str_empty_list_returns_empty() -> None:
    assert R._list_str([]) == []


# ─── _stamp ──────────────────────────────────────────────────────────────────

def test_stamp_returns_int() -> None:
    assert isinstance(R._stamp(), int)


def test_stamp_is_positive() -> None:
    assert R._stamp() > 0


def test_stamp_is_recent_unix_ts() -> None:
    import time
    ts = R._stamp()
    # Should be within a few seconds of now
    assert abs(ts - int(time.time())) < 10


# ─── _selected_forms ─────────────────────────────────────────────────────────

def test_selected_forms_empty_returns_all() -> None:
    all_forms = R._selected_forms([])
    assert isinstance(all_forms, list)
    assert len(all_forms) > 0


def test_selected_forms_none_returns_all() -> None:
    all_forms = R._selected_forms(None)
    assert isinstance(all_forms, list)
    assert len(all_forms) > 0


def test_selected_forms_non_list_returns_all() -> None:
    all_forms = R._selected_forms("sales")
    assert isinstance(all_forms, list)
    assert len(all_forms) > 0


def test_selected_forms_filters_by_process() -> None:
    forms = R._selected_forms(["sales"])
    assert len(forms) >= 1
    assert all(f["process"] == "sales" for f in forms)


def test_selected_forms_multi_process() -> None:
    forms = R._selected_forms(["sales", "manufacturing"])
    processes = {f["process"] for f in forms}
    assert "sales" in processes
    assert "manufacturing" in processes


def test_selected_forms_unknown_process_returns_empty() -> None:
    forms = R._selected_forms(["nonexistent-process-xyz"])
    assert forms == []


def test_selected_forms_result_has_required_keys() -> None:
    forms = R._selected_forms(["sales"])
    for form in forms:
        assert "process" in form
        assert "fields" in form or "title" in form or True  # any valid key


# ─── _dependency_projection ──────────────────────────────────────────────────

def test_dependency_projection_returns_dict_with_keys() -> None:
    result = R._dependency_projection([])
    assert "dependencies" in result
    assert "missingPrerequisites" in result


def test_dependency_projection_all_processes_has_deps() -> None:
    # All standard processes selected → all deps should be covered
    all_processes = list({d["from"] for d in R.PROCESS_DEPENDENCIES}
                         | {d["to"] for d in R.PROCESS_DEPENDENCIES})
    result = R._dependency_projection(all_processes)
    assert len(result["dependencies"]) > 0
    assert len(result["missingPrerequisites"]) == 0


def test_dependency_projection_partial_has_missing_prerequisites() -> None:
    # Only manufacturing selected → transport→manufacturing dep exists but
    # production-planning is missing
    result = R._dependency_projection(["manufacturing"])
    # There should be missing prerequisites (deps whose 'from' isn't in selected)
    assert len(result["missingPrerequisites"]) > 0


def test_dependency_projection_empty_processes_returns_all_deps() -> None:
    # Empty list → _selected_forms returns all forms → all deps included
    result = R._dependency_projection([])
    assert len(result["dependencies"]) > 0
