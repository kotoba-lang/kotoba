"""resources.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("RESOURCES_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"resources-{safe}.db"


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS vertex_resources_resource (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    kind            TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_resources_allocation (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    resource_id     TEXT NOT NULL DEFAULT '',
    requester_did   TEXT NOT NULL DEFAULT '',
    quantity        INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);
"""

def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def _open(actor: str = _ACTOR) -> sqlite3.Connection:
    path = _db_path(actor)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn


# ---------------------------------------------------------------------------
# Synchronous helpers
# ---------------------------------------------------------------------------

def _create_resource_sync(name: str, kind: str, owner_did: str, actor: str) -> dict[str, Any]:
    resource_id = str(uuid.uuid4())
    vertex_id = f"resources:resource:{resource_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_resources_resource
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, name, kind, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             resource_id, name, kind, "active",
             "did:web:resources.etzhayyim.com", "did:web:resources.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"id": resource_id, "status": "active", "createdAt": now}


def _get_resource_sync(resource_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, name, kind, status, created_at, updated_at "
            "FROM vertex_resources_resource WHERE id = ?",
            (resource_id,)
        ).fetchone()

    if not row:
        return {"error": "not found"}
    return dict(row)


def _update_resource_sync(resource_id: str, name: str, status: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_resources_resource SET name = ?, status = ?, updated_at = ? WHERE id = ?",
            (name, status, now, resource_id)
        )
        conn.commit()

    return {"id": resource_id, "status": status, "updatedAt": now}


def _delete_resource_sync(resource_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        conn.execute(
            "DELETE FROM vertex_resources_resource WHERE id = ?",
            (resource_id,)
        )
        conn.commit()

    return {"id": resource_id, "deleted": True}


def _list_resources_sync(kind: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if kind:
            rows = conn.execute(
                "SELECT id, name, kind, status, created_at FROM vertex_resources_resource "
                "WHERE kind = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (kind, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_resources_resource WHERE kind = ?",
                (kind,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, name, kind, status, created_at FROM vertex_resources_resource "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_resources_resource"
            ).fetchone()[0]

    return {
        "resources": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _allocate_resource_sync(resource_id: str, requester_did: str, quantity: int, actor: str) -> dict[str, Any]:
    allocation_id = str(uuid.uuid4())
    vertex_id = f"resources:allocation:{allocation_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_resources_allocation
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, resource_id, requester_did, quantity, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, requester_did,
             allocation_id, resource_id, requester_did, quantity, "allocated",
             "did:web:resources.etzhayyim.com", "did:web:resources.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"allocationId": allocation_id, "resourceId": resource_id, "status": "allocated"}


def _release_resource_sync(allocation_id: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_resources_allocation SET status = 'released', updated_at = ? WHERE id = ?",
            (now, allocation_id)
        )
        conn.commit()

    return {"allocationId": allocation_id, "status": "released", "releasedAt": now}


def _resource_usage_sync(resource_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT COUNT(*) AS total_allocations FROM vertex_resources_allocation WHERE resource_id = ?",
            (resource_id,)
        ).fetchone()
        active_row = conn.execute(
            "SELECT COUNT(*) AS active_allocations FROM vertex_resources_allocation "
            "WHERE resource_id = ? AND status = 'allocated'",
            (resource_id,)
        ).fetchone()

    return {
        "resourceId": resource_id,
        "totalAllocations": row["total_allocations"] if row else 0,
        "activeAllocations": active_row["active_allocations"] if active_row else 0,
    }


# ---------------------------------------------------------------------------
# Worker & Tasks
# ---------------------------------------------------------------------------

async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.resources.createResource")
    async def task_create_resource(**kwargs):
        return await asyncio.to_thread(
            _create_resource_sync,
            kwargs.get("name", ""),
            kwargs.get("kind", ""),
            kwargs.get("ownerDid", "did:web:resources.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.resources.getResource")
    async def task_get_resource(**kwargs):
        return await asyncio.to_thread(
            _get_resource_sync,
            kwargs.get("id", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.resources.updateResource")
    async def task_update_resource(**kwargs):
        return await asyncio.to_thread(
            _update_resource_sync,
            kwargs.get("id", ""),
            kwargs.get("name", ""),
            kwargs.get("status", "active"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.resources.deleteResource")
    async def task_delete_resource(**kwargs):
        return await asyncio.to_thread(
            _delete_resource_sync,
            kwargs.get("id", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.resources.listResources")
    async def task_list_resources(**kwargs):
        return await asyncio.to_thread(
            _list_resources_sync,
            kwargs.get("kind", ""),
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.resources.allocateResource")
    async def task_allocate_resource(**kwargs):
        return await asyncio.to_thread(
            _allocate_resource_sync,
            kwargs.get("resourceId", ""),
            kwargs.get("requesterDid", ""),
            int(kwargs.get("quantity", 1)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.resources.releaseResource")
    async def task_release_resource(**kwargs):
        return await asyncio.to_thread(
            _release_resource_sync,
            kwargs.get("allocationId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.resources.resourceUsage")
    async def task_resource_usage(**kwargs):
        return await asyncio.to_thread(
            _resource_usage_sync,
            kwargs.get("resourceId", ""),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
