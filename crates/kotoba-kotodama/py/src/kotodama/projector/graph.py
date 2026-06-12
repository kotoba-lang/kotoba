"""projector_lifecycle — LangGraph state machine for project lifecycle management.

State machine:
  init → planning → active → check_health
    ├─[open blockers]  → blocked  → wait_unblock → active (re-entry)
    └─[progress=1000]  → done     → END

Input shape (via /runs):
  {
    "project_id": "<vertex_id>",
    "action": "create|set_active|update_progress|force_done",
    "progress_permille": 0-1000,   # optional
    "lifecycle_state": "<state>",  # optional override
  }

ADR refs:
  2605082000-langgraph-graph-definition-as-data.md
  2605080600-langgraph-server-granian-l3-runtime.md
"""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Optional

import asyncpg
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

_log = logging.getLogger(__name__)

_DB_URL = os.getenv(
    "DATABASE_URL",
    "REDACTED_USE_DATABASE_URL_ENV",
)
_OWNER_DID = os.getenv("PROJECTOR_OWNER_DID", "did:web:projector.etzhayyim.com")


# ── State ──────────────────────────────────────────────────────────────────────

class ProjectorLifecycleState(TypedDict):
    project_id: str
    action: str
    progress_permille: int
    lifecycle_state: str
    open_blocker_count: int
    error: Optional[str]
    db_updated: bool


# ── DB helpers ─────────────────────────────────────────────────────────────────

async def _fetch_project(project_id: str) -> dict[str, Any] | None:
    conn = await asyncpg.connect(_DB_URL)
    try:
        row = await conn.fetchrow(
            """SELECT vertex_id, name, lifecycle_state, progress_permille
               FROM vertex_project_props WHERE vertex_id = $1""",
            project_id,
        )
        return dict(row) if row else None
    finally:
        await conn.close()


async def _count_open_blockers(project_id: str) -> int:
    conn = await asyncpg.connect(_DB_URL)
    try:
        row = await conn.fetchrow(
            "SELECT COUNT(*) AS cnt FROM vertex_projector_blocker WHERE project_id = $1 AND status = 'open'",
            project_id,
        )
        return int(row["cnt"]) if row else 0
    finally:
        await conn.close()


async def _update_project_state(project_id: str, lifecycle_state: str, progress_permille: int) -> None:
    conn = await asyncpg.connect(_DB_URL)
    try:
        await conn.execute(
            """UPDATE vertex_project_props
               SET lifecycle_state = $1, progress_permille = $2
               WHERE vertex_id = $3""",
            lifecycle_state, progress_permille, project_id,
        )
    finally:
        await conn.close()


# ── Graph nodes ────────────────────────────────────────────────────────────────

async def node_load_project(state: ProjectorLifecycleState) -> ProjectorLifecycleState:
    try:
        row = await _fetch_project(state["project_id"])
        if not row:
            return {**state, "error": f"project not found: {state['project_id']}"}
        return {
            **state,
            "lifecycle_state": row.get("lifecycle_state") or "planning",
            "progress_permille": row.get("progress_permille") or 0,
        }
    except Exception as e:
        _log.exception("[projector_lifecycle][load_project] failed")
        return {**state, "error": str(e)}


async def node_check_health(state: ProjectorLifecycleState) -> ProjectorLifecycleState:
    if state.get("error"):
        return state
    try:
        cnt = await _count_open_blockers(state["project_id"])
        return {**state, "open_blocker_count": cnt}
    except Exception as e:
        _log.exception("[projector_lifecycle][check_health] failed")
        return {**state, "error": str(e)}


async def node_transition(state: ProjectorLifecycleState) -> ProjectorLifecycleState:
    if state.get("error"):
        return state

    action = state.get("action", "")
    current = state.get("lifecycle_state", "planning")
    progress = state.get("progress_permille", 0)
    blockers = state.get("open_blocker_count", 0)

    next_state = current

    if action == "create":
        next_state = "planning"
    elif action == "set_active":
        if current in ("planning", "blocked"):
            next_state = "active" if blockers == 0 else "blocked"
    elif action == "update_progress":
        if progress >= 1000:
            next_state = "done"
        elif blockers > 0:
            next_state = "blocked"
        elif current == "blocked" and blockers == 0:
            next_state = "active"
    elif action == "force_done":
        next_state = "done"
        progress = 1000

    if next_state != current or progress != state.get("progress_permille", 0):
        try:
            await _update_project_state(state["project_id"], next_state, progress)
        except Exception as e:
            _log.exception("[projector_lifecycle][transition] db update failed")
            return {**state, "error": str(e)}

    return {**state, "lifecycle_state": next_state, "progress_permille": progress, "db_updated": True}


# ── Edge conditions ────────────────────────────────────────────────────────────

def route_after_transition(state: ProjectorLifecycleState) -> str:
    if state.get("error"):
        return END
    return END


# ── Graph builder ──────────────────────────────────────────────────────────────

def build_lifecycle_graph():
    g = StateGraph(ProjectorLifecycleState)

    g.add_node("load_project", node_load_project)
    g.add_node("check_health", node_check_health)
    g.add_node("transition", node_transition)

    g.set_entry_point("load_project")
    g.add_edge("load_project", "check_health")
    g.add_edge("check_health", "transition")
    g.add_conditional_edges("transition", route_after_transition)

    return g.compile()
