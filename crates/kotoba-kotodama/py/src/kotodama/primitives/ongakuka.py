"""
ongakuka.etzhayyim.com — Zeebe primitive for AI music generation.

Env vars:
  SS_MURAKUMO_API_KEY    Murakumo service API key
  B2_ACCESS_KEY_ID       Backblaze B2 application key ID
  B2_SECRET_ACCESS_KEY   Backblaze B2 application key
  B2_ENDPOINT            B2 S3-compatible endpoint (default: https://s3.us-west-004.backblazeb2.com)
  B2_REGION              B2 region (default: us-west-004)
"""

from __future__ import annotations

import hashlib
import hmac
import os
import time
import json
import urllib.request as _req
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

_MURAKUMO_BASE_URL = os.environ.get("MURAKUMO_BASE_URL", "https://murakumo-serve.etzhayyim.com").rstrip("/")
_MURAKUMO_API_KEY  = os.environ.get("SS_MURAKUMO_API_KEY", "").strip()
_MURAKUMO_MODEL    = "musicgen-small"

_B2_BUCKET   = "etzhayyim-ongakuka"
_B2_KEY_ID   = os.environ.get("B2_ACCESS_KEY_ID",    "").strip()
_B2_KEY      = os.environ.get("B2_SECRET_ACCESS_KEY","").strip()
_B2_ENDPOINT = os.environ.get("B2_ENDPOINT", "https://s3.us-west-004.backblazeb2.com").rstrip("/")
_B2_REGION   = os.environ.get("B2_REGION",   "us-west-004")

_OWNER_DID      = "did:web:ongakuka.etzhayyim.com"
_COMPOSER_DID   = "did:web:ongakuka.etzhayyim.com:actor:composer"


# ---------------------------------------------------------------------------
# B2 helpers (AWS Sig V4 — no boto3, same pattern as training_export.py)
# ---------------------------------------------------------------------------

def _b2_put(key: str, data: bytes, content_type: str = "audio/wav") -> str:
    if not _B2_KEY_ID or not _B2_KEY:
        raise RuntimeError("B2_ACCESS_KEY_ID / B2_SECRET_ACCESS_KEY not set")
    url  = f"{_B2_ENDPOINT}/{_B2_BUCKET}/{key}"
    now  = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    date = now[:8]
    host = _B2_ENDPOINT.replace("https://", "").replace("http://", "")
    ph   = hashlib.sha256(data).hexdigest()
    ch   = f"content-type:{content_type}\nhost:{host}\nx-amz-content-sha256:{ph}\nx-amz-date:{now}\n"
    sh   = "content-type;host;x-amz-content-sha256;x-amz-date"
    cr   = f"PUT\n/{_B2_BUCKET}/{key}\n\n{ch}\n{sh}\n{ph}"
    scope = f"{date}/{_B2_REGION}/s3/aws4_request"
    sts   = f"AWS4-HMAC-SHA256\n{now}\n{scope}\n" + hashlib.sha256(cr.encode()).hexdigest()

    def _sign(k: bytes, msg: str) -> bytes:
        return hmac.new(k, msg.encode(), hashlib.sha256).digest()

    sk  = _sign(_sign(_sign(_sign(f"AWS4{_B2_KEY}".encode(), date), _B2_REGION), "s3"), "aws4_request")
    sig = hmac.new(sk, sts.encode(), hashlib.sha256).hexdigest()
    auth = (
        f"AWS4-HMAC-SHA256 Credential={_B2_KEY_ID}/{scope},"
        f" SignedHeaders={sh},"
        f" Signature={sig}"
    )
    req = _req.Request(url, data=data, method="PUT", headers={
        "Content-Type": content_type,
        "x-amz-date": now,
        "x-amz-content-sha256": ph,
        "Authorization": auth,
    })
    with _req.urlopen(req, timeout=120) as resp:
        resp.read()
    return f"s3://{_B2_BUCKET}/{key}"


def _b2_head(key: str) -> bool:
    """Return True if key exists in B2."""
    if not _B2_KEY_ID or not _B2_KEY:
        return False
    url  = f"{_B2_ENDPOINT}/{_B2_BUCKET}/{key}"
    now  = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    date = now[:8]
    host = _B2_ENDPOINT.replace("https://", "").replace("http://", "")
    ph   = "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    ch   = f"host:{host}\nx-amz-content-sha256:{ph}\nx-amz-date:{now}\n"
    sh   = "host;x-amz-content-sha256;x-amz-date"
    cr   = f"HEAD\n/{_B2_BUCKET}/{key}\n\n{ch}\n{sh}\n{ph}"
    scope = f"{date}/{_B2_REGION}/s3/aws4_request"
    sts   = f"AWS4-HMAC-SHA256\n{now}\n{scope}\n" + hashlib.sha256(cr.encode()).hexdigest()

    def _sign(k: bytes, msg: str) -> bytes:
        return hmac.new(k, msg.encode(), hashlib.sha256).digest()

    sk  = _sign(_sign(_sign(_sign(f"AWS4{_B2_KEY}".encode(), date), _B2_REGION), "s3"), "aws4_request")
    sig = hmac.new(sk, sts.encode(), hashlib.sha256).hexdigest()
    auth = (
        f"AWS4-HMAC-SHA256 Credential={_B2_KEY_ID}/{scope},"
        f" SignedHeaders={sh},"
        f" Signature={sig}"
    )
    req = _req.Request(url, method="HEAD", headers={
        "x-amz-date": now,
        "x-amz-content-sha256": ph,
        "Authorization": auth,
    })
    try:
        with _req.urlopen(req, timeout=30):
            return True
    except Exception:
        return False


# ---------------------------------------------------------------------------
# Murakumo audio helper
# ---------------------------------------------------------------------------

def _call_murakumo_music(
    prompt: str,
    duration_sec: int,
    seed: int | None,
) -> dict[str, Any]:
    """Call murakumo audio API; retries up to 8x for 404/5xx node misses."""
    api_key = _MURAKUMO_API_KEY
    last_err: str = ""
    for attempt in range(8):
        try:
            payload = json.dumps({
                "model": _MURAKUMO_MODEL,
                "prompt": prompt,
                "duration_sec": duration_sec,
                "seed": seed,
            }).encode()
            headers: dict[str, str] = {"Content-Type": "application/json"}
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"
            req = _req.Request(
                f"{_MURAKUMO_BASE_URL}/api/audio/v1/music/generations",
                data=payload, method="POST", headers=headers,
            )
            with _req.urlopen(req, timeout=90) as resp:
                wav = resp.read()
                return {
                    "wav": wav,
                    "inference_ms": int(resp.headers.get("x-inference-ms") or 0),
                    "node": resp.headers.get("x-node") or "unknown",
                    "sample_rate": int(resp.headers.get("x-sample-rate") or 32000),
                }
        except Exception as exc:
            last_err = str(exc)
            status = getattr(exc, "code", 0)
            if status not in (0, 404, 502, 503, 522, 524):
                raise
            time.sleep(2 ** attempt * 0.5)
    raise RuntimeError(f"murakumo audio exhausted retries (last={last_err})")


# ---------------------------------------------------------------------------
# Zeebe task
# ---------------------------------------------------------------------------

def task_ongakuka_music_generate(
    style:       str = "",
    title:       str = "",
    duration_sec: int = 15,
    seed:        int = 0,
    project_id:  str = "",
    track_rkey:  str = "",
    pre_gen_sha: str = "",
) -> dict[str, Any]:
    """
    Zeebe: generate one music track (or use pre-uploaded B2 blob) and persist
    the track record + generation audit row.

    Returns {track_rkey, blob_key, audio_url, duration_sec, inference_ms, status}.
    """
    if not style and not pre_gen_sha:
        raise ValueError("style or pre_gen_sha is required")

    duration_sec = max(5, min(30, duration_sec or 15))
    seed_val     = seed or None
    t0           = time.time()

    # -- audio generation or pre-upload bypass --------------------------------
    if pre_gen_sha:
        sha          = pre_gen_sha
        inference_ms = 0
        node         = "preGenerated"
        sample_rate  = 32000
        if not _b2_head(f"ongakuka/tracks/{sha}.wav"):
            raise RuntimeError(f"pre_gen_sha {sha} not found in B2")
    else:
        result = _call_murakumo_music(style, duration_sec, seed_val)
        wav    = result["wav"]
        sha    = hashlib.sha256(wav).hexdigest()
        inference_ms = result["inference_ms"]
        node         = result["node"]
        sample_rate  = result["sample_rate"]
        obj_key = f"ongakuka/tracks/{sha}.wav"
        if not _b2_head(obj_key):
            _b2_put(obj_key, wav, "audio/wav")

    audio_url = f"https://ongakuka.etzhayyim.com/blobs/{sha}.wav"
    now_iso   = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    wall_ms   = int((time.time() - t0) * 1000)

    track_title = title or f"Track {now_iso[:16]}"

    # -- kotoba Datom log writes ----------------------------------------------
    # T2 domain: vertex_ongakuka_track
    track_vid = f"at://{_OWNER_DID}/com.etzhayyim.apps.ongakuka.track/{track_rkey}"
    get_kotoba_client().insert_row(
        "vertex_ongakuka_track",
        {
            "vertex_id":   track_vid,
            "title":       track_title,
            "style":       style,
            "duration_sec": duration_sec,
            "blob_key":    sha,
            "mime_type":   "audio/wav",
            "status":      "published",
            "project_id":  project_id,
            "model_id":    _MURAKUMO_MODEL,
            "seed":        seed or 0,
            "created_at":  now_iso,
        },
    )

    # T2 domain: vertex_ongakuka_generation
    gen_rkey = f"gen-{track_rkey}"
    gen_vid  = f"at://{_COMPOSER_DID}/com.etzhayyim.apps.ongakuka.generation/{gen_rkey}"
    get_kotoba_client().insert_row(
        "vertex_ongakuka_generation",
        {
            "vertex_id":  gen_vid,
            "target_uri": track_vid,
            "stage":      "compose",
            "actor_did":  _COMPOSER_DID,
            "model_id":   _MURAKUMO_MODEL,
            "params":     json.dumps({"prompt": style, "duration_sec": duration_sec,
                                       "seed": seed or None, "sample_rate": sample_rate}),
            "audio_sec":     duration_sec,
            "inference_ms":  inference_ms,
            "node":          node,
            "status":        "ok",
            "created_at":    now_iso,
        },
    )

    # -- T1 social post (C-path via vertex_repo_record) -----------------------
    from kotodama.primitives.yoro_social import insert_social_post_record  # local import
    import secrets as _sec

    post_rkey = f"ongakuka-{track_rkey[:12]}-{_sec.token_hex(4)}"
    post_text = f'New music track: "{track_title}" ({duration_sec}s, {_MURAKUMO_MODEL}) {audio_url}'
    insert_social_post_record({
        "uri":        f"at://{_OWNER_DID}/app.bsky.feed.post/{post_rkey}",
        "cid":        "",
        "collection": "app.bsky.feed.post",
        "rkey":       post_rkey,
        "repo":       _OWNER_DID,
        "repo_rev":   "",
        "value_json": json.dumps({
            "$type":     "app.bsky.feed.post",
            "text":      post_text,
            "createdAt": now_iso,
            "embed": {
                "$type": "app.bsky.embed.external",
                "external": {
                    "uri":         audio_url,
                    "title":       f"Track: {track_title}",
                    "description": f"{duration_sec}s instrumental — {_MURAKUMO_MODEL} — ongakuka.etzhayyim.com",
                },
            },
        }),
        "indexed_at":  now_iso,
        "takedown_ref": None,
        "ts_ms":       int(time.time() * 1000),
        "created_at":  now_iso,
        "text":        post_text,
    }, flush=False)

    return {
        "track_rkey":   track_rkey,
        "blob_key":     sha,
        "audio_url":    audio_url,
        "duration_sec": duration_sec,
        "inference_ms": inference_ms,
        "wall_ms":      wall_ms,
        "node":         node,
        "status":       "published",
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="ongakuka.music.generate",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_ongakuka_music_generate)


__all__ = ["register", "task_ongakuka_music_generate"]
