"""
shinshi.scene.render — SDXL still-image generation via ComfyUI + AT post.
shinshi.scene.bulkSeed — bulk 5-scene seeding per actress (anime / photoreal).

Generation pipeline lives here per ADR-2604282300 (CF Worker = edge layer
only). The shinshi CF Worker proxies to dispatcher.etzhayyim.com → Zeebe →
this handler, which builds the ComfyUI workflow, submits to RunPod
(via comfyui.etzhayyim.com or pod direct with browser UA per
runpod-proxy-browser-ua-required), polls /history, fetches /view bytes,
uploads to PDS, and writes the AT post (graph C-path).

Tasks
  shinshi.scene.render      single render (used by `requestScene`)
    inputs : modelDid, userDid, prompt, sceneType, ckpt, appDid
    outputs: postUri, blobKey, cid, renderMs

  shinshi.scene.bulkSeed    5-scene narrative loop (anime SDXL or photoreal)
    inputs : slugs[], appDid, sceneType, sceneIndices[], skipIfExisting,
             ckpt, style ("anime"/"photoreal")
    outputs: results[], totalActresses, totalPosted, totalSkipped
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import base64 as _b64
import hashlib
import hmac
import json
import os
import time
import urllib.error as _u_err
import urllib.parse as _u_parse
import urllib.request as _u_req
from typing import Any

from kotodama.primitives.yoro_social import (
    build_repo_record,
    insert_social_post_record,
    utc_now_iso,
    _rkey,
)

_COMFY_POD_URL = os.environ.get(
    "COMFY_POD_URL",
    "https://vyp99t9px7h4dl-8188.proxy.runpod.net",
)
_PDS_BASE = os.environ.get("PDS_URL", "https://atproto.etzhayyim.com")
_SHINSHI_DID = "did:web:sh1n5h1x.etzhayyim.com"

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/129.0.0.0 Safari/537.36"
)
_INTERNAL_HEADERS = {
    "x-kotoba-kotodama-verified": "true",
    "x-etzhayyim-org-id": "anon",
}

# ── PDS Service Auth (lxm-scoped JWT) — mirror gov_che / zeebe_worker_main ──
# LangServer pod runs in Vultr k8s, calls PDS over public internet → CF Worker.
# The `x-kotoba-kotodama-verified` shortcut is only honored for intra-CF callers, so
# external callers must mint a Service Auth JWT via the PDS internal mint
# endpoint (HMAC-signed body → short-lived bearer token, lxm-scoped).
_PDS_SERVICE_AUTH_TOKEN = os.environ.get("PDS_SERVICE_AUTH_TOKEN", "").strip()
_PDS_SERVICE_AUTH_MINT_URL = os.environ.get(
    "PDS_SERVICE_AUTH_MINT_URL",
    f"{_PDS_BASE}/_internal/mint-pds-bearer",
).strip()
_PDS_SERVICE_AUTH_MINT_SECRET = os.environ.get("PDS_SERVICE_AUTH_MINT_SECRET", "").strip()
_PDS_LEGACY_INTERNAL_TRUST = os.environ.get("PDS_LEGACY_INTERNAL_TRUST", "0") == "1"
try:
    _PDS_SERVICE_AUTH_TTL_SEC = max(30, min(600, int(os.environ.get("PDS_SERVICE_AUTH_TTL_SEC", "600"))))
except ValueError:
    _PDS_SERVICE_AUTH_TTL_SEC = 600
_PDS_SERVICE_AUTH_CACHE: dict[str, dict[str, Any]] = {}


def _mint_pds_service_auth(lxm: str) -> str:
    """Mint or reuse a cached lxm-scoped PDS Service Auth JWT."""
    cached = _PDS_SERVICE_AUTH_CACHE.get(lxm)
    now = int(time.time())
    if cached and int(cached.get("expiresAt", 0)) > now + 30:
        token = str(cached.get("token") or "")
        if token:
            return token
    if not _PDS_SERVICE_AUTH_MINT_URL or not _PDS_SERVICE_AUTH_MINT_SECRET:
        return ""
    payload = {"lxm": lxm, "ttlSeconds": _PDS_SERVICE_AUTH_TTL_SEC}
    body = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    sig = hmac.new(_PDS_SERVICE_AUTH_MINT_SECRET.encode("utf-8"), body, hashlib.sha256).hexdigest()
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "x-bpmn-auth": sig,
        "User-Agent": _BROWSER_UA,
    }
    req = _u_req.Request(_PDS_SERVICE_AUTH_MINT_URL, data=body, headers=headers, method="POST")
    try:
        with _u_req.urlopen(req, timeout=10.0) as resp:
            data = json.loads(resp.read().decode("utf-8"))
    except Exception:  # noqa: BLE001
        return ""
    token = str(data.get("token") or "")
    expires_at = int(data.get("expiresAt") or (now + _PDS_SERVICE_AUTH_TTL_SEC))
    if token:
        _PDS_SERVICE_AUTH_CACHE[lxm] = {"token": token, "expiresAt": expires_at}
    return token


def _pds_auth_headers(lxm: str, *, repo: str = "") -> dict[str, str]:
    """Resolve auth headers for a PDS XRPC call.
    Order: cached/fresh service-auth JWT → static PDS_SERVICE_AUTH_TOKEN
           → legacy x-kotoba-kotodama-verified (only if PDS_LEGACY_INTERNAL_TRUST=1).
    """
    token = _mint_pds_service_auth(lxm) or _PDS_SERVICE_AUTH_TOKEN
    headers: dict[str, str] = {"User-Agent": _BROWSER_UA}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    elif _PDS_LEGACY_INTERNAL_TRUST:
        headers["x-kotoba-kotodama-verified"] = "true"
        headers["x-etzhayyim-org-id"] = "anon"
    if repo:
        headers["x-kotoba-kotodama-repo"] = repo
    return headers

_RENDER_TIMEOUT_MS = 180_000  # 3 min per scene
_POLL_DEADLINE_SEC = 90.0
_HARD_DENY_TERMS = (
    "child",
    "minor",
    "loli",
    "shota",
    "underage",
    "rape",
    "bestial",
    "necro",
    "real-person",
    "real person",
    "deepfake",
)

# ── Slug → minimal profile (port of deriveSlugProfile, prompt-only fields) ──

_KNOWN_SERIES_MULTI = (
    "seraph-of-the-end", "call-of-duty-mobile", "final-fantasy-xiv", "final-fantasy-vii",
    "final-fantasy-xv", "honkai-impact-3rd", "mob-psycho-100", "dark-souls-iii",
    "street-fighter-v", "street-fighter-6", "rurouni-kenshin", "pandora-hearts",
    "fate-grand-order", "spy-x-family", "octopath-traveler", "elden-ring", "one-piece",
    "arena-of-valor", "mobile-legends", "psycho-pass", "ace-attorney", "tower-of-fantasy",
    "clash-royale", "one-punch-man", "granblue-fantasy", "yuyu-hakusho", "honor-of-kings",
    "fruits-basket", "azur-lane", "apex-legends", "summoners-war", "high-school-dxd",
    "persona-5", "crossfire", "dota-2", "bayonetta", "trigun", "onmyoji",
    "attack-on-titan", "demon-slayer", "jujutsu-kaisen", "chainsaw-man", "soulworker",
    "identity-v", "my-hero-academia", "naruto", "bleach", "yakuza-0", "cyberpunk-2077",
    "final-fantasy", "fire-emblem", "genshin-impact", "arknights", "blue-archive",
    "warframe", "chrono-trigger", "blue-exorcist", "free-fire", "overwatch-2",
    "league-of-legends", "valorant", "tekken-7", "sailor-moon",
)


def _title_case(s: str) -> str:
    return " ".join(
        w.lower() if len(w) <= 2 else w[:1].upper() + w[1:].lower()
        for w in s.split(" ")
    )


def _cheap_hash(s: str) -> int:
    h = 0
    for c in s:
        h = ((h << 5) - h + ord(c)) & 0xFFFFFFFF
    return h


def _derive_profile(slug: str) -> dict[str, Any]:
    char_slug, series_slug = "", ""
    for sx in _KNOWN_SERIES_MULTI:
        if slug.endswith(f"-{sx}"):
            char_slug = slug[: -(len(sx) + 1)]
            series_slug = sx
            break
    if not series_slug:
        parts = slug.split("-")
        if len(parts) >= 3:
            char_slug = " ".join(parts[:-2])
            series_slug = " ".join(parts[-2:])
        elif len(parts) == 2:
            char_slug, series_slug = parts[0], parts[1]
        else:
            char_slug = slug.replace("-", " ")
            series_slug = "original"

    char_name = _title_case(char_slug.replace("-", " "))
    series = _title_case(series_slug.replace("-", " "))
    h = _cheap_hash(slug)

    body_types = ("slim", "average", "curvy", "athletic", "voluptuous", "petite", "tall")
    ethnicities = ("asian", "asian", "european", "latin", "mixed")
    occupations = (
        "student", "idol", "warrior", "mage", "adventurer", "office lady", "nurse",
        "teacher", "swordsman", "gunner", "hacker", "scientist", "thief", "detective",
        "mercenary",
    )
    hobbies_pool = (
        "gaming", "cosplay", "karaoke", "dance", "tea ceremony", "reading", "cooking",
        "training", "photography", "anime", "shopping", "astronomy", "painting", "music",
    )
    personality_pool = (
        "confident", "playful", "calm", "flirty", "shy", "energetic", "mysterious",
        "warm", "sarcastic", "caring", "bold", "gentle", "witty", "serene", "fierce",
    )
    prompt_styles = (
        "playful-casual", "regal-flirty", "cool-tsundere", "warm-mentor",
        "shy-sweet", "bold-seducer",
    )

    return {
        "charName": char_name,
        "series": series,
        "bodyType": body_types[h % len(body_types)],
        "ethnicityLook": ethnicities[h % len(ethnicities)],
        "personality": [
            personality_pool[h % len(personality_pool)],
            personality_pool[(h * 11 + 13) % len(personality_pool)],
        ],
        "hobbies": [hobbies_pool[h % len(hobbies_pool)]],
        "occupation": occupations[h % len(occupations)],
        "promptStyle": prompt_styles[h % len(prompt_styles)],
    }


# ── 5-scene narrative templates (anime / photoreal) ──

_SCENE_LABELS_ANIME = (
    {
        "key": "morning", "ja": "朝の目覚め",
        "prompt": "morning sunlight through curtains, just-awoken expression, soft pillow, casual home wear, intimate atmosphere, golden hour interior",
        "chapter": "Chapter 1 / 朝",
    },
    {
        "key": "training", "ja": "鍛錬の時間",
        "prompt": "training environment, focused intense expression, athletic outfit, dynamic motion, sweat detail, dramatic side light",
        "chapter": "Chapter 2 / 昼",
    },
    {
        "key": "moment", "ja": "ふとした瞬間",
        "prompt": "quiet cafe window seat, wistful gaze through window, autumn afternoon light, melancholy mood, casual elegant outfit",
        "chapter": "Chapter 3 / 午後",
    },
    {
        "key": "stage", "ja": "本番の輝き",
        "prompt": "stage performance moment, confident triumphant pose, dramatic spotlight, audience perspective, professional finish",
        "chapter": "Chapter 4 / 夕",
    },
    {
        "key": "private", "ja": "誰にも見せない夜",
        "prompt": "private bedroom moment, soft bedside lamp, lingerie or yukata, vulnerable graceful pose, midnight blue mood, candle-lit",
        "chapter": "Chapter 5 / 夜",
    },
)

_SCENE_LABELS_PHOTOREAL = (
    {
        "key": "morning", "ja": "朝の目覚め",
        "prompt": "morning sunlight streaming through linen curtains, just-awoken expression, natural skin texture, warm bedroom interior, golden hour, 35mm lens, shallow depth of field",
        "chapter": "Chapter 1 / 朝",
    },
    {
        "key": "training", "ja": "鍛錬の時間",
        "prompt": "training environment, focused intense expression, athletic outfit, dynamic motion, skin glistening with sweat, dramatic side rim light, 50mm lens, motion blur background",
        "chapter": "Chapter 2 / 昼",
    },
    {
        "key": "moment", "ja": "ふとした瞬間",
        "prompt": "quiet cafe window seat, wistful gaze through window, autumn afternoon natural light, melancholy mood, casual elegant outfit, 85mm lens portrait, bokeh background",
        "chapter": "Chapter 3 / 午後",
    },
    {
        "key": "stage", "ja": "本番の輝き",
        "prompt": "stage performance moment, confident triumphant pose, dramatic spotlight, audience perspective, professional event photography, 70-200mm zoom, shallow focus",
        "chapter": "Chapter 4 / 夕",
    },
    {
        "key": "private", "ja": "誰にも見せない夜",
        "prompt": "private bedroom moment, soft bedside lamp, lingerie or yukata, vulnerable graceful pose, midnight blue mood, candlelight, 50mm lens, intimate composition, low key lighting",
        "chapter": "Chapter 5 / 夜",
    },
)

_VOICE_LINES = {
    "morning":  "おはよ。{name}です。{mood}な朝、{hobby}でゆっくり始めようかな。",
    "training": "{occupation}としては妥協できない。{mood}な私を、見ててね。",
    "moment":   "{series}での日々を、ふと思い出す午後。{mood}な時間、嫌いじゃないかも。",
    "stage":    "{name}の本気、見てくれる? {mood}全開で行くから。",
    "private":  "…誰にも見せない、私だけの時間。{mood}な夜、ちょっとだけ覗いてみる?",
}

_NSFW_LABELS = {
    "$type": "com.atproto.label.defs#selfLabels",
    "values": [{"val": "nsfw"}, {"val": "nudity"}, {"val": "sexual"}],
}


def _build_anime_workflow(prompt: str, ckpt: str, width: int, height: int, steps: int) -> dict:
    """Animagine / illustrious-style anime SDXL workflow."""
    seed = int(time.time() * 1000) & 0xFFFFFFFF
    negative = (
        "lowres, worst quality, low quality, bad anatomy, bad hands, missing fingers, "
        "extra digit, fewer digits, cropped, text, signature, watermark, username, blurry, "
        "jpeg artifacts, ugly, duplicate, mutated, deformed, normal quality, monochrome"
    )
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 5.0,
            "sampler_name": "euler_ancestral", "scheduler": "normal", "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["5", 0],
        }},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "shinshi"}},
    }


def _build_photoreal_workflow(prompt: str, ckpt: str, width: int, height: int, steps: int) -> dict:
    """waiREALCN / SDXL-realistic — dpmpp_2m + karras for skin detail."""
    seed = int(time.time() * 1000) & 0xFFFFFFFF
    negative = (
        "anime, illustration, painting, cartoon, drawing, 3d render, cgi, sketch, "
        "lowres, worst quality, low quality, bad anatomy, bad hands, missing fingers, "
        "extra digit, fewer digits, cropped, text, signature, watermark, username, blurry, "
        "jpeg artifacts, ugly, duplicate, mutated, deformed, plastic skin, doll-like, airbrushed"
    )
    return {
        "3": {"class_type": "KSampler", "inputs": {
            "seed": seed, "steps": steps, "cfg": 6.5,
            "sampler_name": "dpmpp_2m", "scheduler": "karras", "denoise": 1.0,
            "model": ["4", 0], "positive": ["6", 0], "negative": ["7", 0],
            "latent_image": ["5", 0],
        }},
        "4": {"class_type": "CheckpointLoaderSimple", "inputs": {"ckpt_name": ckpt}},
        "5": {"class_type": "EmptyLatentImage", "inputs": {"width": width, "height": height, "batch_size": 1}},
        "6": {"class_type": "CLIPTextEncode", "inputs": {"text": prompt, "clip": ["4", 1]}},
        "7": {"class_type": "CLIPTextEncode", "inputs": {"text": negative, "clip": ["4", 1]}},
        "8": {"class_type": "VAEDecode", "inputs": {"samples": ["3", 0], "vae": ["4", 2]}},
        "9": {"class_type": "SaveImage", "inputs": {"images": ["8", 0], "filename_prefix": "shinshi-real"}},
    }


# ── HTTP helpers (sync, called via asyncio.to_thread) ──

def _http_post_json(url: str, payload: dict, timeout: float = 30.0) -> tuple[int, dict]:
    body = json.dumps(payload).encode("utf-8")
    req = _u_req.Request(
        url, data=body, method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": _BROWSER_UA},
    )
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


def _http_get_json(url: str, timeout: float = 30.0) -> tuple[int, dict]:
    req = _u_req.Request(url, headers={"User-Agent": _BROWSER_UA, "Accept": "application/json"})
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8"))
    except Exception as e:  # noqa: BLE001
        return -1, {"error": str(e)}


def _http_get_bytes(url: str, timeout: float = 60.0) -> tuple[int, bytes]:
    req = _u_req.Request(url, headers={"User-Agent": _BROWSER_UA})
    try:
        with _u_req.urlopen(req, timeout=timeout) as resp:
            return resp.status, resp.read()
    except Exception as e:  # noqa: BLE001
        return -1, str(e).encode("utf-8")


def _http_post_bytes(url: str, body: bytes, headers: dict, timeout: float = 60.0) -> tuple[int, dict]:
    h = {"User-Agent": _BROWSER_UA, **headers}
    req = _u_req.Request(url, data=body, method="POST", headers=h)
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


# ── Generation primitives ──

async def _comfy_render_png(workflow: dict) -> tuple[bytes | None, str]:
    """Submit workflow to RunPod ComfyUI pod (browser UA), poll history,
    fetch first PNG. Returns (png_bytes_or_none, error_string_or_empty)."""
    base = _COMFY_POD_URL.rstrip("/")
    submit_status, submit_data = await asyncio.to_thread(
        _http_post_json, f"{base}/prompt", {"prompt": workflow}, 30.0
    )
    if submit_status != 200:
        return None, f"submit:{submit_status}:{json.dumps(submit_data)[:120]}"
    prompt_id = submit_data.get("prompt_id") if isinstance(submit_data, dict) else None
    if not prompt_id:
        return None, "no-prompt-id"

    deadline = time.monotonic() + _POLL_DEADLINE_SEC
    img_ref: dict | None = None
    intervals = (1.0, 2.0, 2.0, 3.0, 3.0, 3.0)
    i = 0
    while time.monotonic() < deadline:
        await asyncio.sleep(intervals[min(i, len(intervals) - 1)])
        i += 1
        hist_status, hist_data = await asyncio.to_thread(
            _http_get_json, f"{base}/history/{prompt_id}", 15.0
        )
        if hist_status != 200 or not isinstance(hist_data, dict):
            continue
        entry = hist_data.get(prompt_id)
        if not isinstance(entry, dict):
            continue
        outputs = entry.get("outputs") or {}
        for node in outputs.values():
            if isinstance(node, dict):
                for img in node.get("images") or []:
                    if isinstance(img, dict) and img.get("filename"):
                        img_ref = img
                        break
            if img_ref:
                break
        if img_ref:
            break

    if not img_ref:
        return None, "poll-timeout"

    qs = _u_parse.urlencode({
        "filename": img_ref.get("filename", ""),
        "subfolder": img_ref.get("subfolder", "") or "",
        "type": img_ref.get("type", "output") or "output",
    })
    view_status, view_bytes = await asyncio.to_thread(
        _http_get_bytes, f"{base}/view?{qs}", 60.0
    )
    if view_status != 200 or not view_bytes or len(view_bytes) < 100:
        return None, f"view:{view_status}:{len(view_bytes)}"
    return view_bytes, ""


async def _upload_blob_to_pds(png: bytes, repo: str) -> str:
    """uploadBlob to PDS via Service Auth Bearer token, return blob CID
    (`$link`) or empty string. Mints (or reuses cached) lxm-scoped JWT for
    `com.atproto.repo.uploadBlob` since LangServer pod calls PDS over public
    internet (intra-CF `x-kotoba-kotodama-verified` shortcut not honored)."""
    auth = _pds_auth_headers("com.atproto.repo.uploadBlob", repo=repo)
    if (
        "Authorization" not in auth
        and "x-kotoba-kotodama-verified" not in auth
        and "x-kotoba-kotodama-repo" not in auth
    ):
        return ""  # no auth available — fail loud rather than silent 401
    headers = {"Content-Type": "image/png", **auth}
    status, body = await asyncio.to_thread(
        _http_post_bytes,
        f"{_PDS_BASE}/xrpc/com.atproto.repo.uploadBlob",
        png, headers, 90.0,
    )
    if status != 200 or not isinstance(body, dict):
        return ""
    blob = body.get("blob") or {}
    ref = blob.get("ref") or {} if isinstance(blob, dict) else {}
    link = ref.get("$link") if isinstance(ref, dict) else ""
    return str(link or "")


async def _list_existing_image_posts(model_did: str, limit: int = 10) -> int:
    """Return count of posts on `model_did` that already carry image embeds."""
    qs = _u_parse.urlencode({
        "repo": model_did,
        "collection": "app.bsky.feed.post",
        "limit": str(limit),
    })
    auth = _pds_auth_headers("com.atproto.repo.listRecords")
    req = _u_req.Request(
        f"{_PDS_BASE}/xrpc/com.atproto.repo.listRecords?{qs}",
        headers=auth,
    )
    def _do() -> int:
        try:
            with _u_req.urlopen(req, timeout=15.0) as resp:
                if resp.status != 200:
                    return 0
                data = json.loads(resp.read().decode("utf-8"))
        except Exception:  # noqa: BLE001
            return 0
        records = data.get("records") if isinstance(data, dict) else None
        if not isinstance(records, list):
            return 0
        n = 0
        for r in records:
            v = r.get("value") if isinstance(r, dict) else None
            embed = v.get("embed") if isinstance(v, dict) else None
            if isinstance(embed, dict) and embed.get("$type") == "app.bsky.embed.images":
                imgs = embed.get("images")
                if isinstance(imgs, list) and imgs:
                    n += 1
        return n
    return await asyncio.to_thread(_do)


async def _post_scene(
    *, repo: str, png: bytes, blob_cid: str, text: str, alt: str,
    actor_path: str = "shinshi-scene",
) -> tuple[str, str]:
    """Build embed.images record and persist via graph C-path. Returns
    (post_uri, post_cid). post_cid is "" since vertex_repo_record path
    does not compute MST CID (record-log semantics, see root CLAUDE.md
    'Record-log semantics, not MST')."""
    created_at = utc_now_iso()
    rkey = _rkey(actor_path)
    uri = f"at://{repo}/app.bsky.feed.post/{rkey}"
    record = {
        "$type": "app.bsky.feed.post",
        "text": text[:290],
        "createdAt": created_at,
        "embed": {
            "$type": "app.bsky.embed.images",
            "images": [{
                "image": {
                    "$type": "blob",
                    "ref": {"$link": blob_cid},
                    "mimeType": "image/png",
                    "size": len(png),
                },
                "alt": alt[:300],
            }],
        },
        "labels": _NSFW_LABELS,
    }
    row = build_repo_record(
        repo=repo,
        collection="app.bsky.feed.post",
        record=record,
        created_at=created_at,
        rkey=rkey,
        actor_path=actor_path,
    )
    # flush=False — RW checkpoint (~5s) makes the row visible without
    # an explicit FLUSH, and `RW_DDL_GUARD=1` (CLAUDE.md scaling
    # contract) blocks FLUSH in hot-path workers. Mirrors the
    # `task_yoro_social_*GraphFallback` fix from 2026-04-30; without
    # this, every scene render succeeds but reports FAIL → Zeebe
    # retries up to 3x → 3x ComfyUI cost per scene.
    await asyncio.to_thread(insert_social_post_record, row, flush=False)
    return uri, ""


def _hard_deny(text: str) -> bool:
    low = text.lower()
    return any(t in low for t in _HARD_DENY_TERMS)


# ── Single-render task ──

async def task_shinshi_scene_render(
    modelDid: str = "",
    userDid: str = "anon",
    prompt: str = "",
    sceneType: str = "standard",
    ckpt: str = "animagine-xl-4.0.safetensors",
    appDid: str = _SHINSHI_DID,
    style: str = "anime",
) -> dict[str, Any]:
    started = time.monotonic()
    if not modelDid or not prompt:
        return {"error": "modelDid and prompt required"}
    if _hard_deny(prompt):
        return {"error": "content policy violation"}

    # Derive light profile from modelDid path (the slug after the last ':')
    slug = modelDid.rsplit(":", 1)[-1]
    profile = _derive_profile(slug)
    char_name = profile["charName"]
    series = profile["series"]
    persona = ", ".join(profile["personality"][:2])

    # Resolution from sceneType
    sizes = {"thumb": (768, 1152), "standard": (832, 1216), "hires": (1024, 1536)}
    width, height = sizes.get(sceneType, (832, 1216))
    steps_map = {"thumb": 14, "standard": 22, "hires": 28}
    steps = steps_map.get(sceneType, 22)

    if style == "photoreal":
        full_prompt = (
            f"RAW photo, 8k uhd, dslr, soft natural lighting, photorealistic, sharp focus, kodak portra 400, "
            f"solo woman, age 21, cosplay of {char_name} from {series}, mature elegant, professional cosplay outfit, "
            f"{profile['bodyType']} build, {profile['ethnicityLook']}, {persona} expression, {profile['promptStyle']}, "
            f"{prompt}, perfect anatomy, perfect hands, detailed eyes, natural pores"
        )
        workflow = _build_photoreal_workflow(full_prompt, ckpt, width, height, steps)
    else:
        full_prompt = (
            f"masterpiece, best quality, very aesthetic, absurdres, highres, newest, "
            f"1girl, solo, {char_name} \\({series}\\), cosplay, mature woman, 21 years old, "
            f"{profile['bodyType']} build, {profile['ethnicityLook']}, {persona} expression, {profile['promptStyle']}, "
            f"{prompt}, looking at viewer, perfect anatomy, detailed eyes"
        )
        workflow = _build_anime_workflow(full_prompt, ckpt, width, height, steps)

    png, err = await _comfy_render_png(workflow)
    if not png:
        return {"error": f"render-failed:{err}", "renderMs": int((time.monotonic() - started) * 1000)}

    blob_cid = await _upload_blob_to_pds(png, modelDid)
    if not blob_cid:
        return {"error": "blob-upload-failed", "renderMs": int((time.monotonic() - started) * 1000)}

    title = prompt if len(prompt) <= 80 else prompt[:77] + "…"
    post_uri, post_cid = await _post_scene(
        repo=modelDid, png=png, blob_cid=blob_cid,
        text=f"{char_name} — {title}",
        alt=f"{char_name} — {title} (AI-generated cosplay)",
        actor_path="shinshi-scene",
    )

    return {
        "postUri": post_uri,
        "blobKey": blob_cid,
        "cid": post_cid,
        "renderMs": int((time.monotonic() - started) * 1000),
        "userDid": userDid,
    }


# ── Bulk seed task ──

async def task_shinshi_scene_bulk_seed(
    slugs: list[str] | None = None,
    appDid: str = _SHINSHI_DID,
    sceneType: str = "thumb",
    sceneIndices: list[int] | None = None,
    skipIfExisting: bool = True,
    ckpt: str = "animagine-xl-4.0.safetensors",
    style: str = "anime",
) -> dict[str, Any]:
    safe_slugs = []
    for s in (slugs or [])[:3]:
        if isinstance(s, str) and s and not any(t in s.lower() for t in ("test", "rkey-fix", "dummy")):
            safe_slugs.append(s)
    indices = [i for i in (sceneIndices or [0, 1, 2, 3, 4]) if isinstance(i, int) and 0 <= i < 5]
    if not indices:
        indices = [0, 1, 2, 3, 4]

    labels = _SCENE_LABELS_PHOTOREAL if style == "photoreal" else _SCENE_LABELS_ANIME
    sizes = {"thumb": (768, 1152), "standard": (832, 1216), "hires": (1024, 1536)}
    width, height = sizes.get(sceneType, (768, 1152))
    steps = {"thumb": 14, "standard": 22, "hires": 28}.get(sceneType, 14)

    results: list[dict[str, Any]] = []
    total_posted = 0
    total_skipped = 0

    for slug in safe_slugs:
        model_did = f"{appDid}:{slug}"
        if skipIfExisting:
            existing = await _list_existing_image_posts(model_did, 10)
            if existing >= 5:
                results.append({"slug": slug, "did": model_did, "scenesPosted": 0, "blobKeys": [], "skipped": True})
                total_skipped += 1
                continue

        profile = _derive_profile(slug)
        char_name = profile["charName"]
        series = profile["series"]
        persona = ", ".join(profile["personality"][:2])

        if style == "photoreal":
            base_prompt = (
                "RAW photo, 8k uhd, dslr, soft natural lighting, photorealistic, sharp focus, kodak portra 400, "
                f"solo woman, age 21, cosplay of {char_name} from {series}, mature elegant, professional cosplay outfit, "
                f"{profile['bodyType']} build, {profile['ethnicityLook']}, {persona} expression, {profile['promptStyle']}, "
                "perfect anatomy, perfect hands, detailed eyes, natural pores, subsurface scattering, photorealistic skin"
            )
        else:
            base_prompt = (
                "masterpiece, best quality, very aesthetic, absurdres, highres, newest, "
                f"1girl, solo, {char_name} \\({series}\\), cosplay, mature woman, 21 years old, "
                f"{profile['bodyType']} build, {profile['ethnicityLook']}, {persona} expression, {profile['promptStyle']}, "
                "looking at viewer, perfect anatomy, detailed eyes, sharp focus"
            )

        scene_blobs: list[str] = []
        scenes_posted = 0
        diag: list[str] = []

        for idx in indices:
            scene = labels[idx]
            full_prompt = f"{base_prompt}, {scene['prompt']}"
            if _hard_deny(full_prompt):
                diag.append(f"{scene['key']}:deny")
                continue
            workflow = (
                _build_photoreal_workflow(full_prompt, ckpt, width, height, steps)
                if style == "photoreal"
                else _build_anime_workflow(full_prompt, ckpt, width, height, steps)
            )
            png, err = await _comfy_render_png(workflow)
            if not png:
                diag.append(f"{scene['key']}:{err}")
                continue
            blob_cid = await _upload_blob_to_pds(png, model_did)
            if not blob_cid:
                diag.append(f"{scene['key']}:blob-fail")
                continue
            scene_blobs.append(blob_cid)

            voice = _VOICE_LINES.get(scene["key"], "{name} — {scene}").format(
                name=char_name, scene=scene["ja"], series=series,
                mood=profile["personality"][0] if profile["personality"] else "穏やか",
                hobby=profile["hobbies"][0] if profile["hobbies"] else "コーヒー",
                occupation=profile["occupation"],
            )
            tag_style = " #photoreal" if style == "photoreal" else ""
            text = (
                f"{voice}\n\n#{series.replace(' ', '')} "
                f"#{scene['chapter'].split(' / ')[0].replace(' ', '')}{tag_style}"
            )
            try:
                await _post_scene(
                    repo=model_did, png=png, blob_cid=blob_cid,
                    text=text,
                    alt=f"{char_name} - {scene['ja']} ({scene['chapter']}, AI generated, 18+)",
                    actor_path="shinshi-bulk",
                )
                scenes_posted += 1
                total_posted += 1
            except Exception as e:  # noqa: BLE001
                diag.append(f"{scene['key']}:post:{str(e)[:60]}")

        result_entry: dict[str, Any] = {
            "slug": slug, "did": model_did,
            "scenesPosted": scenes_posted, "blobKeys": scene_blobs,
        }
        if diag:
            result_entry["error"] = "; ".join(diag)
        results.append(result_entry)

    return {
        "results": results,
        "totalActresses": len(safe_slugs),
        "totalPosted": total_posted,
        "totalSkipped": total_skipped,
    }


async def task_shinshi_coverage_find_incomplete(
    appDid: str = _SHINSHI_DID,
    minScenes: int = 5,
    maxModels: int = 5,
) -> dict[str, Any]:
    """Return slugs of registered shinshi models with fewer than `minScenes`
    image posts. Used by `shinshi_seed_gap_fill` BPMN to drive autonomous
    backfill of partial / empty model bulk seeds.

    Output: {"slugs": [...], "totalIncomplete": int, "checked": int}
    """

    bound_max = max(1, min(50, int(maxModels)))
    bound_min = max(1, min(5, int(minScenes)))
    repo_prefix = f"{appDid}:"

    sql = (
        "WITH model_repos AS ("
        "  SELECT DISTINCT repo FROM vertex_repo_record "
        "  WHERE collection = 'com.etzhayyim.apps.shinshi.modelProfile' "
        "    AND repo LIKE %s"
        "), "
        "scene_counts AS ("
        "  SELECT repo, count(*) AS n FROM vertex_repo_record "
        "  WHERE collection = 'app.bsky.feed.post' "
        "    AND repo LIKE %s "
        "  GROUP BY repo"
        ") "
        "SELECT m.repo, COALESCE(s.n, 0) AS scene_count "
        "FROM model_repos m "
        "LEFT JOIN scene_counts s ON s.repo = m.repo "
        f"WHERE COALESCE(s.n, 0) < {bound_min} "
        "ORDER BY COALESCE(s.n, 0) ASC, m.repo "
        f"LIMIT {bound_max}"
    )
    like_pat = f"{repo_prefix}%"

    rows: list[tuple[str, int]] = []
    total_incomplete = 0
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(sql, (like_pat, like_pat))
            rows = list(_res or [])
            _res = client.q(
                "SELECT count(*) FROM ("
                "  SELECT m.repo FROM ("
                "    SELECT DISTINCT repo FROM vertex_repo_record "
                "    WHERE collection = 'com.etzhayyim.apps.shinshi.modelProfile' "
                "      AND repo LIKE %s"
                "  ) m "
                "  LEFT JOIN ("
                "    SELECT repo, count(*) AS n FROM vertex_repo_record "
                "    WHERE collection = 'app.bsky.feed.post' "
                "      AND repo LIKE %s "
                "    GROUP BY repo"
                "  ) s ON s.repo = m.repo "
                f"  WHERE COALESCE(s.n, 0) < {bound_min}"
                ") t",
                (like_pat, like_pat),
            )
            r = (_res[0] if _res else None)
            total_incomplete = int(r[0]) if r else 0
    except Exception as e:  # noqa: BLE001
        return {"slugs": [], "totalIncomplete": 0, "checked": 0, "error": str(e)[:200]}

    slugs: list[str] = []
    for repo, _n in rows:
        if not isinstance(repo, str) or not repo.startswith(repo_prefix):
            continue
        slug = repo[len(repo_prefix):]
        if slug and not any(t in slug.lower() for t in ("test", "rkey-fix", "dummy")):
            slugs.append(slug)

    # Phase D2 (ADR-2605082000): embed routing decision so shinshi.canonical.v2
    # uses field-based conditional edges, retiring _route_after_find.
    return {
        "slugs": slugs,
        "totalIncomplete": total_incomplete,
        "checked": len(rows),
        "nextRoute": "bulk_seed" if slugs else "emit_audit",
    }


def register(worker: Any, timeout_ms: int = _RENDER_TIMEOUT_MS) -> None:
    worker.task(
        task_type="shinshi.scene.render",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_shinshi_scene_render)
    worker.task(
        task_type="shinshi.scene.bulkSeed",
        single_value=False,
        # 5 scenes × 3 slugs × ~25s each = ~375s; allow 15 min headroom
        timeout_ms=900_000,
    )(task_shinshi_scene_bulk_seed)
    worker.task(
        task_type="shinshi.coverage.findIncomplete",
        single_value=False,
        timeout_ms=60_000,
    )(task_shinshi_coverage_find_incomplete)
