"""Generic-primitive worker for com.etzhayyim.tools.time.* (ADR-2605082000 Phase D).

Stateless wall-clock readout. Replaces per-actor inline ``time.time()`` /
``datetime.now(tz=...)`` py_primitive nodes.

Surface:

  com.etzhayyim.tools.time.now({"format": "iso"|"epoch_s"|"epoch_ms",
                          "tz": "UTC"|"Asia/Tokyo"|...})
    → {"now": <str|int|float>}

The dispatcher convention does not apply here — namespace is
``com.etzhayyim.tools.time``, wired via ``register_overrides`` in mcp_dispatch.
"""

from __future__ import annotations

import time
from datetime import datetime, timezone
from typing import Any

_FORMATS = ("iso", "epoch_s", "epoch_ms")


async def task_time_now(
    *,
    format: str = "iso",
    tz: str = "UTC",
    **_ignored: Any,
) -> dict[str, Any]:
    """Return the current time in the requested format.

    ``format`` ∈ {"iso", "epoch_s", "epoch_ms"}.
    ``tz`` is honored for ``iso`` only (epoch is timezone-agnostic).
    Unknown tz falls back to UTC with an ``error`` field added.
    """
    if format not in _FORMATS:
        return {"error": f"format must be one of {_FORMATS}, got {format!r}"}

    if format == "epoch_s":
        return {"now": time.time()}
    if format == "epoch_ms":
        return {"now": int(time.time() * 1000)}

    # iso
    tzinfo: Any = timezone.utc
    err: str | None = None
    if tz and tz != "UTC":
        try:
            from zoneinfo import ZoneInfo
            tzinfo = ZoneInfo(tz)
        except Exception as exc:
            err = f"unknown tz {tz!r}: {exc}; falling back to UTC"
            tzinfo = timezone.utc
    out = {"now": datetime.now(tz=tzinfo).isoformat()}
    if err:
        out["error"] = err
    return out
