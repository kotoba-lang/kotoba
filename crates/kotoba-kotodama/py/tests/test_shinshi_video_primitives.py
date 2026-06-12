"""Tests for shinshi_video primitives (Wan 2.2 i2v helpers)."""

from __future__ import annotations

import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import shinshi_video as SV  # noqa: E402


# ─── _build_wan_i2v_workflow (pure) ──────────────────────────────────────

def test_workflow_has_required_node_types():
    wf = SV._build_wan_i2v_workflow(
        prompt="cinematic motion", width=832, height=480, length=25, fps=16,
    )
    class_types = {v["class_type"] for v in wf.values() if isinstance(v, dict)}
    assert "WanVideoModelLoader" in class_types
    assert "WanVideoTextEncode" in class_types
    assert "WanVideoSampler" in class_types
    assert "WanVideoDecode" in class_types
    assert "SaveVideo" in class_types


def test_workflow_uses_custom_prompt():
    wf = SV._build_wan_i2v_workflow(
        prompt="slow zoom on cherry blossoms", width=480, height=832, length=16, fps=8,
    )
    encode_node = next(
        v for v in wf.values() if isinstance(v, dict) and v.get("class_type") == "WanVideoTextEncode"
    )
    assert encode_node["inputs"]["positive_prompt"] == "slow zoom on cherry blossoms"


def test_workflow_sampler_respects_dimensions():
    wf = SV._build_wan_i2v_workflow(
        prompt="pan left", width=1280, height=720, length=32, fps=24,
    )
    sampler = next(
        v for v in wf.values() if isinstance(v, dict) and v.get("class_type") == "WanVideoSampler"
    )
    assert sampler["inputs"]["width"] == 1280
    assert sampler["inputs"]["height"] == 720
    assert sampler["inputs"]["fps"] == 24


def test_workflow_minimum_frames_clamped():
    wf = SV._build_wan_i2v_workflow(
        prompt="", width=832, height=480, length=2, fps=8,
    )
    sampler = next(
        v for v in wf.values() if isinstance(v, dict) and v.get("class_type") == "WanVideoSampler"
    )
    assert sampler["inputs"]["num_frames"] >= 8


# ─── _extract_video_b64 (pure) ───────────────────────────────────────────

def test_extract_video_b64_direct_video_key():
    assert SV._extract_video_b64({"video": "BASE64DATA"}) == "BASE64DATA"


def test_extract_video_b64_videos_list_dict():
    out = SV._extract_video_b64({"videos": [{"data": "B64"}]})
    assert out == "B64"


def test_extract_video_b64_videos_list_str():
    out = SV._extract_video_b64({"videos": ["STRDATA"]})
    assert out == "STRDATA"


def test_extract_video_b64_missing_returns_empty():
    assert SV._extract_video_b64({}) == ""
    assert SV._extract_video_b64({"other": "stuff"}) == ""


def test_extract_video_b64_non_dict_returns_empty():
    assert SV._extract_video_b64(None) == ""
    assert SV._extract_video_b64("not a dict") == ""
    assert SV._extract_video_b64([1, 2]) == ""


# ─── register ────────────────────────────────────────────────────────────

def test_register_exposes_one_task():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    SV.register(FakeWorker(), timeout_ms=60_000)
    assert registered == ["shinshi.video.render"]
