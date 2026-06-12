"""
shinshi.video.render — Wan 2.2 i2v video generation via ComfyUI + AT post.

Zeebe task inputs  : slug, actorDid, motionPrompt, length, width, height, fps
Zeebe task outputs : blobKey, postUri, renderMs

Flow:
  1. Build Wan 2.2 i2v ComfyUI workflow
  2. POST to RunPod Serverless /runsync (or /run + poll /status on cold start)
  3. Decode base64 video → upload to PDS as video/mp4 blob
  4. Write graph-visible AT post record (C-path, vertex_repo_record)
  5. Return blobKey (blob CID link), postUri (at:// URI), renderMs
"""

from __future__ import annotations

import json
import os
import time
import urllib.error as _u_err
import urllib.request as _u_req
from typing import Any

from kotodama.primitives.yoro_social import (
    build_repo_record,
    insert_social_post_record,
    utc_now_iso,
    _rkey,
)

_COMFYUI_BASE = os.environ.get("COMFYUI_URL", "https://comfyui.etzhayyim.com")
_COMFYUI_KEY = os.environ.get("COMFYUI_API_KEY", "")
_PDS_BASE = os.environ.get("PDS_URL", "https://atproto.etzhayyim.com")
_SHINSHI_DID = "did:web:sh1n5h1x.etzhayyim.com"

_VIDEO_RENDER_TIMEOUT_MS = 540_000  # 9 min
_VIDEO_RENDER_TIMEOUT_SEC = 540.0


def _build_wan_i2v_workflow(prompt: str, width: int, height: int, length: int, fps: int) -> dict:
    """ComfyUI workflow graph for Wan 2.2 image-to-video."""
    seed = int(time.time() * 1000) & 0xFFFFFFFF
    return {
        "1": {
            "class_type": "WanVideoModelLoader",
            "inputs": {"model": "wan2.2_i2v_480p_14B_fp8_e4m3fn.safetensors"},
        },
        "2": {
            "class_type": "WanVideoTextEncode",
            "inputs": {
                "positive_prompt": prompt or "cinematic motion, smooth camera",
                "negative_prompt": "static, blurry, low quality, watermark",
                "model": ["1", 0],
            },
        },
        "3": {
            "class_type": "WanVideoSampler",
            "inputs": {
                "width": width,
                "height": height,
                "num_frames": max(8, length),
                "fps": fps,
                "seed": seed,
                "steps": 30,
                "cfg": 6.0,
                "model": ["1", 0],
                "conditioning": ["2", 0],
            },
        },
        "4": {
            "class_type": "WanVideoDecode",
            "inputs": {"samples": ["3", 0], "model": ["1", 0]},
        },
        "5": {
            "class_type": "SaveVideo",
            "inputs": {"video": ["4", 0], "filename_prefix": "shinshi", "fps": fps},
        },
    }


def _extract_video_b64(output: Any) -> str:
    """Pull base64 video string from RunPod Serverless output."""
    if not isinstance(output, dict):
        return ""
    if isinstance(output.get("video"), str):
        return output["video"]
    vids = output.get("videos")
    if isinstance(vids, list) and vids:
        v = vids[0]
        if isinstance(v, dict):
            return str(v.get("data") or "")
        if isinstance(v, str):
            return v
    return ""


def _http_post(url: str, payload: bytes, headers: dict, timeout: float = 30.0) -> tuple[int, dict]:
    req = _u_req.Request(url, data=payload, headers=headers, method="POST")
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except _u_err.HTTPError as e:
        try:
            return e.code, json.loads(e.read().decode("utf-8"))
        except Exception:
            return e.code, {"error": str(e)}
    except Exception as e:  # noqa: BLE001
        return -1, {"error": f"transport: {e}"}


def _http_get(url: str, headers: dict, timeout: float = 30.0) -> tuple[int, dict]:
    req = _u_req.Request(url, headers=headers, method="GET")
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return -1, {"error": str(e)}


async def task_shinshi_video_render(
    slug: str = "",
    actorDid: str = "",
    motionPrompt: str = "",
    length: int = 25,
    width: int = 832,
    height: int = 480,
    fps: int = 16,
) -> dict[str, Any]:
    """Render a Wan 2.2 i2v video via ComfyUI and publish as an AT post."""
    import asyncio
    import base64 as _b64

    started = time.monotonic()
    repo = actorDid or _SHINSHI_DID
    w = max(64, int(width or 832))
    h = max(64, int(height or 480))
    n_frames = max(8, int(length or 25))
    n_fps = max(1, int(fps or 16))

    workflow = _build_wan_i2v_workflow(
        prompt=str(motionPrompt or "cinematic motion")[:1000],
        width=w, height=h, length=n_frames, fps=n_fps,
    )
    base = _COMFYUI_BASE.rstrip("/")
    auth_headers = {"Authorization": f"Bearer {_COMFYUI_KEY}"}
    payload_bytes = json.dumps({"input": {"workflow": workflow}}).encode("utf-8")
    post_headers = {**auth_headers, "Content-Type": "application/json"}

    # Submit to RunPod Serverless
    status, data = await asyncio.to_thread(
        _http_post, f"{base}/runsync", payload_bytes, post_headers, 30.0
    )

    video_b64 = _extract_video_b64(data.get("output") if isinstance(data, dict) else {})

    # Cold-start polling
    if not video_b64 and isinstance(data, dict) and data.get("status") in ("IN_QUEUE", "IN_PROGRESS"):
        job_id = data.get("id", "")
        if not job_id:
            return {
                "blobKey": "", "postUri": "", "renderMs": int((time.monotonic() - started) * 1000),
                "error": "no job id in runsync response",
            }
        deadline = started + _VIDEO_RENDER_TIMEOUT_SEC
        status_url = f"{base}/status/{job_id}"
        while time.monotonic() < deadline:
            await asyncio.sleep(10)
            _, d = await asyncio.to_thread(_http_get, status_url, auth_headers, 30.0)
            if not isinstance(d, dict):
                continue
            s = d.get("status")
            if s == "COMPLETED":
                video_b64 = _extract_video_b64(d.get("output"))
                break
            if s == "FAILED":
                return {
                    "blobKey": "", "postUri": "", "renderMs": int((time.monotonic() - started) * 1000),
                    "error": f"render failed: {json.dumps(d)[:300]}",
                }

    render_ms = int((time.monotonic() - started) * 1000)

    if not video_b64:
        err = (data.get("error") or data) if isinstance(data, dict) else data
        return {
            "blobKey": "", "postUri": "", "renderMs": render_ms,
            "error": f"no video output: {json.dumps(err)[:300]}",
        }

    if video_b64.startswith("data:"):
        _, _, video_b64 = video_b64.partition(",")
    try:
        raw = _b64.b64decode(video_b64)
    except Exception as e:  # noqa: BLE001
        return {"blobKey": "", "postUri": "", "renderMs": render_ms, "error": f"b64 decode: {e}"}

    # Upload blob to PDS
    upload_url = f"{_PDS_BASE}/xrpc/com.atproto.repo.uploadBlob"
    up_headers = {
        "Content-Type": "video/mp4",
        "x-kotoba-kotodama-verified": "true",
        "x-kotoba-kotodama-repo": repo,
    }
    up_status, up_body = await asyncio.to_thread(
        _http_post, upload_url, raw, up_headers, 120.0
    )

    blob_cid = ""
    if isinstance(up_body, dict):
        blob = up_body.get("blob") or {}
        if isinstance(blob, dict):
            ref = blob.get("ref") or {}
            if isinstance(ref, dict):
                blob_cid = str(ref.get("$link") or "")

    if not blob_cid:
        return {
            "blobKey": "", "postUri": "", "renderMs": render_ms,
            "error": f"blob upload failed: {up_status} {json.dumps(up_body)[:200]}",
        }

    # Build AT post with video embed (graph-visible C-path)
    created_at = utc_now_iso()
    rkey = _rkey("shinshi-video")
    uri = f"at://{repo}/app.bsky.feed.post/{rkey}"
    video_ref = {
        "$type": "blob",
        "ref": {"$link": blob_cid},
        "mimeType": "video/mp4",
        "size": len(raw),
    }
    tag = (slug or "shinshi")[:24]
    text = f"#{tag} {str(motionPrompt or '')[:80]}"
    record = {
        "$type": "app.bsky.feed.post",
        "text": text,
        "embed": {
            "$type": "app.bsky.embed.video",
            "video": video_ref,
            "alt": str(motionPrompt or "")[:300],
        },
        "createdAt": created_at,
    }
    row = build_repo_record(
        repo=repo,
        collection="app.bsky.feed.post",
        record=record,
        created_at=created_at,
        rkey=rkey,
        actor_path="shinshi-video",
    )
    await asyncio.to_thread(insert_social_post_record, row, flush=False)

    return {"blobKey": blob_cid, "postUri": uri, "renderMs": render_ms}


def register(worker: Any, timeout_ms: int = _VIDEO_RENDER_TIMEOUT_MS) -> None:
    worker.task(
        task_type="shinshi.video.render",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_shinshi_video_render)
