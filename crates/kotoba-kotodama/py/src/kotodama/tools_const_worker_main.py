"""Generic-primitive worker for com.etzhayyim.tools.const.* (ADR-2605082000 §2.6 follow-up).

Hosts identity / no-op tools that let LangGraph topology nodes stay data-only
without per-actor Python code. Today's surface:

  com.etzhayyim.tools.const.echo({"constant": {...}}) → {...}

The dispatcher convention (`kotodama.{actor}_worker_main:task_{snake}`) does
not apply here — the namespace is `com.etzhayyim.tools.const`, not
`com.etzhayyim.apps.<actor>`. Wire-up uses ``register_overrides`` in mcp_dispatch.
"""

from __future__ import annotations

from typing import Any


async def task_echo(*, constant: Any | None = None, **_ignored: Any) -> dict[str, Any]:
    """Echo the input `constant` verbatim as the response object.

    Returns ``constant`` as a dict (the MCP envelope requires dict). If the
    input is missing or not a dict, returns an explanatory error envelope —
    same shape as the rest of the saikin / ki tools.
    """
    if constant is None:
        return {"error": "com.etzhayyim.tools.const.echo: 'constant' is required"}
    if not isinstance(constant, dict):
        return {"error": "com.etzhayyim.tools.const.echo: 'constant' must be an object"}
    return dict(constant)
