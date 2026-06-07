"""Pure helper tests for projector, loading_robot, and business_person primitives.

Covers pure functions with no DB/HTTP/LLM dependencies:
- projector: _now_iso / _now_ms / _new_rkey / _strip_reasoning / _extract_final_answer
- loading_robot: _as_dict / _as_list / _num / _text / _bbox / _normalize_detections
- business_person: _today / _slug / _stable_id / _as_rows / _as_json / _as_text /
                   _is_public_http_url / _compact_cik / _bounded_page_size / _with_query
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import projector as PJ
from kotodama.primitives import loading_robot as LR
from kotodama.primitives import business_person as BP


# ─── projector — _now_iso ─────────────────────────────────────────────────────

def test_pj_now_iso_returns_string():
    assert isinstance(PJ._now_iso(), str)


def test_pj_now_iso_ends_with_z():
    assert PJ._now_iso().endswith("Z")


def test_pj_now_iso_contains_t():
    assert "T" in PJ._now_iso()


# ─── projector — _now_ms ──────────────────────────────────────────────────────

def test_pj_now_ms_returns_int():
    assert isinstance(PJ._now_ms(), int)


def test_pj_now_ms_is_positive():
    assert PJ._now_ms() > 0


def test_pj_now_ms_is_recent():
    # Should be around current epoch in ms
    import time
    result = PJ._now_ms()
    assert result > 1_700_000_000_000  # after 2023


# ─── projector — _new_rkey ───────────────────────────────────────────────────

def test_pj_new_rkey_starts_with_prefix():
    result = PJ._new_rkey("proj")
    assert result.startswith("proj-")


def test_pj_new_rkey_returns_string():
    assert isinstance(PJ._new_rkey("x"), str)


def test_pj_new_rkey_is_unique():
    a = PJ._new_rkey("x")
    b = PJ._new_rkey("x")
    assert a != b


# ─── projector — _strip_reasoning ────────────────────────────────────────────

def test_pj_strip_reasoning_no_tag():
    reasoning, cleaned = PJ._strip_reasoning("just text")
    assert reasoning == ""
    assert cleaned == "just text"


def test_pj_strip_reasoning_with_tag():
    text = "<reasoning>my thoughts</reasoning>Final answer"
    reasoning, cleaned = PJ._strip_reasoning(text)
    assert reasoning == "my thoughts"
    assert "Final answer" in cleaned
    assert "<reasoning>" not in cleaned


def test_pj_strip_reasoning_empty():
    reasoning, cleaned = PJ._strip_reasoning("")
    assert reasoning == ""
    assert cleaned == ""


def test_pj_strip_reasoning_none():
    reasoning, cleaned = PJ._strip_reasoning(None)
    assert reasoning == ""
    assert isinstance(cleaned, str)


# ─── projector — _extract_final_answer ───────────────────────────────────────

def test_pj_extract_final_answer_with_tag():
    text = "thinking...<answer>42</answer>"
    result = PJ._extract_final_answer(text)
    assert result == "42"


def test_pj_extract_final_answer_no_tag():
    text = "just text without tag"
    result = PJ._extract_final_answer(text)
    assert result == "just text without tag"


def test_pj_extract_final_answer_empty():
    result = PJ._extract_final_answer("")
    assert result == ""


# ─── loading_robot — _as_dict ─────────────────────────────────────────────────

def test_lr_as_dict_with_dict():
    d = {"key": "val"}
    assert LR._as_dict(d) == d


def test_lr_as_dict_json_string():
    result = LR._as_dict('{"key": "val"}')
    assert result == {"key": "val"}


def test_lr_as_dict_invalid_string():
    assert LR._as_dict("not json") == {}


def test_lr_as_dict_none():
    assert LR._as_dict(None) == {}


def test_lr_as_dict_list_returns_empty():
    assert LR._as_dict([1, 2]) == {}


# ─── loading_robot — _as_list ─────────────────────────────────────────────────

def test_lr_as_list_with_list():
    assert LR._as_list([1, 2, 3]) == [1, 2, 3]


def test_lr_as_list_json_string():
    result = LR._as_list('[1, 2, 3]')
    assert result == [1, 2, 3]


def test_lr_as_list_non_list_json():
    assert LR._as_list('{"key": "val"}') == []


def test_lr_as_list_none():
    assert LR._as_list(None) == []


def test_lr_as_list_invalid_string():
    assert LR._as_list("bad json") == []


# ─── loading_robot — _num ─────────────────────────────────────────────────────

def test_lr_num_int():
    assert LR._num(5, 0.0) == 5.0


def test_lr_num_float():
    assert LR._num(3.14, 0.0) == 3.14


def test_lr_num_string_float():
    assert LR._num("2.5", 0.0) == 2.5


def test_lr_num_none_returns_default():
    assert LR._num(None, 42.0) == 42.0


def test_lr_num_bool_returns_default():
    assert LR._num(True, 99.0) == 99.0


def test_lr_num_inf_returns_default():
    assert LR._num(float("inf"), 7.0) == 7.0


# ─── loading_robot — _text ────────────────────────────────────────────────────

def test_lr_text_returns_stripped_string():
    assert LR._text("  hello  ", "default") == "hello"


def test_lr_text_empty_returns_default():
    assert LR._text("", "mydefault") == "mydefault"


def test_lr_text_none_returns_default():
    assert LR._text(None, "fallback") == "fallback"


def test_lr_text_whitespace_returns_default():
    assert LR._text("   ", "default") == "default"


# ─── loading_robot — _bbox ────────────────────────────────────────────────────

def test_lr_bbox_from_list_format():
    det = {"bbox": [10, 20, 30, 40]}
    result = LR._bbox(det)
    assert result["x"] == 10.0
    assert result["y"] == 20.0
    assert result["width"] == 30.0
    assert result["height"] == 40.0


def test_lr_bbox_from_dict_format():
    det = {"bbox": {"x": 5, "y": 10, "width": 20, "height": 15}}
    result = LR._bbox(det)
    assert result["x"] == 5.0
    assert result["width"] == 20.0


def test_lr_bbox_empty_returns_zeros():
    result = LR._bbox({})
    assert result["x"] == 0.0
    assert result["y"] == 0.0
    assert result["width"] == 0.0
    assert result["height"] == 0.0


def test_lr_bbox_clamps_negative_width_to_zero():
    det = {"bbox": [0, 0, -10, -5]}
    result = LR._bbox(det)
    assert result["width"] == 0.0
    assert result["height"] == 0.0


# ─── loading_robot — _normalize_detections ────────────────────────────────────

def test_lr_normalize_detections_empty():
    assert LR._normalize_detections([]) == []


def test_lr_normalize_detections_basic():
    raw = [{"label": "box", "confidence": 0.9, "bbox": [0, 0, 10, 10]}]
    result = LR._normalize_detections(raw)
    assert len(result) == 1
    assert result[0]["label"] == "box"
    assert result[0]["confidence"] == 0.9


def test_lr_normalize_detections_clamps_confidence():
    raw = [{"label": "item", "confidence": 1.5}]
    result = LR._normalize_detections(raw)
    assert result[0]["confidence"] <= 1.0


def test_lr_normalize_detections_sorted_by_confidence_desc():
    raw = [
        {"label": "low", "confidence": 0.3},
        {"label": "high", "confidence": 0.9},
    ]
    result = LR._normalize_detections(raw)
    assert result[0]["label"] == "high"


def test_lr_normalize_detections_has_required_keys():
    raw = [{"label": "obj", "confidence": 0.5}]
    result = LR._normalize_detections(raw)
    for key in ("id", "label", "confidence", "bbox", "estimatedWeightKg", "attributes"):
        assert key in result[0]


# ─── business_person — _today ─────────────────────────────────────────────────

def test_bp_today_returns_string():
    assert isinstance(BP._today(), str)


def test_bp_today_is_date_format():
    result = BP._today()
    assert len(result) == 10
    assert result[4] == "-" and result[7] == "-"


# ─── business_person — _slug ──────────────────────────────────────────────────

def test_bp_slug_lowercases():
    assert BP._slug("Hello World") == "hello-world"


def test_bp_slug_replaces_spaces():
    result = BP._slug("Acme Corp")
    assert " " not in result
    assert "acme" in result


def test_bp_slug_strips_special_chars():
    result = BP._slug("Test & Company!")
    assert "&" not in result
    assert "!" not in result


def test_bp_slug_empty_returns_unknown():
    assert BP._slug("") == "unknown"
    assert BP._slug(None) == "unknown"


def test_bp_slug_truncates_to_96():
    result = BP._slug("a" * 200)
    assert len(result) <= 96


# ─── business_person — _stable_id ─────────────────────────────────────────────

def test_bp_stable_id_starts_with_prefix():
    result = BP._stable_id("company", "ABC Corp", "JP")
    assert result.startswith("company-")


def test_bp_stable_id_is_deterministic():
    a = BP._stable_id("pfx", "partA", "partB")
    b = BP._stable_id("pfx", "partA", "partB")
    assert a == b


def test_bp_stable_id_differs_by_parts():
    a = BP._stable_id("pfx", "val1")
    b = BP._stable_id("pfx", "val2")
    assert a != b


# ─── business_person — _as_rows ───────────────────────────────────────────────

def test_bp_as_rows_list_of_dicts():
    rows = [{"a": 1}, {"b": 2}]
    assert BP._as_rows(rows) == rows


def test_bp_as_rows_filters_non_dicts():
    rows = [{"a": 1}, "not a dict", 42]
    result = BP._as_rows(rows)
    assert len(result) == 1


def test_bp_as_rows_empty():
    assert BP._as_rows([]) == []


def test_bp_as_rows_json_string():
    result = BP._as_rows('[{"a": 1}]')
    assert result == [{"a": 1}]


# ─── business_person — _as_json ───────────────────────────────────────────────

def test_bp_as_json_dict_passthrough():
    d = {"key": "val"}
    assert BP._as_json(d) is d


def test_bp_as_json_list_passthrough():
    lst = [1, 2]
    assert BP._as_json(lst) is lst


def test_bp_as_json_json_string():
    result = BP._as_json('{"x": 1}')
    assert result == {"x": 1}


def test_bp_as_json_none_returns_none():
    assert BP._as_json(None) is None


# ─── business_person — _is_public_http_url ────────────────────────────────────

def test_bp_is_public_http_url_valid():
    assert BP._is_public_http_url("https://www.example.com/") is True


def test_bp_is_public_http_url_http():
    assert BP._is_public_http_url("http://example.com/") is True


def test_bp_is_public_http_url_no_scheme():
    assert BP._is_public_http_url("example.com") is False


def test_bp_is_public_http_url_empty():
    assert BP._is_public_http_url("") is False


def test_bp_is_public_http_url_none():
    assert BP._is_public_http_url(None) is False


# ─── business_person — _compact_cik ──────────────────────────────────────────

def test_bp_compact_cik_pads_to_10():
    result = BP._compact_cik("12345")
    assert len(result) == 10
    assert result == "0000012345"


def test_bp_compact_cik_strips_non_digits():
    result = BP._compact_cik("CIK-00012345")
    assert result == "0000012345"


def test_bp_compact_cik_empty_returns_empty():
    assert BP._compact_cik("") == ""
    assert BP._compact_cik(None) == ""


# ─── business_person — _bounded_page_size ────────────────────────────────────

def test_bp_bounded_page_size_normal():
    assert BP._bounded_page_size(50) == 50


def test_bp_bounded_page_size_clamps_high():
    assert BP._bounded_page_size(9999) == 1000


def test_bp_bounded_page_size_clamps_low():
    # 0 is falsy → int(0 or 100) = 100, then clamped to [1, 1000] = 100
    assert BP._bounded_page_size(0) == 100


def test_bp_bounded_page_size_default_none():
    assert BP._bounded_page_size(None) == 100


# ─── business_person — _with_query ───────────────────────────────────────────

def test_bp_with_query_adds_param():
    url = BP._with_query("https://example.com/", foo="bar")
    assert "foo=bar" in url


def test_bp_with_query_preserves_path():
    url = BP._with_query("https://example.com/path", key="val")
    assert "/path" in url


def test_bp_with_query_skips_none():
    url = BP._with_query("https://example.com/", key=None)
    assert "key" not in url


def test_bp_with_query_skips_empty_string():
    url = BP._with_query("https://example.com/", key="")
    assert "key" not in url
