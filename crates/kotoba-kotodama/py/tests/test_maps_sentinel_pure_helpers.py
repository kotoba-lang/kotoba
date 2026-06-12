"""Pure helper tests for maps_sentinel primitives.

Covers pure functions with no DB/HTTP/RunPod dependencies:
- _now_iso / _now_ms / _new_rkey
- _build_datetime_range
- _parse_aoi / _resolve_aois
- _stage1_build_input / _stage3_parse_output
- _VALID_ANALYSIS_TYPES / _BOOTSTRAP_AOIS constants
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import maps_sentinel as MS


# ─── _now_iso ─────────────────────────────────────────────────────────────────

def test_ms_now_iso_returns_string():
    assert isinstance(MS._now_iso(), str)


def test_ms_now_iso_ends_with_z():
    assert MS._now_iso().endswith("Z")


def test_ms_now_iso_contains_t():
    assert "T" in MS._now_iso()


# ─── _now_ms ──────────────────────────────────────────────────────────────────

def test_ms_now_ms_returns_int():
    assert isinstance(MS._now_ms(), int)


def test_ms_now_ms_is_positive():
    assert MS._now_ms() > 0


def test_ms_now_ms_is_recent():
    # Should be after Jan 2023 in epoch ms
    assert MS._now_ms() > 1_700_000_000_000


# ─── _new_rkey ────────────────────────────────────────────────────────────────

def test_ms_new_rkey_starts_with_prefix():
    result = MS._new_rkey("sentinel")
    assert result.startswith("sentinel-")


def test_ms_new_rkey_returns_string():
    assert isinstance(MS._new_rkey("pfx"), str)


def test_ms_new_rkey_is_unique():
    a = MS._new_rkey("x")
    b = MS._new_rkey("x")
    assert a != b


# ─── _build_datetime_range ────────────────────────────────────────────────────

def test_ms_build_datetime_range_returns_string():
    result = MS._build_datetime_range(7)
    assert isinstance(result, str)


def test_ms_build_datetime_range_has_slash():
    result = MS._build_datetime_range(7)
    assert "/" in result


def test_ms_build_datetime_range_both_parts_end_with_z():
    result = MS._build_datetime_range(7)
    start, end = result.split("/")
    assert start.endswith("Z")
    assert end.endswith("Z")


def test_ms_build_datetime_range_clamps_to_1_day_minimum():
    result = MS._build_datetime_range(0)
    assert "/" in result


def test_ms_build_datetime_range_clamps_to_365_days_max():
    result = MS._build_datetime_range(9999)
    assert "/" in result


# ─── _parse_aoi ───────────────────────────────────────────────────────────────

def test_ms_parse_aoi_valid_dict():
    spec = {"name": "tokyo", "bbox": [139.5, 35.3, 139.95, 35.7]}
    result = MS._parse_aoi(spec)
    assert result["name"] == "tokyo"
    assert len(result["bbox"]) == 4


def test_ms_parse_aoi_bbox_values_are_floats():
    spec = {"name": "test", "bbox": [0, 0, 1, 1]}
    result = MS._parse_aoi(spec)
    for v in result["bbox"]:
        assert isinstance(v, float)


def test_ms_parse_aoi_raises_on_non_dict():
    with pytest.raises(ValueError, match="dict"):
        MS._parse_aoi("not a dict")


def test_ms_parse_aoi_raises_on_missing_bbox():
    with pytest.raises(ValueError, match="bbox"):
        MS._parse_aoi({"name": "test"})


def test_ms_parse_aoi_raises_on_wrong_bbox_length():
    with pytest.raises(ValueError, match="bbox"):
        MS._parse_aoi({"name": "test", "bbox": [0, 0, 1]})


def test_ms_parse_aoi_raises_on_minlon_gte_maxlon():
    with pytest.raises(ValueError, match="longitude"):
        MS._parse_aoi({"name": "test", "bbox": [1.0, 0.0, 0.0, 1.0]})


def test_ms_parse_aoi_raises_on_minlat_gte_maxlat():
    with pytest.raises(ValueError, match="latitude"):
        MS._parse_aoi({"name": "test", "bbox": [0.0, 1.0, 1.0, 0.0]})


# ─── _resolve_aois ────────────────────────────────────────────────────────────

def test_ms_resolve_aois_no_override_returns_bootstrap():
    result = MS._resolve_aois(None)
    assert isinstance(result, list)
    assert len(result) > 0


def test_ms_resolve_aois_with_override():
    override = [{"name": "custom", "bbox": [0.0, 0.0, 1.0, 1.0]}]
    result = MS._resolve_aois(override)
    assert len(result) == 1
    assert result[0]["name"] == "custom"


def test_ms_resolve_aois_skips_invalid():
    override = [
        {"name": "valid", "bbox": [0.0, 0.0, 1.0, 1.0]},
        {"name": "bad", "bbox": [1.0, 0.0, 0.0, 1.0]},  # invalid lon
    ]
    result = MS._resolve_aois(override)
    assert len(result) == 1
    assert result[0]["name"] == "valid"


def test_ms_resolve_aois_empty_override():
    result = MS._resolve_aois([])
    assert result == []


# ─── _stage1_build_input ──────────────────────────────────────────────────────

def test_ms_stage1_build_input_valid_type_unchanged():
    for atype in MS._VALID_ANALYSIS_TYPES:
        result = MS._stage1_build_input({"analysis_type": atype})
        assert result["analysis_type"] == atype


def test_ms_stage1_build_input_unknown_type_falls_back():
    result = MS._stage1_build_input({"analysis_type": "unknown_xyz"})
    assert result["analysis_type"] == "change_detection"


def test_ms_stage1_build_input_empty_string_falls_back():
    result = MS._stage1_build_input({"analysis_type": ""})
    assert result["analysis_type"] == "change_detection"


def test_ms_stage1_build_input_preserves_other_keys():
    result = MS._stage1_build_input({"analysis_type": "land_use", "scene_uri": "at://foo/bar"})
    assert result["scene_uri"] == "at://foo/bar"


# ─── _stage3_parse_output ─────────────────────────────────────────────────────

def test_ms_stage3_parse_output_adds_ok_true():
    result = MS._stage3_parse_output({"confidence": 0.7})
    assert result["ok"] is True


def test_ms_stage3_parse_output_clamps_high_confidence():
    result = MS._stage3_parse_output({"confidence": 1.5})
    assert result["confidence"] == 1.0


def test_ms_stage3_parse_output_clamps_negative_confidence():
    result = MS._stage3_parse_output({"confidence": -0.5})
    assert result["confidence"] == 0.0


def test_ms_stage3_parse_output_phase1_caps_at_085():
    result = MS._stage3_parse_output({"confidence": 0.9, "model_version": "phase1"})
    assert result["confidence"] == 0.85


def test_ms_stage3_parse_output_adds_empty_summary_if_missing():
    result = MS._stage3_parse_output({"confidence": 0.5})
    assert "summary" in result


def test_ms_stage3_parse_output_preserves_existing_summary():
    result = MS._stage3_parse_output({"confidence": 0.5, "summary": "Found changes"})
    assert result["summary"] == "Found changes"


def test_ms_stage3_parse_output_invalid_confidence_becomes_zero():
    result = MS._stage3_parse_output({"confidence": "bad"})
    assert result["confidence"] == 0.0


# ─── constants ────────────────────────────────────────────────────────────────

def test_ms_valid_analysis_types_is_set():
    assert isinstance(MS._VALID_ANALYSIS_TYPES, set)


def test_ms_valid_analysis_types_not_empty():
    assert len(MS._VALID_ANALYSIS_TYPES) > 0


def test_ms_valid_analysis_types_contains_change_detection():
    assert "change_detection" in MS._VALID_ANALYSIS_TYPES


def test_ms_bootstrap_aois_is_list():
    assert isinstance(MS._BOOTSTRAP_AOIS, list)


def test_ms_bootstrap_aois_not_empty():
    assert len(MS._BOOTSTRAP_AOIS) > 0


def test_ms_bootstrap_aois_have_bbox():
    for aoi in MS._BOOTSTRAP_AOIS:
        assert "bbox" in aoi
        assert len(aoi["bbox"]) == 4


def test_ms_bootstrap_aois_have_name():
    for aoi in MS._BOOTSTRAP_AOIS:
        assert "name" in aoi
        assert isinstance(aoi["name"], str)
