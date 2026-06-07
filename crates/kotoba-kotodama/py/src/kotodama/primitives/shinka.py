"""Shinka LangServer task handlers.

These functions are the pod-side replacement for the old Zeebe task wrappers.
They intentionally depend only on kotodama.shinka and db_sync so the
LangServer/MCP path does not import deprecated broker clients.
"""

from __future__ import annotations

import json
import time
from typing import Any

from kotodama.primitives.shinka_murakumo import shinka_tick


def _now_ms() -> int:
    return int(time.time() * 1000)


async def task_shinka_tick(actor: str = "") -> dict[str, Any]:
    """Call shinka_murakumo.shinka_tick for one actor and return stable JSON fields."""
    if not actor:
        return {"error": "actor required"}
    try:
        raw = await shinka_tick(adherent_did=actor)
    except Exception as exc:  # noqa: BLE001
        return {"error": f"shinka_murakumo.shinka_tick failed: {exc}", "actor": actor}

    # The result from shinka_murakumo.shinka_tick is already a dict.
    # The original logic expected `row[0]` which could be a string (JSON) or a dict.
    # We will assume `shinka_tick` returns a dict, as per its docstring "Wire shape (output) is byte-compatible with vendor shinka_tick_actor JSON response".
    # This means 'raw' will always be a dict, effectively skipping the 'isinstance(raw, str)' branch.
    if isinstance(raw, str):
        try:
            tick: dict[str, Any] = json.loads(raw)
        except json.JSONDecodeError:
            tick = {"raw": raw}
    elif isinstance(raw, dict):
        tick = raw
    else:
        tick = {"raw": repr(raw)}

    return {
        "actor": tick.get("actor_did") or actor,
        "mood": tick.get("mood"),
        "actions": tick.get("actions") or [],
        "heartbeatWritten": bool(tick.get("heartbeat_written")),
        "evolutionWritten": bool(tick.get("evolution_written")),
        "knowledgeWritten": bool(tick.get("knowledge_written")),
        "tickMs": tick.get("tick_ms"),
    }


async def task_shinka_load_and_resolve(actorDid: str = "") -> dict[str, Any]:
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _load_state, _resolve_cadence

    state: dict[str, Any] = {"actor_did": actorDid, "now_ms": _now_ms()}
    state = _load_state(state)  # type: ignore[arg-type]
    state = _resolve_cadence(state)  # type: ignore[arg-type]
    return {
        "mood": state.get("mood"),
        "axes": state.get("axes"),
        "lastHeartbeatMs": state.get("last_heartbeat_ms"),
        "shouldPost": bool(state.get("should_post")),
        "shouldEngage": bool(state.get("should_engage")),
        "shouldDrill": bool(state.get("should_drill")),
        "shouldValidate": bool(state.get("should_validate")),
        "shouldAnalyze": bool(state.get("should_analyze")),
        "actions": state.get("actions", []),
        "followerDeltaCount": state.get("follower_delta_count", 0),
        "tickMs": state["now_ms"],
    }


async def task_shinka_compose(
    actorDid: str = "",
    mood: str = "neutral",
    axes: dict[str, Any] | None = None,
    actions: list[Any] | None = None,
    followerDeltaCount: int = 0,
) -> dict[str, Any]:
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _compose_content

    state = {
        "actor_did": actorDid,
        "now_ms": _now_ms(),
        "mood": mood,
        "axes": axes or {},
        "actions": actions or [],
        "follower_delta_count": int(followerDeltaCount or 0),
        "should_post": True,
    }
    state = _compose_content(state)  # type: ignore[arg-type]
    return {
        "draft": state.get("compose_draft"),
        "actions": state.get("actions", actions or []),
    }


async def task_shinka_write_heartbeat(
    actorDid: str = "",
    mood: str = "neutral",
    actions: list[Any] | None = None,
) -> dict[str, Any]:
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _write_heartbeat

    state = {
        "actor_did": actorDid,
        "now_ms": _now_ms(),
        "mood": mood,
        "actions": actions or [],
    }
    state = _write_heartbeat(state)  # type: ignore[arg-type]
    return {"heartbeatWritten": bool(state.get("heartbeat_written")), "tickMs": state["now_ms"]}


async def task_shinka_emit_evolution(
    actorDid: str = "",
    mood: str = "neutral",
    axes: dict[str, Any] | None = None,
    actions: list[Any] | None = None,
    followerDeltaCount: int = 0,
    draft: dict[str, Any] | None = None,
) -> dict[str, Any]:
    if not actorDid:
        return {"error": "actorDid is required"}
    from kotodama.shinka import _emit_evolution

    state = {
        "actor_did": actorDid,
        "now_ms": _now_ms(),
        "mood": mood,
        "axes": axes or {},
        "actions": actions or [],
        "follower_delta_count": int(followerDeltaCount or 0),
        "compose_draft": draft,
    }
    state = _emit_evolution(state)  # type: ignore[arg-type]
    return {"evolutionWritten": bool(state.get("evolution_written")), "tickMs": state["now_ms"]}
