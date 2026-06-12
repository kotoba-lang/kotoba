"""Yukkuri video generation pipeline primitives.

Five LangServer task types backing the yukkuriCompose.bpmn pipeline:

  yukkuri.scene.persist     — persist project payload into typed vertex tables:
                               vertex_yukkuri_video,
                               vertex_yukkuri_scene, vertex_yukkuri_line.
  yukkuri.voice.synthesize  — Kokoro TTS via KOKORO_URL (OpenAI-compat /v1/audio/speech).
                               Stores audio in vertex_yukkuri_line.voice_blob_key.
  yukkuri.image.generate    — ComfyUI SDXL via COMFYUI_URL (/v1/images/generations).
                               Stores image URI in vertex_yukkuri_scene.background_asset_uri.
  yukkuri.video.assemble    — Build timeline from typed rows, set status=editready.
  yukkuri.critic.review     — QA gate (duration / line-count / expression),
                               set status=published or rejected.

ADR-0056 BPMN-as-actor.

Env vars:
  KOKORO_URL      OpenAI-compat TTS endpoint, e.g. http://kokoro-worker:8020
  COMFYUI_URL     ComfyUI gateway, e.g. https://comfyui.etzhayyim.com  (default)
  COMFYUI_API_KEY ComfyUI auth token (optional for internal gateway)
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import datetime as _dt
import json
import os
import time
import uuid
from typing import Any

from kotodama import llm as _llm
from kotodama.primitives.yoro_social import build_repo_record, insert_social_post_record

DEFAULT_REPO = "did:web:y5kk5r1x.etzhayyim.com"
COLLECTION_VIDEO = "com.etzhayyim.apps.yukkuri.video"
COLLECTION_SCENE = "com.etzhayyim.apps.yukkuri.scene"
COLLECTION_LINE = "com.etzhayyim.apps.yukkuri.line"
COLLECTION_ASSET = "com.etzhayyim.apps.yukkuri.asset"
COLLECTION_GENERATION = "com.etzhayyim.apps.yukkuri.generation"

PATH_SCRIPTWRITER = "did:web:yukkuri.etzhayyim.com:actor:scriptwriter"

_SCRIPT_SYSTEM = (
    "Output ONLY valid JSON. No preamble, no commentary, no code fences.\n"
    'Schema: {"title":string,"scenes":[{"idx":number,"summary":string,'
    '"lines":[{"speaker":"left"|"right","text":string,'
    '"emotion":"neutral"|"happy"|"surprised"|"thinking"}]}]}'
)


def _generate_script_from_llm(topic: str, language: str = "ja") -> list[dict]:
    """Call LLM via murakumo fleet (fast tier, 60s timeout) to generate a yukkuri script.

    Returns a list of scene dicts matching the Schema above, or [] on failure.
    Runs inside the Zeebe worker — no CF 25s XRPC constraint applies here.
    """
    user = (
        f"Generate a yukkuri commentary video script in {language}.\n"
        f"Topic: {topic}\n"
        "Rules: 4 scenes, 4-6 lines per scene alternating left/right speaker, "
        "concise text under 50 chars each. Output JSON only."
    )
    try:
        result = _llm.call_tier_json(
            "fast",
            system=_SCRIPT_SYSTEM,
            user=user,
            max_tokens=2000,
            temperature=0.7,
        )
        if result.get("ok") and isinstance(result.get("data"), dict):
            scenes = result["data"].get("scenes", [])
            if isinstance(scenes, list) and len(scenes) > 0:
                return scenes
    except Exception:
        pass
    return []


PATH_VOICE_LEFT = "did:web:yukkuri.etzhayyim.com:actor:voiceLeft"
PATH_VOICE_RIGHT = "did:web:yukkuri.etzhayyim.com:actor:voiceRight"
PATH_ILLUSTRATOR = "did:web:yukkuri.etzhayyim.com:actor:illustrator"
PATH_EDITOR = "did:web:yukkuri.etzhayyim.com:actor:editor"
PATH_CRITIC = "did:web:yukkuri.etzhayyim.com:actor:critic"


def _now_iso() -> str:
    return (
        _dt.datetime.now(tz=_dt.UTC)
        .replace(microsecond=0)
        .isoformat()
        .replace("+00:00", "Z")
    )


def _now_ms() -> int:
    return int(time.time() * 1000)


def _rkey(prefix: str) -> str:
    stamp = _dt.datetime.now(tz=_dt.UTC).strftime("%Y%m%d%H%M%S")
    return f"{prefix}-{stamp}-{uuid.uuid4().hex[:8]}"


def _uri_to_rkey(uri: str) -> str:
    """Extract rkey from AT URI  at://did.../collection/rkey."""
    parts = uri.rsplit("/", 1)
    return parts[-1] if len(parts) == 2 else uri


# ──────────────────────────────────────────────────────────────────────
# Task 1: yukkuri.scene.persist
# ──────────────────────────────────────────────────────────────────────

def task_yukkuri_scene_persist(
    video_uri: str = "",
    voice_left: str = "af_heart",
    voice_right: str = "am_puck",
    # Video metadata — passed from BPMN when CF Worker does not pre-write the DB record.
    # If the record already exists in vertex_yukkuri_video these are ignored.
    title_hint: str = "",
    topic_hint: str = "",
    language_hint: str = "ja",
    target_sec_hint: int = 120,
    resolution_hint: str = "1080p",
    fps_hint: int = 30,
    seed_hint: int = 0,
    project_id_hint: str = "",
) -> dict[str, Any]:
    """Project video record into typed vertex tables.

    Reads vertex_yukkuri_video; if the record is missing (CF Worker no longer
    pre-writes it), inserts it using the *_hint values from BPMN variables.
    Writes vertex_yukkuri_video + vertex_yukkuri_scene + vertex_yukkuri_line.
    Idempotent: re-running overwrites existing rows (RisingWave PK upsert).
    """
    if not video_uri:
        return {"ok": False, "error": "video_uri is required", "sceneCount": 0, "lineCount": 0}

    rkey = _uri_to_rkey(video_uri)
    created_at = _now_iso()

    title = ""
    topic = ""
    language = "ja"
    target_sec = 120
    resolution = "1080p"
    fps = 30
    status = "script"
    project_id = ""
    seed = 0
    script_source = ""
    scenes_json_str = "[]"
    scene_count_orig = 0
    line_count_orig = 0
    stored_voice_left = "af_heart"
    stored_voice_right = "am_puck"
    duration_sec_orig = 0.0

    if True:

        client = get_kotoba_client()
        _res = client.q(
            "SELECT title, topic, language, target_sec, resolution, fps, status, "
            "       project_id, seed, script_source, scenes_json, scene_count, line_count, "
            "       voice_left, voice_right, duration_sec "
            "FROM vertex_yukkuri_video WHERE vertex_id = %s LIMIT 1",
            (video_uri,),
        )
        row = (_res[0] if _res else None)
        if not row:
            # CF Worker simplified path: no pre-write. Insert initial record using hints.
            _title = title_hint or f"ゆっくり実況: {topic_hint[:48]}"
            _res = client.q(
                """
                INSERT INTO vertex_yukkuri_video (
                  vertex_id, owner_did, project_id, title, topic, status, language,
                  target_sec, resolution, fps, seed, voice_left, voice_right,
                  script_source, scenes_json, scene_count, line_count,
                  actor_did, org_did, sensitivity_ord, created_at
                ) VALUES (
                  %s, %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s, %s, %s,
                  %s, %s, %s, %s,
                  %s, %s, %s, %s
                )
                """,
                (
                    video_uri, DEFAULT_REPO, project_id_hint or f"proj-{rkey}",
                    _title, topic_hint, "queued", language_hint,
                    target_sec_hint, resolution_hint, fps_hint, seed_hint,
                    voice_left, voice_right,
                    "bpmn:pending", "[]", 0, 0,
                    DEFAULT_REPO, DEFAULT_REPO, 1, created_at,
                ),
            )
            title = _title
            topic = topic_hint
            language = language_hint
            target_sec = target_sec_hint
            resolution = resolution_hint
            fps = fps_hint
            seed = seed_hint
            project_id = project_id_hint
            stored_voice_left = voice_left
            stored_voice_right = voice_right
        else:
            # Fall back to *_hint when DB columns were clobbered to NULL by a prior
            # partial INSERT (assemble/critic PK upsert bug, now fixed).
            title = str(row[0] or "") or title_hint
            topic = str(row[1] or "") or topic_hint
            language = str(row[2] or "") or language_hint
            target_sec = int(row[3] or 0) or target_sec_hint
            resolution = str(row[4] or "") or resolution_hint
            fps = int(row[5] or 0) or fps_hint
            status = str(row[6] or "script")
            project_id = str(row[7] or "") or project_id_hint
            seed = int(row[8] or 0) or seed_hint
            script_source = str(row[9] or "")
            scenes_json_str = str(row[10] or "[]")
            scene_count_orig = int(row[11] or 0)
            line_count_orig = int(row[12] or 0)
            stored_voice_left = str(row[13] or "af_heart")
            stored_voice_right = str(row[14] or "am_puck")
            duration_sec_orig = float(row[15] or 0.0)

    try:
        scenes: list[dict[str, Any]] = json.loads(scenes_json_str)
    except (json.JSONDecodeError, TypeError):
        scenes = []

    # If the CF Worker queued the video without a pre-generated script (status="queued"
    # or scenes_json="[]"), generate the script now via the murakumo LLM fleet.
    # This runs inside the Zeebe worker — no CF 25s XRPC timeout constraint applies.
    if not scenes and topic:
        generated = _generate_script_from_llm(topic, language)
        if generated:
            scenes = generated
            # Normalise scene dicts (add durationSec, voicePreset etc. for each line)
            dur_each = max(8, round(target_sec / max(1, len(scenes))))
            vl_pre = voice_left or stored_voice_left
            vr_pre = voice_right or stored_voice_right
            normalised: list[dict[str, Any]] = []
            for si, sc in enumerate(scenes):
                idx = int(sc.get("idx", si))
                lines_out = []
                for li, ln in enumerate(sc.get("lines") or []):
                    spk = str(ln.get("speaker") or "left")
                    lines_out.append({
                        "idx": li,
                        "speaker": spk,
                        "text": str(ln.get("text") or "")[:400],
                        "emotion": str(ln.get("emotion") or "neutral"),
                        "voicePreset": vr_pre if spk == "right" else vl_pre,
                        "voicedBy": PATH_VOICE_RIGHT if spk == "right" else PATH_VOICE_LEFT,
                    })
                normalised.append({
                    "idx": idx,
                    "summary": str(sc.get("summary") or ""),
                    "durationSec": dur_each,
                    "lines": lines_out,
                })
            scenes_json_str = json.dumps(normalised)
            scenes = normalised
            scene_count_orig = len(scenes)
            line_count_orig = sum(len(s.get("lines", [])) for s in scenes)
            script_source = "oss-llm:fast"
            status = "script"

    # Normalise voice presets: use values from BPMN input if provided,
    # else fall back to what the CF Worker recorded.
    vl = voice_left or stored_voice_left
    vr = voice_right or stored_voice_right

    # Write vertex_yukkuri_video row.
    _upsert_video(
        vertex_id=video_uri,
        owner_did=DEFAULT_REPO,
        project_id=project_id,
        title=title,
        topic=topic,
        language=language,
        target_sec=target_sec,
        resolution=resolution,
        fps=fps,
        status=status,
        seed=seed,
        scenes_json=scenes_json_str,
        scene_count=scene_count_orig or len(scenes),
        line_count=line_count_orig,
        voice_left=vl,
        voice_right=vr,
        script_source=script_source,
        created_at=created_at,
        duration_sec=duration_sec_orig,
    )

    # Write vertex_yukkuri_scene + vertex_yukkuri_line rows.
    scene_count = 0
    line_count = 0
    for sc in scenes:
        si = int(sc.get("idx", scene_count))
        scene_uri = f"at://{DEFAULT_REPO}/{COLLECTION_SCENE}/{rkey}-s{si:03d}"
        dur_sec = float(sc.get("durationSec") or 0)
        _upsert_scene(
            vertex_id=scene_uri,
            owner_did=DEFAULT_REPO,
            video_uri=video_uri,
            idx=si,
            duration_sec=dur_sec,
            summary=str(sc.get("summary") or ""),
            created_at=created_at,
        )
        scene_count += 1

        for li, ln in enumerate(sc.get("lines") or []):
            speaker = str(ln.get("speaker") or "left")
            line_uri = f"at://{DEFAULT_REPO}/{COLLECTION_LINE}/{rkey}-s{si:03d}-l{li:03d}"
            preset = vr if speaker == "right" else vl
            _upsert_line(
                vertex_id=line_uri,
                owner_did=DEFAULT_REPO,
                video_uri=video_uri,
                scene_uri=scene_uri,
                idx=li,
                speaker=speaker,
                text=str(ln.get("text") or ""),
                emotion=str(ln.get("emotion") or "neutral"),
                voice_preset=preset,
                created_at=created_at,
            )
            line_count += 1

    return {"ok": True, "sceneCount": scene_count, "lineCount": line_count}


def _upsert_video(
    *, vertex_id: str, owner_did: str, project_id: str, title: str, topic: str,
    language: str, target_sec: int, resolution: str, fps: int, status: str,
    seed: int, scenes_json: str, scene_count: int, line_count: int,
    voice_left: str, voice_right: str, script_source: str, created_at: str,
    duration_sec: float = 0.0,
) -> None:
    # RisingWave PK upsert: same vertex_id → overwrite.
    sql = (
        "INSERT INTO vertex_yukkuri_video "
        "(vertex_id, owner_did, project_id, title, topic, language, target_sec, "
        " resolution, fps, status, seed, scenes_json, scene_count, line_count, "
        " voice_left, voice_right, script_source, duration_sec, actor_did, org_did, "
        " sensitivity_ord, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, "
        "        %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (
            vertex_id, owner_did, project_id, title, topic, language, target_sec,
            resolution, fps, status, seed, scenes_json, scene_count, line_count,
            voice_left, voice_right, script_source, duration_sec,
            owner_did, owner_did,  # actor_did, org_did
            1, created_at,
        ))


def _upsert_scene(
    *, vertex_id: str, owner_did: str, video_uri: str, idx: int,
    duration_sec: float, summary: str, created_at: str,
) -> None:
    sql = (
        "INSERT INTO vertex_yukkuri_scene "
        "(vertex_id, owner_did, video_uri, idx, duration_sec, summary, "
        " actor_did, org_did, sensitivity_ord, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (
            vertex_id, owner_did, video_uri, idx, duration_sec, summary,
            owner_did, owner_did, 1, created_at,
        ))


def _upsert_line(
    *, vertex_id: str, owner_did: str, video_uri: str, scene_uri: str, idx: int,
    speaker: str, text: str, emotion: str, voice_preset: str, created_at: str,
) -> None:
    sql = (
        "INSERT INTO vertex_yukkuri_line "
        "(vertex_id, owner_did, video_uri, scene_uri, idx, speaker, text, emotion, "
        " voice_preset, actor_did, org_did, sensitivity_ord, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (
            vertex_id, owner_did, video_uri, scene_uri, idx, speaker, text, emotion,
            voice_preset, owner_did, owner_did, 1, created_at,
        ))


# ──────────────────────────────────────────────────────────────────────
# Task 2: yukkuri.voice.synthesize
# ──────────────────────────────────────────────────────────────────────

def task_yukkuri_voice_synthesize(
    video_uri: str = "",
    voice_left: str = "af_heart",
    voice_right: str = "am_puck",
) -> dict[str, Any]:
    """Synthesize voice for each dialogue line via Kokoro TTS.

    Reads vertex_yukkuri_line rows, calls KOKORO_URL/v1/audio/speech
    for each line, stores the blob key in vertex_yukkuri_line.voice_blob_key
    and inserts vertex_yukkuri_asset rows (kind=voice_audio).
    Falls back gracefully when KOKORO_URL is not configured.
    """
    import httpx

    if not video_uri:
        return {"ok": False, "linesProcessed": 0, "error": "video_uri required", "voiceOk": False}

    kokoro_url = os.environ.get("KOKORO_URL", "").rstrip("/")
    if not kokoro_url:
        _write_generation(
            video_uri=video_uri,
            stage="voice",
            actor_did=PATH_VOICE_LEFT,
            model_id="kokoro-unconfigured",
            params=json.dumps({"note": "KOKORO_URL not set, voice synthesis skipped"}),
            status="ok",
        )
        return {"ok": True, "linesProcessed": 0, "voiceOk": True,
                "note": "KOKORO_URL not configured"}

    lines: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT vertex_id, idx, speaker, text, emotion, voice_preset, scene_uri "
            "FROM vertex_yukkuri_line WHERE video_uri = %s ORDER BY idx",
            (video_uri,),
        )
        for row in _res:
            lines.append({
                "vertex_id": row[0], "idx": row[1], "speaker": row[2] or "left",
                "text": row[3] or "", "emotion": row[4] or "neutral",
                "voice_preset": row[5] or "",
                "scene_uri": row[6] or "",
            })

    if not lines:
        _write_generation(
            video_uri=video_uri, stage="voice", actor_did=PATH_VOICE_LEFT,
            model_id="kokoro-tts", params=json.dumps({"lineCount": 0}), status="ok",
        )
        return {"ok": True, "linesProcessed": 0, "voiceOk": True}

    created_at = _now_iso()
    rkey_vid = _uri_to_rkey(video_uri)
    lines_ok = 0
    lines_failed = 0
    total_audio_sec = 0.0

    for ln in lines:
        text = ln["text"]
        if not text.strip():
            continue

        idx = ln["idx"]
        speaker = ln["speaker"]
        preset = ln["voice_preset"] or (voice_right if speaker == "right" else voice_left)

        audio_data: bytes = b""
        try:
            resp = httpx.post(
                f"{kokoro_url}/v1/audio/speech",
                json={
                    "model": "kokoro",
                    "input": text,
                    "voice": preset,
                    "response_format": "mp3",
                    "speed": 1.0,
                },
                timeout=60.0,
            )
            resp.raise_for_status()
            audio_data = resp.content
        except Exception:
            lines_failed += 1
            continue

        if not audio_data:
            lines_failed += 1
            continue

        # Approximate duration: MP3 ~128kbps → ~16 KB/s
        total_audio_sec += len(audio_data) / 16_000

        blob_key = f"yukkuri-voice-{rkey_vid}-l{idx:04d}"
        asset_uri = f"at://{DEFAULT_REPO}/{COLLECTION_ASSET}/{blob_key}"

        if True:

            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_yukkuri_asset "
                "(vertex_id, owner_did, video_uri, kind, asset_uri, "
                " actor_did, org_did, sensitivity_ord, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s)",
                (asset_uri, DEFAULT_REPO, video_uri, "voice_audio", blob_key,
                 DEFAULT_REPO, DEFAULT_REPO, created_at),
            )

        # Re-insert line row with voice_blob_key set (RW PK upsert)
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_yukkuri_line "
                "(vertex_id, owner_did, video_uri, scene_uri, idx, speaker, text, "
                " emotion, voice_preset, voice_blob_key, "
                " actor_did, org_did, sensitivity_ord, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)",
                (ln["vertex_id"], DEFAULT_REPO, video_uri, ln["scene_uri"],
                 idx, speaker, text, ln["emotion"], preset, blob_key,
                 DEFAULT_REPO, DEFAULT_REPO, created_at),
            )

        lines_ok += 1

    _write_generation(
        video_uri=video_uri,
        stage="voice",
        actor_did=PATH_VOICE_LEFT,
        model_id="kokoro-tts",
        params=json.dumps({
            "lineCount": len(lines),
            "linesOk": lines_ok,
            "linesFailed": lines_failed,
            "voiceLeft": voice_left,
            "voiceRight": voice_right,
        }),
        audio_sec=total_audio_sec,
        status="ok",
    )

    return {
        "ok": True,
        "linesProcessed": lines_ok,
        "voiceOk": lines_ok > 0 or lines_failed == 0,
        "audioSec": round(total_audio_sec, 2),
    }


# ──────────────────────────────────────────────────────────────────────
# Task 3: yukkuri.image.generate
# ──────────────────────────────────────────────────────────────────────

def task_yukkuri_image_generate(
    video_uri: str = "",
) -> dict[str, Any]:
    """Generate background images for each scene via ComfyUI SDXL.

    Reads vertex_yukkuri_scene rows, calls COMFYUI_URL/v1/images/generations
    (OpenAI-compat) for each scene prompt, stores image URI in
    vertex_yukkuri_scene.background_asset_uri and inserts
    vertex_yukkuri_asset rows (kind=bg_image).
    """
    import httpx

    if not video_uri:
        return {"ok": False, "scenesProcessed": 0, "error": "video_uri required", "imageOk": False}

    comfyui_url = os.environ.get("COMFYUI_URL", "https://comfyui.etzhayyim.com").rstrip("/")
    comfyui_api_key = os.environ.get("COMFYUI_API_KEY", "")

    headers: dict[str, str] = {"Content-Type": "application/json"}
    if comfyui_api_key:
        headers["Authorization"] = f"Bearer {comfyui_api_key}"

    scenes: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT vertex_id, idx, summary, duration_sec "
            "FROM vertex_yukkuri_scene WHERE video_uri = %s ORDER BY idx",
            (video_uri,),
        )
        for row in _res:
            scenes.append({
                "vertex_id": row[0], "idx": row[1],
                "summary": row[2] or "", "duration_sec": float(row[3] or 0),
            })

    if not scenes:
        _write_generation(
            video_uri=video_uri, stage="image", actor_did=PATH_ILLUSTRATOR,
            model_id="animagine-xl-4.0",
            params=json.dumps({"sceneCount": 0}), status="ok",
        )
        return {"ok": True, "scenesProcessed": 0, "imageOk": True}

    created_at = _now_iso()
    rkey_vid = _uri_to_rkey(video_uri)
    scenes_ok = 0
    scenes_failed = 0

    for sc in scenes:
        scene_id = sc["vertex_id"]
        idx = sc["idx"]
        summary = sc["summary"]

        prompt = (
            f"anime background art, detailed scenery, {summary}, "
            "high quality, 4k, vivid colors, no characters"
        )

        image_uri = ""
        try:
            resp = httpx.post(
                f"{comfyui_url}/v1/images/generations",
                json={
                    "model": "animagine-xl-4.0.safetensors",
                    "prompt": prompt,
                    "n": 1,
                    "size": "1280x720",
                    "response_format": "url",
                },
                headers=headers,
                timeout=120.0,
            )
            resp.raise_for_status()
            data = resp.json()
            if data.get("data") and len(data["data"]) > 0:
                item = data["data"][0]
                image_uri = item.get("url") or item.get("b64_json", "")
        except Exception:
            scenes_failed += 1
            continue

        if not image_uri:
            scenes_failed += 1
            continue

        asset_rkey = f"yukkuri-bg-{rkey_vid}-s{idx:03d}"
        asset_uri = f"at://{DEFAULT_REPO}/{COLLECTION_ASSET}/{asset_rkey}"

        if True:

            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_yukkuri_asset "
                "(vertex_id, owner_did, video_uri, kind, asset_uri, "
                " actor_did, org_did, sensitivity_ord, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, 1, %s)",
                (asset_uri, DEFAULT_REPO, video_uri, "bg_image", image_uri,
                 DEFAULT_REPO, DEFAULT_REPO, created_at),
            )

        # Re-insert scene row with background_asset_uri set (RW PK upsert)
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "INSERT INTO vertex_yukkuri_scene "
                "(vertex_id, owner_did, video_uri, idx, duration_sec, summary, "
                " background_asset_uri, actor_did, org_did, sensitivity_ord, created_at) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)",
                (scene_id, DEFAULT_REPO, video_uri, idx, sc["duration_sec"],
                 summary, image_uri, DEFAULT_REPO, DEFAULT_REPO, created_at),
            )

        scenes_ok += 1

    _write_generation(
        video_uri=video_uri,
        stage="image",
        actor_did=PATH_ILLUSTRATOR,
        model_id="animagine-xl-4.0",
        params=json.dumps({
            "sceneCount": len(scenes),
            "scenesOk": scenes_ok,
            "scenesFailed": scenes_failed,
        }),
        status="ok",
    )

    return {
        "ok": True,
        "scenesProcessed": scenes_ok,
        "imageOk": scenes_ok > 0 or scenes_failed == 0,
    }


# ──────────────────────────────────────────────────────────────────────
# Task 4: yukkuri.video.assemble
# ──────────────────────────────────────────────────────────────────────

def task_yukkuri_video_assemble(
    video_uri: str = "",
) -> dict[str, Any]:
    """Build timeline from scene/line rows, update video status to editready."""
    if not video_uri:
        return {"ok": False, "status": "error", "durationSec": 0, "error": "video_uri required"}

    created_at = _now_iso()

    # Load scene rows to calculate total duration.
    scenes: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT vertex_id, idx, duration_sec, summary "
            "FROM vertex_yukkuri_scene WHERE video_uri = %s ORDER BY idx",
            (video_uri,),
        )
        for row in _res:
            scenes.append({"vertex_id": row[0], "idx": row[1],
                           "duration_sec": float(row[2] or 0), "summary": row[3] or ""})

    total_duration = sum(s["duration_sec"] for s in scenes)

    # Build lightweight timeline JSON stored in vertex_yukkuri_generation.
    timeline = {
        "videoUri": video_uri,
        "sceneCount": len(scenes),
        "totalDurationSec": total_duration,
        "scenes": [{"idx": s["idx"], "durationSec": s["duration_sec"],
                    "summary": s["summary"]} for s in scenes],
        "generatedAt": created_at,
    }

    # Full-row upsert (RisingWave PK upsert: same vertex_id → overwrite).
    # SELECT existing columns first so we don't clobber title/topic/scenes_json/etc.
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT owner_did, project_id, title, topic, language, target_sec, "
            "       resolution, fps, seed, scenes_json, scene_count, line_count, "
            "       voice_left, voice_right, script_source, created_at "
            "FROM vertex_yukkuri_video WHERE vertex_id = %s LIMIT 1",
            (video_uri,),
        )
        vrow = (_res[0] if _res else None)
    if vrow:
        _upsert_video(
            vertex_id=video_uri,
            owner_did=str(vrow[0] or DEFAULT_REPO),
            project_id=str(vrow[1] or ""),
            title=str(vrow[2] or ""),
            topic=str(vrow[3] or ""),
            language=str(vrow[4] or "ja"),
            target_sec=int(vrow[5] or 120),
            resolution=str(vrow[6] or "1080p"),
            fps=int(vrow[7] or 30),
            status="editready",
            seed=int(vrow[8] or 0),
            scenes_json=str(vrow[9] or "[]"),
            scene_count=int(vrow[10] or 0),
            line_count=int(vrow[11] or 0),
            voice_left=str(vrow[12] or "af_heart"),
            voice_right=str(vrow[13] or "am_puck"),
            script_source=str(vrow[14] or ""),
            created_at=str(vrow[15] or created_at),
            duration_sec=total_duration,
        )

    _write_generation(
        video_uri=video_uri,
        stage="assemble",
        actor_did=PATH_EDITOR,
        model_id="yukkuri-assembler-v1",
        params=json.dumps(timeline),
        video_sec=total_duration,
        status="ok",
    )

    return {"ok": True, "status": "editready", "durationSec": total_duration,
            "sceneCount": len(scenes)}


# ──────────────────────────────────────────────────────────────────────
# Task 5: yukkuri.critic.review
# ──────────────────────────────────────────────────────────────────────

_MIN_LINES = 4
_MAX_DURATION_SEC = 1800
_REJECT_KEYWORDS = [
    "殺", "死ね", "差別", "ヘイト", "レイプ", "爆弾", "自殺",
    "死刑", "虐殺", "テロ", "拷問",
]


def task_yukkuri_critic_review(
    video_uri: str = "",
) -> dict[str, Any]:
    """QA gate: duration / line-count / expression checks.

    Sets vertex_yukkuri_video.status to 'published' or 'rejected'.
    """
    if not video_uri:
        return {"ok": False, "passed": False, "status": "error",
                "rejectReason": "video_uri required"}

    created_at = _now_iso()
    passed = True
    reject_reason = ""

    # Load video metadata.
    video_row: dict[str, Any] = {}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT duration_sec, scene_count, line_count, title, topic "
            "FROM vertex_yukkuri_video WHERE vertex_id = %s LIMIT 1",
            (video_uri,),
        )
        row = (_res[0] if _res else None)
        if row:
            video_row = {
                "duration_sec": float(row[0] or 0),
                "scene_count": int(row[1] or 0),
                "line_count": int(row[2] or 0),
                "title": str(row[3] or ""),
                "topic": str(row[4] or ""),
            }

    # Load all lines for expression check.
    all_text = ""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT text FROM vertex_yukkuri_line WHERE video_uri = %s",
            (video_uri,),
        )
        for row in _res:
            all_text += str(row[0] or "")

    # Duration check.
    duration = video_row.get("duration_sec", 0)
    if duration > _MAX_DURATION_SEC:
        passed = False
        reject_reason = f"duration {duration:.0f}s exceeds max {_MAX_DURATION_SEC}s"

    # Line-count check.
    line_count = video_row.get("line_count", 0)
    if passed and line_count < _MIN_LINES:
        passed = False
        reject_reason = f"too few lines: {line_count} < {_MIN_LINES}"

    # Expression check.
    if passed:
        for kw in _REJECT_KEYWORDS:
            if kw in all_text:
                passed = False
                reject_reason = f"prohibited expression detected"
                break

    final_status = "published" if passed else "rejected"

    # Full-row upsert (RisingWave PK upsert: same vertex_id → overwrite).
    # SELECT existing columns first so we don't clobber title/topic/scenes_json/etc.
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT owner_did, project_id, title, topic, language, target_sec, "
            "       resolution, fps, seed, scenes_json, scene_count, line_count, "
            "       voice_left, voice_right, script_source, created_at, duration_sec "
            "FROM vertex_yukkuri_video WHERE vertex_id = %s LIMIT 1",
            (video_uri,),
        )
        vrow = (_res[0] if _res else None)
    if vrow:
        _upsert_video(
            vertex_id=video_uri,
            owner_did=str(vrow[0] or DEFAULT_REPO),
            project_id=str(vrow[1] or ""),
            title=str(vrow[2] or ""),
            topic=str(vrow[3] or ""),
            language=str(vrow[4] or "ja"),
            target_sec=int(vrow[5] or 120),
            resolution=str(vrow[6] or "1080p"),
            fps=int(vrow[7] or 30),
            status=final_status,
            seed=int(vrow[8] or 0),
            scenes_json=str(vrow[9] or "[]"),
            scene_count=int(vrow[10] or 0),
            line_count=int(vrow[11] or 0),
            voice_left=str(vrow[12] or "af_heart"),
            voice_right=str(vrow[13] or "am_puck"),
            script_source=str(vrow[14] or ""),
            created_at=str(vrow[15] or created_at),
            duration_sec=float(vrow[16] or 0),
        )

    _write_generation(
        video_uri=video_uri,
        stage="critic",
        actor_did=PATH_CRITIC,
        model_id="yukkuri-critic-v1",
        params=json.dumps({"passed": passed, "rejectReason": reject_reason,
                           "lineCount": line_count, "durationSec": duration}),
        status="ok" if passed else "rejected",
        reject_reason=reject_reason if not passed else "",
    )

    return {
        "ok": True,
        "passed": passed,
        "status": final_status,
        "rejectReason": reject_reason,
    }


# ──────────────────────────────────────────────────────────────────────
# Task 6: yukkuri.social.post
# ──────────────────────────────────────────────────────────────────────

def task_yukkuri_social_post(
    video_uri: str = "",
    title: str = "",
    topic: str = "",
    scene_count: int = 0,
    duration_sec: float = 0.0,
    final_status: str = "published",
) -> dict[str, Any]:
    """Emit a social post to vertex_repo_record after critic passes.

    Visible on yoro.etzhayyim.com via the vertex_repo_record → mv_actor_social_stats
    pipeline.  Posts as did:web:yukkuri.etzhayyim.com.
    """
    if not video_uri:
        return {"ok": False, "error": "video_uri required", "postUri": ""}

    # Fetch title/topic from DB if BPMN did not pass them.
    if not title:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT title, topic FROM vertex_yukkuri_video WHERE vertex_id = %s LIMIT 1",
                (video_uri,),
            )
            row = (_res[0] if _res else None)
            if row:
                title = str(row[0] or "")
                topic = str(row[1] or "")

    text = f"🎬 {title}" if title else "🎬 New Yukkuri video"
    if topic:
        text += f"\nテーマ: {topic}"
    if scene_count or duration_sec:
        parts = []
        if scene_count:
            parts.append(f"シーン {int(scene_count)}")
        if duration_sec:
            parts.append(f"{int(duration_sec)}秒")
        text += "\n" + " | ".join(parts)

    created_at = _now_iso()
    rkey = _rkey("yukkuri-pub")
    # Extract video rkey for the embed link (last path segment of AT URI).
    video_rkey = video_uri.split("/")[-1] if video_uri else ""
    embed: dict[str, Any] | None = None
    if video_rkey:
        embed = {
            "$type": "app.bsky.embed.external",
            "external": {
                "uri": f"https://yukkuri.etzhayyim.com/video/{video_rkey}",
                "title": (title or "🎬 Yukkuri AI Video")[:200],
                "description": (topic or "AI-generated ゆっくり commentary video")[:300],
            },
        }
    record: dict[str, Any] = {
        "$type": "app.bsky.feed.post",
        "text": text[:300],
        "createdAt": created_at,
        "tags": ["yukkuri", "ai-video"],
    }
    if embed:
        record["embed"] = embed
    repo_row = build_repo_record(
        repo=DEFAULT_REPO,
        collection="app.bsky.feed.post",
        record=record,
        created_at=created_at,
        rkey=rkey,
        actor_path="yukkuri-pub",
    )
    result = insert_social_post_record(repo_row, flush=False)
    return {"ok": True, "postUri": result["uri"], "postText": result["text"]}


# ──────────────────────────────────────────────────────────────────────
# Shared helper
# ──────────────────────────────────────────────────────────────────────

def _write_generation(
    *,
    video_uri: str,
    stage: str,
    actor_did: str,
    model_id: str,
    params: str,
    audio_sec: float = 0.0,
    video_sec: float = 0.0,
    status: str = "ok",
    reject_reason: str = "",
) -> None:
    rkey = _rkey(f"gen-{stage}")
    gen_uri = f"at://{DEFAULT_REPO}/{COLLECTION_GENERATION}/{rkey}"
    created_at = _now_iso()
    sql = (
        "INSERT INTO vertex_yukkuri_generation "
        "(vertex_id, target_uri, stage, actor_did, model_id, params, "
        " audio_sec, video_sec, status, reject_reason, "
        " owner_did, org_did, sensitivity_ord, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1, %s)"
    )
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, (
            gen_uri, video_uri, stage, actor_did, model_id, params,
            audio_sec, video_sec, status, reject_reason,
            DEFAULT_REPO, DEFAULT_REPO, created_at,
        ))


# ──────────────────────────────────────────────────────────────────────
# LangServer registration
# ──────────────────────────────────────────────────────────────────────

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire yukkuri pipeline primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    t("yukkuri.scene.persist",     task_yukkuri_scene_persist,    timeout=max(timeout_ms, 60_000))
    t("yukkuri.voice.synthesize",  task_yukkuri_voice_synthesize, timeout=max(timeout_ms, 120_000))
    t("yukkuri.image.generate",    task_yukkuri_image_generate,   timeout=max(timeout_ms, 120_000))
    t("yukkuri.video.assemble",    task_yukkuri_video_assemble,   timeout=max(timeout_ms, 60_000))
    t("yukkuri.critic.review",     task_yukkuri_critic_review,    timeout=max(timeout_ms, 60_000))
    t("yukkuri.social.post",       task_yukkuri_social_post,      timeout=30_000)


__all__ = [
    "register",
    "task_yukkuri_scene_persist",
    "task_yukkuri_voice_synthesize",
    "task_yukkuri_image_generate",
    "task_yukkuri_video_assemble",
    "task_yukkuri_critic_review",
    "task_yukkuri_social_post",
]
