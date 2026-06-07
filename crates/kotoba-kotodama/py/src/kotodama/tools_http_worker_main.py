"""Generic-primitive worker for com.etzhayyim.tools.http.* (ADR-2605082000 §2 follow-up).

Read-only HTTP fetch. Write methods (POST/PUT/DELETE) require an explicit
`allowWrite=true` flag — defense-in-depth against accidental side-effects.

Wired into mcp_dispatch via ``register_overrides``.
"""

from __future__ import annotations

import base64
from typing import Any

_READ_METHODS = {"GET", "HEAD", "OPTIONS"}
_WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}
_DEFAULT_TIMEOUT = 30.0


def _is_text_content(content_type: str) -> bool:
    if not content_type:
        return False
    ct = content_type.lower()
    return (
        ct.startswith("text/")
        or "json" in ct
        or "xml" in ct
        or ct.startswith("application/javascript")
    )


async def task_http_fetch(
    *,
    url: str = "",
    method: str = "GET",
    headers: dict[str, str] | None = None,
    body: str | None = None,
    timeout: float | int | None = None,
    allowWrite: bool = False,
    **_ignored: Any,
) -> dict[str, Any]:
    """Run an outbound HTTP request via httpx and return a JSON-safe envelope.

    Returns ``{"error": ...}`` on rejection / failure. Binary responses are
    base64-encoded under ``body`` with ``isText: false`` so the envelope
    stays JSON-serializable.
    """
    if not url:
        return {"error": "com.etzhayyim.tools.http.fetch: url required"}
    m = (method or "GET").upper()
    if m not in _READ_METHODS and m not in _WRITE_METHODS:
        return {"error": f"unsupported method {m!r}"}
    if m in _WRITE_METHODS and not allowWrite:
        return {"error": f"method {m!r} requires allowWrite=true"}

    to = float(timeout) if timeout is not None else _DEFAULT_TIMEOUT
    try:
        import httpx
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"httpx unavailable: {exc}"}

    try:
        async with httpx.AsyncClient(timeout=to) as client:
            kwargs: dict[str, Any] = {"headers": headers or {}}
            if body is not None and m in _WRITE_METHODS:
                kwargs["content"] = body
            resp = await client.request(m, url, **kwargs)
    except Exception as exc:  # pragma: no cover — defensive
        return {"error": f"http_fetch failed: {exc}"}

    raw = resp.content
    ct = resp.headers.get("content-type", "")
    is_text = _is_text_content(ct)
    if is_text:
        try:
            body_str = raw.decode(resp.encoding or "utf-8", errors="replace")
        except Exception:
            body_str = raw.decode("utf-8", errors="replace")
    else:
        body_str = base64.b64encode(raw).decode("ascii")

    return {
        "status": int(resp.status_code),
        "headers": {k.lower(): v for k, v in resp.headers.items()},
        "body": body_str,
        "isText": is_text,
    }
