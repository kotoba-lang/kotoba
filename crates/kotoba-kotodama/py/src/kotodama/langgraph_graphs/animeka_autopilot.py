"""
animeka.autopilot — LangGraph StateGraph port (ADR-2605080600 Phase 5).

Replaces the Zeebe timer-start BPMN `animeka_autopilot` (R/PT15M).
Triggered by K8s CronJob (every 15 minutes) via POST /runs.

Graph:
  START → generate_scene_text → generate_storyboard
         → [sbCid?] → generate_storyboard_retry (if blank)
         → generate_layout → generate_keyframe → generate_background
         → compose_post → emit_audit → END

State:
  cutId             str   unique cut identifier (auto-{ts})
  sceneText         str   LLM-generated scene description for misaki
  visualPrompt      str   storyboard visual prompt from LLM
  sbCid             str   storyboard blob CID
  lyCid             str   layout blob CID
  kfCid             str   keyframe blob CID
  bgCid             str   background blob CID
  bgPrompt          str   background prompt from LLM
  layoutBgMood      str   bgMood extracted from layout plan JSON
  postStatus        str   "posted" | "skipped" | "error"
  ok                bool  overall success flag
  error             str   error message if ok=False
"""

from __future__ import annotations

import asyncio
import time as _time
from datetime import datetime, timezone
from typing import TypedDict

# ---------------------------------------------------------------------------
# State
# ---------------------------------------------------------------------------

_CHARACTER_DESC = "misaki: high-school girl, navy blazer, dark long hair, introspective"
_ACTOR_DID = "did:web:animeka.etzhayyim.com"
_REPO = "did:web:an1m3k4x.etzhayyim.com"
# Match the working shinshi ckpt name. ComfyUI rejects bare "animagine-xl-4"
# (no .safetensors suffix); the OpenAI-compat shim path `/v1/images/generations`
# does not exist on this pod, so we render via native `/prompt` workflow.
_CKPT = "animagine-xl-4.0.safetensors"


async def _render_and_upload(prompt: str, width: int, height: int, steps: int) -> tuple[str, str]:
    """ComfyUI native /prompt workflow + PDS uploadBlob. Returns
    (blob_cid_link_or_empty, error_or_empty). Mirrors shinshi_image's
    working render path (replaces the broken `task_generic_comfyui_call`
    OpenAI-compat shim that returned 405 on every call → empty CIDs)."""
    from kotodama.primitives.shinshi_image import (
        _build_anime_workflow,
        _comfy_render_png,
        _upload_blob_to_pds,
    )
    workflow = _build_anime_workflow(prompt, _CKPT, width, height, steps)
    png, err = await _comfy_render_png(workflow)
    if not png:
        return "", f"render-failed:{err}"
    blob_cid = await _upload_blob_to_pds(png, _REPO)
    if not blob_cid:
        return "", "blob-upload-failed"
    return blob_cid, ""


def _envelope_content(state: dict, envelope_key: str, legacy_key: str) -> str:
    """Phase E3: extract content from {envelope_key}.result.content (when the
    upstream node is mcp_tool com.etzhayyim.tools.llm.chat) and fall back to
    state.<legacy_key> if the envelope is absent (v1 path / direct unit
    test seeding). Returns '' if neither is set."""
    env = state.get(envelope_key)
    if isinstance(env, dict):
        r = env.get("result")
        if isinstance(r, dict):
            c = r.get("content")
            if isinstance(c, str) and c:
                return c
    legacy = state.get(legacy_key)
    return legacy if isinstance(legacy, str) else ""


class AnimakaAutopilotState(TypedDict, total=False):
    cutId: str
    sceneText: str
    visualPrompt: str
    sbCid: str
    lyCid: str
    kfCid: str
    bgCid: str
    bgPrompt: str
    layoutBgMood: str
    postStatus: str
    ok: bool
    error: str | None


# ---------------------------------------------------------------------------
# Nodes
# ---------------------------------------------------------------------------

def generate_scene_text(state: AnimakaAutopilotState) -> dict:
    """LLM generates a fresh scene description for misaki (R/PT15M autopilot)."""
    from kotodama.zeebe_worker_main import task_generic_llm_chat

    cut_id = f"auto-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"

    system = (
        "You are an anime scene writer. Write SHORT (1-3 sentence) evocative "
        "scene descriptions for an anime short starring Misaki — a thoughtful "
        "high-school girl in a navy blazer with long dark hair. Vary the mood: "
        "calm mornings, wistful afternoons, introspective evenings. "
        "Output only the scene description, no preamble."
    )
    try:
        result = asyncio.run(task_generic_llm_chat(
            tier="deep",
            system=system,
            user="Generate a fresh scene now.",
            maxTokens=400,
            temperature=0.85,
        ))
        scene_text = result.get("content", "").strip() or "Misaki stands quietly by the window, watching the world outside."
        return {"cutId": cut_id, "sceneText": scene_text}
    except Exception as e:
        fallback_scene = "Misaki stands quietly by the window, watching the world outside."
        return {"cutId": cut_id, "sceneText": fallback_scene, "error": str(e)}


def generate_storyboard(state: AnimakaAutopilotState) -> dict:
    """LLM storyboard prompt → ComfyUI 512×512 → DB insert (candidateNum=1)."""
    from kotodama.zeebe_worker_main import (
        task_generic_llm_chat,
        task_generic_db_insert,
    )

    cut_id = state.get("cutId", f"auto-{int(_time.time() * 1000)}")
    cut_summary = _envelope_content(state, "sceneTextLlmOut", "sceneText")

    system = (
        "You are a storyboard artist for a moody anime short. "
        "Given a scene description and character list, output a SINGLE concise "
        "visual prompt (max 80 words) for a monochrome storyboard sketch. "
        "Describe composition, camera angle, and character pose. No dialogue."
    )
    user = (
        f"Cut: {cut_summary}\n"
        f"Characters: {_CHARACTER_DESC}\n"
        "Candidate variant: 1"
    )

    try:
        llm_result = asyncio.run(task_generic_llm_chat(
            tier="deep", system=system, user=user,
            maxTokens=400, temperature=0.7,
        ))
        visual_prompt = llm_result.get("content", "").strip()
    except Exception as e:
        return {"sbCid": "", "visualPrompt": "", "error": str(e)}

    full_prompt = visual_prompt + ", storyboard sketch, monochrome pencil lineart, loose confident strokes, story panel"
    sb_cid, err = asyncio.run(_render_and_upload(full_prompt, 512, 512, 22))
    if err:
        return {"sbCid": "", "visualPrompt": visual_prompt, "error": err}

    if sb_cid:
        try:
            asyncio.run(task_generic_db_insert(
                table="vertex_animeka",
                values={
                    "vertex_id": f"at://{_REPO}/com.etzhayyim.apps.animeka.storyboard/{cut_id}-c1",
                    "repo": _REPO,
                    "collection": "com.etzhayyim.apps.animeka.storyboard",
                    "rkey": f"{cut_id}-c1",
                    "blob_cid": sb_cid,
                    "cut_summary": cut_summary,
                    "candidate_num": 1,
                    "ts_ms": int(_time.time() * 1000),
                },
            ))
        except Exception:
            pass

    # Phase D2 (ADR-2605082000): embed routing decision so the topology uses
    # field-based conditional edges, retiring _route_after_storyboard.
    return {
        "sbCid": sb_cid,
        "visualPrompt": visual_prompt,
        "nextRoute": "generate_storyboard_retry" if not sb_cid else "generate_layout",
    }


def generate_storyboard_retry(state: AnimakaAutopilotState) -> dict:
    """Retry storyboard with candidateNum=2 when first attempt returned empty CID."""
    from kotodama.zeebe_worker_main import (
        task_generic_llm_chat,
        task_generic_db_insert,
    )

    cut_id = state.get("cutId", f"auto-{int(_time.time() * 1000)}")
    cut_summary = _envelope_content(state, "sceneTextLlmOut", "sceneText")

    system = (
        "You are a storyboard artist for a moody anime short. "
        "Given a scene description and character list, output a SINGLE concise "
        "visual prompt (max 80 words) for a monochrome storyboard sketch. "
        "Describe composition, camera angle, and character pose. No dialogue."
    )
    user = (
        f"Cut: {cut_summary}\n"
        f"Characters: {_CHARACTER_DESC}\n"
        "Candidate variant: 2"
    )

    try:
        llm_result = asyncio.run(task_generic_llm_chat(
            tier="deep", system=system, user=user,
            maxTokens=400, temperature=0.7,
        ))
        visual_prompt = llm_result.get("content", "").strip()
    except Exception as e:
        return {"sbCid": "", "visualPrompt": "", "error": str(e)}

    full_prompt = visual_prompt + ", storyboard sketch, monochrome pencil lineart, loose confident strokes, story panel"
    sb_cid, err = asyncio.run(_render_and_upload(full_prompt, 512, 512, 22))
    if err:
        return {"sbCid": "", "visualPrompt": visual_prompt, "error": err}

    if sb_cid:
        try:
            asyncio.run(task_generic_db_insert(
                table="vertex_animeka",
                values={
                    "vertex_id": f"at://{_REPO}/com.etzhayyim.apps.animeka.storyboard/{cut_id}-c2",
                    "repo": _REPO,
                    "collection": "com.etzhayyim.apps.animeka.storyboard",
                    "rkey": f"{cut_id}-c2",
                    "blob_cid": sb_cid,
                    "cut_summary": cut_summary,
                    "candidate_num": 2,
                    "ts_ms": int(_time.time() * 1000),
                },
            ))
        except Exception:
            pass

    return {"sbCid": sb_cid, "visualPrompt": visual_prompt}


def _route_after_storyboard(state: AnimakaAutopilotState) -> str:
    """Conditional: if sbCid is missing/empty, retry storyboard; else proceed."""
    return "generate_storyboard_retry" if not state.get("sbCid") else "generate_layout"


def generate_layout(state: AnimakaAutopilotState) -> dict:
    """LLM layout plan JSON → ComfyUI 1024×1024 production key drawing → DB insert."""
    from kotodama.zeebe_worker_main import (
        task_generic_llm_json,
        task_generic_db_insert,
    )

    cut_id = state.get("cutId", f"auto-{int(_time.time() * 1000)}")
    cut_summary = _envelope_content(state, "sceneTextLlmOut", "sceneText")
    visual_prompt = state.get("visualPrompt", "")

    system = (
        "You are an anime layout artist. Output ONE JSON object with these keys: "
        "prompt (string, positive ComfyUI prompt for the full-colour layout), "
        "negativePrompt (string), charPositions (string, brief description), "
        "bgMood (string, one phrase for the background atmosphere). "
        "No code fences, no preamble."
    )
    user = (
        f"Storyboard concept: {visual_prompt}\n"
        f"Scene: {cut_summary}\n"
        f"Characters: {_CHARACTER_DESC}"
    )

    layout_prompt = visual_prompt
    bg_mood = "soft warm morning light"

    try:
        json_result = asyncio.run(task_generic_llm_json(
            tier="classifier", system=system, user=user,
            maxTokens=900, temperature=0.3,
        ))
        if json_result.get("ok") and isinstance(json_result.get("data"), dict):
            plan = json_result["data"]
            layout_prompt = plan.get("prompt", visual_prompt)
            bg_mood = plan.get("bgMood", "soft warm morning light")
    except Exception:
        pass

    full_prompt = layout_prompt + ", anime layout paper, production key drawing, clean linework, flat colour"
    ly_cid, err = asyncio.run(_render_and_upload(full_prompt, 1024, 1024, 28))
    if err:
        return {"lyCid": "", "layoutBgMood": bg_mood, "error": err}

    if ly_cid:
        try:
            asyncio.run(task_generic_db_insert(
                table="vertex_animeka",
                values={
                    "vertex_id": f"at://{_REPO}/com.etzhayyim.apps.animeka.layout/{cut_id}",
                    "repo": _REPO,
                    "collection": "com.etzhayyim.apps.animeka.layout",
                    "rkey": cut_id,
                    "blob_cid": ly_cid,
                    "cut_summary": cut_summary,
                    "lighting_mood": bg_mood,
                    "ts_ms": int(_time.time() * 1000),
                },
            ))
        except Exception:
            pass

    return {"lyCid": ly_cid, "layoutBgMood": bg_mood}


def generate_keyframe(state: AnimakaAutopilotState) -> dict:
    """ComfyUI 1024×1024 keyframe → PDS uploadBlob → DB insert. ControlNet/
    IPAdapter dropped: not supported by `_build_anime_workflow` baseline.
    Re-add as a separate workflow once the working render path is verified."""
    from kotodama.zeebe_worker_main import task_generic_db_insert

    cut_id = state.get("cutId", f"auto-{int(_time.time() * 1000)}")
    visual_prompt = state.get("visualPrompt", "")
    cut_summary = _envelope_content(state, "sceneTextLlmOut", "sceneText")

    full_prompt = (
        visual_prompt
        + ", anime keyframe, clean lineart, flat cel shading, "
        "character on-model, expressive face, consistent design"
    )
    kf_cid, err = asyncio.run(_render_and_upload(full_prompt, 1024, 1024, 30))
    if err:
        return {"kfCid": "", "error": err}

    if kf_cid:
        try:
            asyncio.run(task_generic_db_insert(
                table="vertex_animeka",
                values={
                    "vertex_id": f"at://{_REPO}/com.etzhayyim.apps.animeka.keyframe/{cut_id}-f1",
                    "repo": _REPO,
                    "collection": "com.etzhayyim.apps.animeka.keyframe",
                    "rkey": f"{cut_id}-f1",
                    "blob_cid": kf_cid,
                    "cut_summary": cut_summary,
                    "frame_num": 1,
                    "ts_ms": int(_time.time() * 1000),
                },
            ))
        except Exception:
            pass

    return {"kfCid": kf_cid}


def generate_background(state: AnimakaAutopilotState) -> dict:
    """LLM bg prompt → ComfyUI flux.1-dev 1920×1080 background painting → DB insert."""
    from kotodama.zeebe_worker_main import (
        task_generic_llm_chat,
        task_generic_db_insert,
    )

    cut_id = state.get("cutId", f"auto-{int(_time.time() * 1000)}")
    cut_summary = _envelope_content(state, "sceneTextLlmOut", "sceneText")
    bg_mood = state.get("layoutBgMood", "soft warm morning light")

    system = (
        "You are an anime background artist. Output a SINGLE evocative environment "
        "description (max 60 words) for a widescreen background painting with "
        "NO characters. Focus on setting, lighting, and atmosphere."
    )
    user = (
        f"Scene: {cut_summary}\n"
        f"Location context: {cut_summary}\n"
        f"Time of day: early spring dawn\n"
        f"Lighting mood: {bg_mood}"
    )

    try:
        llm_result = asyncio.run(task_generic_llm_chat(
            tier="deep", system=system, user=user,
            maxTokens=350, temperature=0.6,
        ))
        bg_prompt = llm_result.get("content", "").strip() or f"anime background, {bg_mood}, early spring dawn, no characters"
    except Exception:
        bg_prompt = f"anime background, {bg_mood}, early spring dawn, no characters"

    # flux.1-dev requires a different ckpt + workflow. Use the working anime
    # SDXL workflow at widescreen dimensions for now; switch to a flux-specific
    # workflow once the baseline render path is verified producing blobs.
    full_prompt = bg_prompt + ", anime background painting, painterly, no characters, widescreen cinematic"
    bg_cid, err = asyncio.run(_render_and_upload(full_prompt, 1344, 768, 28))
    if err:
        return {"bgCid": "", "bgPrompt": bg_prompt, "error": err}

    if bg_cid:
        try:
            asyncio.run(task_generic_db_insert(
                table="vertex_animeka",
                values={
                    "vertex_id": f"at://{_REPO}/com.etzhayyim.apps.animeka.background/{cut_id}",
                    "repo": _REPO,
                    "collection": "com.etzhayyim.apps.animeka.background",
                    "rkey": cut_id,
                    "blob_cid": bg_cid,
                    "bg_cid": bg_cid,
                    "cut_summary": cut_summary,
                    "ts_ms": int(_time.time() * 1000),
                },
            ))
        except Exception:
            pass

    return {"bgCid": bg_cid, "bgPrompt": bg_prompt}


def compose_post(state: AnimakaAutopilotState) -> dict:
    """Build null-tolerant image list and dispatch social post via pds.dispatch."""
    from kotodama.zeebe_worker_main import task_generic_pds_dispatch

    cut_id = state.get("cutId", "")
    cut_summary = _envelope_content(state, "sceneTextLlmOut", "sceneText")

    # Null-tolerant image embed: flatten() — drop any None/empty CIDs.
    images = [
        cid for cid in [
            state.get("bgCid"),
            state.get("lyCid"),
            state.get("kfCid"),
            state.get("sbCid"),
        ]
        if cid
    ]

    post_text = f"✦ animeka autopilot — cut {cut_id}\n{cut_summary[:200]}"

    embed = {
        "$type": "app.bsky.embed.images",
        "images": [
            {"image": {"$type": "blob", "ref": {"$link": cid}, "mimeType": "image/png", "size": 0},
             "alt": f"animeka frame {i+1}"}
            for i, cid in enumerate(images[:4])
        ],
    } if images else None

    payload = {
        "repo": _REPO,
        "collection": "app.bsky.feed.post",
        "record": {
            "$type": "app.bsky.feed.post",
            "text": post_text,
            "createdAt": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            **({"embed": embed} if embed else {}),
        },
    }

    try:
        result = asyncio.run(task_generic_pds_dispatch(
            type="com.atproto.repo.createRecord",
            payload=payload,
        ))
        return {"postStatus": "posted", "ok": True}
    except Exception as e:
        return {"postStatus": "error", "ok": False, "error": str(e)}


def emit_audit(state: AnimakaAutopilotState) -> dict:
    """Write OCEL audit row for this autopilot run (non-fatal)."""
    from kotodama.zeebe_worker_main import task_generic_audit_emit

    try:
        asyncio.run(task_generic_audit_emit(
            actor=_ACTOR_DID,
            action="animeka.autopilot",
            payload={
                "cutId": state.get("cutId", ""),
                "sbCid": state.get("sbCid", ""),
                "lyCid": state.get("lyCid", ""),
                "kfCid": state.get("kfCid", ""),
                "bgCid": state.get("bgCid", ""),
                "postStatus": state.get("postStatus", ""),
                "ok": state.get("ok", True),
            },
        ))
    except Exception:
        pass
    return {}


# ---------------------------------------------------------------------------
# Graph factory
# ---------------------------------------------------------------------------

def build_graph():
    """Build and compile the animeka.autopilot StateGraph."""
    from langgraph.graph import END, StateGraph

    builder = StateGraph(AnimakaAutopilotState)

    builder.add_node("generate_scene_text", generate_scene_text)
    builder.add_node("generate_storyboard", generate_storyboard)
    builder.add_node("generate_storyboard_retry", generate_storyboard_retry)
    builder.add_node("generate_layout", generate_layout)
    builder.add_node("generate_keyframe", generate_keyframe)
    builder.add_node("generate_background", generate_background)
    builder.add_node("compose_post", compose_post)
    builder.add_node("emit_audit", emit_audit)

    builder.set_entry_point("generate_scene_text")
    builder.add_edge("generate_scene_text", "generate_storyboard")

    # Conditional: retry storyboard if sbCid is empty.
    builder.add_conditional_edges(
        "generate_storyboard",
        _route_after_storyboard,
        {
            "generate_storyboard_retry": "generate_storyboard_retry",
            "generate_layout": "generate_layout",
        },
    )
    builder.add_edge("generate_storyboard_retry", "generate_layout")

    builder.add_edge("generate_layout", "generate_keyframe")
    builder.add_edge("generate_keyframe", "generate_background")
    builder.add_edge("generate_background", "compose_post")
    builder.add_edge("compose_post", "emit_audit")
    builder.add_edge("emit_audit", END)

    return builder.compile()
