"""HTTP clients for the RunPod 6000 Ada unified pod (ADR-2605010000 +
ADR-2605080700 addendum).

Two endpoints share the same pod (`vyp99t9px7h4dl`):

  - TRELLIS  (FastAPI)  — ``RUNPOD_TRELLIS_URL`` (default
      ``https://vyp99t9px7h4dl-5000.proxy.runpod.net``).  POST /generate
      ``{prompt | image_url, params}`` → ``{glb_b64, polygon_count,
      vertex_count}``.
  - ComfyUI  (HTTP)     — ``RUNPOD_COMFYUI_URL`` (default
      ``https://vyp99t9px7h4dl-8188.proxy.runpod.net``).  Workflow
      submitted via ``/prompt`` then polled via ``/history/{prompt_id}``.

These clients are thin: they convert primitive args to the underlying
HTTP payload and return raw GLB bytes plus polygon / vertex counts.  All
domain logic stays in ``graph.py``.

Phase A (ADR-2605080700) keeps the ComfyUI path as a stub that 501s if
called.  TRELLIS is the live path.  The CadQuery path (no RunPod) lives
in ``converters.py``.
"""

from __future__ import annotations

import base64
import json
import os
import time
import urllib.error
import urllib.request


_TRELLIS_BASE_DEFAULT = "https://vyp99t9px7h4dl-5000.proxy.runpod.net"
_COMFY_BASE_DEFAULT = "https://vyp99t9px7h4dl-8188.proxy.runpod.net"
_TRELLIS_TIMEOUT = float(os.environ.get("RUNPOD_TRELLIS_TIMEOUT_SEC", "180"))


def call_trellis(
    prompt: str | None,
    image_url: str | None,
    params: dict,
) -> tuple[bytes, int | None, int | None]:
    """POST to the TRELLIS server, return ``(glb_bytes, polys, verts)``.

    Phase A wire-format (subject to change in TRELLIS server PR):

        POST /generate
        {"prompt": str | null, "image_url": str | null, "params": {...}}
        → {"glb_b64": "...", "polygon_count": int, "vertex_count": int}
    """

    base = os.environ.get("RUNPOD_TRELLIS_URL", _TRELLIS_BASE_DEFAULT).rstrip("/")
    body = json.dumps(
        {
            "prompt": prompt,
            "image_url": image_url,
            "params": params,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/generate",
        data=body,
        method="POST",
        headers={"content-type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=_TRELLIS_TIMEOUT) as resp:
            payload = json.loads(resp.read())
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"TRELLIS HTTP {e.code}: {e.read()[:200]!r}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"TRELLIS unreachable: {e}") from e

    glb_b64 = payload.get("glb_b64") or payload.get("glb")
    if not glb_b64:
        raise RuntimeError(f"TRELLIS response missing glb_b64: {payload!r}")
    glb = base64.b64decode(glb_b64)
    return glb, payload.get("polygon_count"), payload.get("vertex_count")


def call_comfyui_3d(
    image_url: str | None,
    params: dict,
) -> tuple[bytes, int | None, int | None]:
    """ComfyUI-3D-Pack image→3D path. Phase A: stub.

    Real implementation requires a workflow JSON template + ``/prompt``
    submission + ``/history/{prompt_id}`` polling + node-output GLB
    download. Tracked in ADR-2605080700 Phase B follow-up.
    """

    raise NotImplementedError(
        "ComfyUI 3D-Pack path not enabled in Phase A. "
        "Use kind=text or kind=image with default generator (TRELLIS)."
    )


def runpod_pod_id() -> str:
    """Best-effort canonical pod id for billing / observability."""

    base = os.environ.get("RUNPOD_TRELLIS_URL", _TRELLIS_BASE_DEFAULT)
    # https://{podId}-{port}.proxy.runpod.net
    try:
        host = base.split("://", 1)[1].split(".", 1)[0]
        return host.rsplit("-", 1)[0]
    except Exception:
        return "unknown"


def _now_ms() -> int:
    return int(time.time() * 1000)
