"""blocker_pregel — Pregel BSP propagation for project blockers.

When a project gains or loses a blocker, this runs up to 2 supersteps to
propagate `blocked` / `unblocked` state to dependent projects.

Superstep 0: mark direct upstream dependents (projects that depend ON the
             changed project via edge_projector_project_dep dst→src).
Superstep 1: propagate one more hop.

ADR refs:
  2605131800-pregel-triage-pipeline.md
"""
from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg

_log = logging.getLogger(__name__)

_DB_URL = os.getenv(
    "DATABASE_URL",
    "REDACTED_USE_DATABASE_URL_ENV",
)

MAX_SUPERSTEPS = 2


async def run_blocker_propagation(project_id: str, action: str) -> int:
    """Propagate blocker state across project dependency edges.

    action: "add" (project became blocked) | "resolve" (blocker resolved)
    Returns the count of projects whose lifecycle_state was updated.
    """
    conn = await asyncpg.connect(_DB_URL)
    try:
        return await _pregel_pass(conn, project_id, action)
    finally:
        await conn.close()


async def _pregel_pass(conn: asyncpg.Connection, root_id: str, action: str) -> int:
    frontier = {root_id}
    updated = 0

    for _step in range(MAX_SUPERSTEPS):
        if not frontier:
            break

        # Find projects that depend ON any project in frontier (dst_vid = frontier member)
        placeholders = ", ".join(f"${i+1}" for i in range(len(frontier)))
        rows = await conn.fetch(
            f"SELECT DISTINCT src_vid FROM edge_projector_project_dep WHERE dst_vid IN ({placeholders})",
            *list(frontier),
        )
        dependents = {r["src_vid"] for r in rows} - frontier

        if not dependents:
            break

        next_frontier = set()
        for dep_id in dependents:
            changed = await _apply_signal(conn, dep_id, action)
            if changed:
                updated += 1
                next_frontier.add(dep_id)

        frontier = next_frontier

    return updated


async def _apply_signal(conn: asyncpg.Connection, project_id: str, action: str) -> bool:
    """Update lifecycle_state for a dependent project if warranted.

    Returns True if a state change was written.
    """
    row = await conn.fetchrow(
        "SELECT lifecycle_state FROM vertex_project_props WHERE vertex_id = $1",
        project_id,
    )
    if not row:
        return False

    current = row["lifecycle_state"] or "planning"

    if action == "add" and current == "active":
        await conn.execute(
            "UPDATE vertex_project_props SET lifecycle_state = 'blocked' WHERE vertex_id = $1",
            project_id,
        )
        _log.info("[blocker_pregel] project=%s active→blocked (dep blocked)", project_id)
        return True

    if action == "resolve" and current == "blocked":
        # Only unblock if this project has no remaining open blockers of its own
        cnt = await conn.fetchval(
            "SELECT COUNT(*) FROM vertex_projector_blocker WHERE project_id = $1 AND status = 'open'",
            project_id,
        )
        if int(cnt or 0) == 0:
            await conn.execute(
                "UPDATE vertex_project_props SET lifecycle_state = 'active' WHERE vertex_id = $1",
                project_id,
            )
            _log.info("[blocker_pregel] project=%s blocked→active (dep unblocked)", project_id)
            return True

    return False
