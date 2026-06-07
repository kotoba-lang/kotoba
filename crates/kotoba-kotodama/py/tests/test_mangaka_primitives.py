"""Tests for mangaka primitives (ComfyUI panel render + Pillow compose pipeline)."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path as _P

_py_src = _P(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import mangaka as MK  # noqa: E402


# ─── _build_workflow (pure) ──────────────────────────────────────────────────

def test_build_workflow_has_required_node_types():
    wf = MK._build_workflow(
        prompt="anime girl reading", negative="blurry", seed=42,
        fname="test-001", checkpoint="model.safetensors",
    )
    class_types = {v["class_type"] for v in wf["prompt"].values()}
    assert "KSampler" in class_types
    assert "CheckpointLoaderSimple" in class_types
    assert "CLIPTextEncode" in class_types
    assert "SaveImage" in class_types


def test_build_workflow_uses_provided_prompt():
    wf = MK._build_workflow(
        prompt="cherry blossom landscape",
        negative=MK.NEG_PROMPT,
        seed=1,
        fname="panel-001",
        checkpoint=MK.DEFAULT_CHECKPOINT,
    )
    clip_nodes = [v for v in wf["prompt"].values() if v["class_type"] == "CLIPTextEncode"]
    prompts = [n["inputs"]["text"] for n in clip_nodes]
    assert "cherry blossom landscape" in prompts


def test_build_workflow_uses_provided_seed():
    wf = MK._build_workflow("test", "neg", 9999, "fname", "ckpt.safetensors")
    sampler = next(v for v in wf["prompt"].values() if v["class_type"] == "KSampler")
    assert sampler["inputs"]["seed"] == 9999


def test_build_workflow_filename_in_save_node():
    wf = MK._build_workflow("test", "neg", 1, "my-panel-001", "ckpt.safetensors")
    save_node = next(v for v in wf["prompt"].values() if v["class_type"] == "SaveImage")
    assert save_node["inputs"]["filename_prefix"] == "my-panel-001"


def test_build_workflow_uses_panel_dimensions():
    wf = MK._build_workflow("test", "neg", 1, "f", "ckpt.safetensors")
    latent = next(v for v in wf["prompt"].values() if v["class_type"] == "EmptyLatentImage")
    assert latent["inputs"]["width"] == MK.PANEL_W
    assert latent["inputs"]["height"] == MK.PANEL_H


# ─── task_batch_render (early-exit paths, no HTTP) ───────────────────────────

def test_batch_render_no_script_returns_error():
    result = asyncio.run(MK.task_batch_render(script=None))
    assert result["status"] == "error"
    assert "script" in result.get("error", "").lower()


def test_batch_render_non_dict_script_returns_error():
    result = asyncio.run(MK.task_batch_render(script="not-a-dict"))
    assert result["status"] == "error"


def test_batch_render_empty_pages_returns_error():
    result = asyncio.run(MK.task_batch_render(script={"pages": []}))
    assert result["status"] == "error"
    assert "panel" in result.get("error", "").lower()


# ─── task_batch_overlay (early-exit paths, no HTTP) ──────────────────────────

def test_batch_overlay_no_args_returns_error():
    result = asyncio.run(MK.task_batch_overlay())
    assert result["status"] == "error"


def test_batch_overlay_script_without_panels_returns_error():
    result = asyncio.run(MK.task_batch_overlay(script={"pages": []}, panelBlobKeys=None))
    assert result["status"] == "error"


# ─── task_batch_compose (early-exit paths, no HTTP) ──────────────────────────

def test_batch_compose_no_args_returns_error():
    result = asyncio.run(MK.task_batch_compose())
    assert result["status"] == "error"


def test_batch_compose_no_overlay_keys_returns_error():
    result = asyncio.run(MK.task_batch_compose(script={"pages": []}, overlayBlobKeys=None))
    assert result["status"] == "error"


# ─── task_batch_insert_pages (no RW_URL → skips DB) ─────────────────────────

def test_batch_insert_pages_no_script_returns_error():
    result = asyncio.run(MK.task_batch_insert_pages(charSlug="testchar", script=None))
    assert result["status"] == "error"


def test_batch_insert_pages_skips_db_when_rw_url_missing(monkeypatch):
    monkeypatch.setattr(MK, "RW_URL", "")
    script = {"title": "Test Episode", "pages": [{"act": "act1", "panels": []}]}
    result = asyncio.run(MK.task_batch_insert_pages(
        charSlug="hero",
        script=script,
        pageBlobKeys=["cid001", "cid002"],
    ))
    assert result["status"] == "ok-skipped-db"
    assert result["workVertexId"].startswith("at://")
    assert len(result["pageVertexIds"]) == 2


# ─── task_post_publish (early-exit paths) ────────────────────────────────────

def test_post_publish_no_work_uri_returns_error():
    result = asyncio.run(MK.task_post_publish(pageBlobKeys=["cid001"]))
    assert result["status"] == "error"


def test_post_publish_no_page_blobs_returns_error():
    result = asyncio.run(MK.task_post_publish(workUri="at://mangaka.etzhayyim.com/work/rk1"))
    assert result["status"] == "error"


# ─── register ────────────────────────────────────────────────────────────────

def test_register_exposes_five_tasks():
    registered = []

    class FakeWorker:
        def task(self, *, task_type, single_value, timeout_ms):
            registered.append(task_type)
            def deco(fn): return fn
            return deco

    MK.register(FakeWorker(), timeout_ms=600_000)
    assert set(registered) == {
        "mangaka.panel.batchRender",
        "mangaka.balloon.batchOverlay",
        "mangaka.page.batchCompose",
        "mangaka.records.batchInsertPages",
        "mangaka.post.publish",
    }
