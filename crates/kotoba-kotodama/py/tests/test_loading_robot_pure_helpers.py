"""Tests for pure helper functions in primitives/loading_robot.py."""

from __future__ import annotations

import importlib.util as _ilu
import json
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


LR = _load("_loading_robot_pure_helpers", "primitives/loading_robot.py")


# ─── _as_dict ────────────────────────────────────────────────────────────────

def test_as_dict_passthrough_dict() -> None:
    d = {"a": 1}
    assert LR._as_dict(d) is d


def test_as_dict_json_string() -> None:
    result = LR._as_dict('{"x": 10}')
    assert result == {"x": 10}


def test_as_dict_invalid_json_returns_empty() -> None:
    assert LR._as_dict("{not json") == {}


def test_as_dict_json_non_dict_returns_empty() -> None:
    assert LR._as_dict("[1, 2, 3]") == {}


def test_as_dict_none_returns_empty() -> None:
    assert LR._as_dict(None) == {}


def test_as_dict_empty_string_returns_empty() -> None:
    assert LR._as_dict("") == {}


def test_as_dict_integer_returns_empty() -> None:
    assert LR._as_dict(42) == {}


# ─── _as_list ────────────────────────────────────────────────────────────────

def test_as_list_passthrough_list() -> None:
    lst = [1, 2, 3]
    assert LR._as_list(lst) is lst


def test_as_list_json_string() -> None:
    result = LR._as_list("[1, 2, 3]")
    assert result == [1, 2, 3]


def test_as_list_json_non_list_returns_empty() -> None:
    assert LR._as_list('{"key": "val"}') == []


def test_as_list_invalid_json_returns_empty() -> None:
    assert LR._as_list("[not json") == []


def test_as_list_none_returns_empty() -> None:
    assert LR._as_list(None) == []


def test_as_list_empty_string_returns_empty() -> None:
    assert LR._as_list("") == []


# ─── _num ────────────────────────────────────────────────────────────────────

def test_num_integer() -> None:
    assert LR._num(42, 0.0) == 42.0


def test_num_float() -> None:
    assert LR._num(3.14, 0.0) == 3.14


def test_num_string_number() -> None:
    assert LR._num("10.5", 0.0) == 10.5


def test_num_none_returns_default() -> None:
    assert LR._num(None, 99.0) == 99.0


def test_num_bool_returns_default() -> None:
    assert LR._num(True, 99.0) == 99.0
    assert LR._num(False, 99.0) == 99.0


def test_num_non_numeric_string_returns_default() -> None:
    assert LR._num("abc", 7.0) == 7.0


def test_num_negative() -> None:
    assert LR._num(-5, 0.0) == -5.0


# ─── _text ───────────────────────────────────────────────────────────────────

def test_text_string_passthrough() -> None:
    assert LR._text("hello", "default") == "hello"


def test_text_strips_whitespace() -> None:
    assert LR._text("  hi  ", "default") == "hi"


def test_text_empty_string_returns_default() -> None:
    assert LR._text("", "default") == "default"


def test_text_whitespace_only_returns_default() -> None:
    assert LR._text("   ", "default") == "default"


def test_text_none_returns_default() -> None:
    assert LR._text(None, "default") == "default"


def test_text_integer_returns_default() -> None:
    assert LR._text(42, "default") == "default"


# ─── _bbox ───────────────────────────────────────────────────────────────────

def test_bbox_from_list_format() -> None:
    det = {"bbox": [10, 20, 100, 50]}
    result = LR._bbox(det)
    assert result["x"] == 10.0
    assert result["y"] == 20.0
    assert result["width"] == 100.0
    assert result["height"] == 50.0


def test_bbox_from_dict_format() -> None:
    det = {"bbox": {"x": 5, "y": 15, "width": 80, "height": 40}}
    result = LR._bbox(det)
    assert result["x"] == 5.0
    assert result["y"] == 15.0
    assert result["width"] == 80.0
    assert result["height"] == 40.0


def test_bbox_negative_width_clamped_to_zero() -> None:
    det = {"bbox": [0, 0, -10, 20]}
    result = LR._bbox(det)
    assert result["width"] == 0.0


def test_bbox_missing_bbox_uses_det_coords() -> None:
    det = {"x": 1, "y": 2, "width": 30, "height": 15}
    result = LR._bbox(det)
    assert result["x"] == 1.0
    assert result["y"] == 2.0


def test_bbox_empty_det_returns_zeros() -> None:
    result = LR._bbox({})
    assert result["x"] == 0.0
    assert result["y"] == 0.0
    assert result["width"] == 0.0
    assert result["height"] == 0.0
