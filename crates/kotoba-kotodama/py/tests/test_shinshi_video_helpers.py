"""Tests for pure helper functions in shinshi_video.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import shinshi_video as SV


# ─── _build_wan_i2v_workflow ─────────────────────────────────────────────────

def test_build_wan_workflow_returns_dict() -> None:
    result = SV._build_wan_i2v_workflow("test prompt", 480, 832, 81, 16)
    assert isinstance(result, dict)
    assert len(result) > 0


def test_build_wan_workflow_has_required_nodes() -> None:
    result = SV._build_wan_i2v_workflow("prompt", 480, 832, 81, 16)
    # Must have loader, text encode, sampler, decode, save
    assert "1" in result
    assert "2" in result
    assert "3" in result
    assert "4" in result
    assert "5" in result


def test_build_wan_workflow_prompt_in_text_encode() -> None:
    result = SV._build_wan_i2v_workflow("my custom prompt", 480, 832, 81, 16)
    text_encode = result["2"]["inputs"]
    assert text_encode["positive_prompt"] == "my custom prompt"


def test_build_wan_workflow_empty_prompt_uses_default() -> None:
    result = SV._build_wan_i2v_workflow("", 480, 832, 81, 16)
    text_encode = result["2"]["inputs"]
    assert text_encode["positive_prompt"]  # non-empty default


def test_build_wan_workflow_dimensions_passed() -> None:
    result = SV._build_wan_i2v_workflow("p", 640, 960, 60, 24)
    sampler = result["3"]["inputs"]
    assert sampler["width"] == 640
    assert sampler["height"] == 960
    assert sampler["fps"] == 24


def test_build_wan_workflow_min_frames_is_8() -> None:
    result = SV._build_wan_i2v_workflow("p", 480, 832, 4, 16)  # length=4 < 8
    sampler = result["3"]["inputs"]
    assert sampler["num_frames"] >= 8


def test_build_wan_workflow_class_types_present() -> None:
    result = SV._build_wan_i2v_workflow("p", 480, 832, 81, 16)
    assert result["1"]["class_type"] == "WanVideoModelLoader"
    assert result["2"]["class_type"] == "WanVideoTextEncode"
    assert result["3"]["class_type"] == "WanVideoSampler"
    assert result["4"]["class_type"] == "WanVideoDecode"
    assert result["5"]["class_type"] == "SaveVideo"


# ─── _extract_video_b64 ──────────────────────────────────────────────────────

def test_extract_video_b64_from_video_key() -> None:
    output = {"video": "base64datahere"}
    assert SV._extract_video_b64(output) == "base64datahere"


def test_extract_video_b64_from_videos_list_dict() -> None:
    output = {"videos": [{"data": "b64content"}]}
    assert SV._extract_video_b64(output) == "b64content"


def test_extract_video_b64_from_videos_list_string() -> None:
    output = {"videos": ["b64string"]}
    assert SV._extract_video_b64(output) == "b64string"


def test_extract_video_b64_empty_videos_list() -> None:
    assert SV._extract_video_b64({"videos": []}) == ""


def test_extract_video_b64_non_dict_returns_empty() -> None:
    assert SV._extract_video_b64(None) == ""
    assert SV._extract_video_b64("string") == ""
    assert SV._extract_video_b64([]) == ""


def test_extract_video_b64_empty_dict_returns_empty() -> None:
    assert SV._extract_video_b64({}) == ""
