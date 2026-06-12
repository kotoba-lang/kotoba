"""ge.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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
_ACTOR = os.getenv("GE_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"ge-{safe}.db"


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS vertex_ge_org (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    country         TEXT NOT NULL DEFAULT '',
    industry        TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_ge_project (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    org_id          TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_ge_resource_assignment (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    project_id      TEXT NOT NULL DEFAULT '',
    resource_did    TEXT NOT NULL DEFAULT '',
    role            TEXT NOT NULL DEFAULT '',
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

def _create_org_sync(name: str, country: str, industry: str, owner_did: str, actor: str) -> dict[str, Any]:
    org_id = str(uuid.uuid4())
    vertex_id = f"ge:org:{org_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_ge_org
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, name, country, industry, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             org_id, name, country, industry, "active",
             "did:web:ge.etzhayyim.com", "did:web:ge.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"orgId": org_id, "status": "active"}


def _list_orgs_sync(limit: int, offset: int, country: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if country:
            rows = conn.execute(
                "SELECT id, name, country, industry, status, created_at "
                "FROM vertex_ge_org WHERE country = ? LIMIT ? OFFSET ?",
                (country, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_ge_org WHERE country = ?",
                (country,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, name, country, industry, status, created_at "
                "FROM vertex_ge_org LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM vertex_ge_org").fetchone()[0]
            
    return {
        "orgs": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _create_project_sync(org_id: str, name: str, description: str, owner_did: str, actor: str) -> dict[str, Any]:
    project_id = str(uuid.uuid4())
    vertex_id = f"ge:project:{project_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_ge_project
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, org_id, name, description, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             project_id, org_id, name, description, "active",
             "did:web:ge.etzhayyim.com", "did:web:ge.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"projectId": project_id, "status": "active"}


def _list_projects_sync(limit: int, offset: int, org_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if org_id:
            rows = conn.execute(
                "SELECT id, org_id, name, description, status, created_at "
                "FROM vertex_ge_project WHERE org_id = ? LIMIT ? OFFSET ?",
                (org_id, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_ge_project WHERE org_id = ?",
                (org_id,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, org_id, name, description, status, created_at "
                "FROM vertex_ge_project LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM vertex_ge_project").fetchone()[0]
            
    return {
        "projects": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _assign_resource_sync(project_id: str, resource_did: str, role: str, owner_did: str, actor: str) -> dict[str, Any]:
    assignment_id = str(uuid.uuid4())
    vertex_id = f"ge:resource_assignment:{assignment_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_ge_resource_assignment
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, project_id, resource_did, role, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             assignment_id, project_id, resource_did, role, "assigned",
             "did:web:ge.etzhayyim.com", "did:web:ge.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"assignmentId": assignment_id, "status": "assigned"}


def _list_resources_sync(limit: int, offset: int, project_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if project_id:
            rows = conn.execute(
                "SELECT id, project_id, resource_did, role, status, created_at "
                "FROM vertex_ge_resource_assignment WHERE project_id = ? LIMIT ? OFFSET ?",
                (project_id, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_ge_resource_assignment WHERE project_id = ?",
                (project_id,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, project_id, resource_did, role, status, created_at "
                "FROM vertex_ge_resource_assignment LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM vertex_ge_resource_assignment").fetchone()[0]
            
    return {
        "resources": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _get_org_metrics_sync(org_id: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    with _open(actor) as conn:
        project_count = conn.execute(
            "SELECT COUNT(*) FROM vertex_ge_project WHERE org_id = ?",
            (org_id,)
        ).fetchone()[0]
        resource_count = conn.execute(
            "SELECT COUNT(*) FROM vertex_ge_resource_assignment ra "
            "JOIN vertex_ge_project p ON ra.project_id = p.id WHERE p.org_id = ?",
            (org_id,)
        ).fetchone()[0]
        
    return {
        "orgId": org_id,
        "projectCount": project_count,
        "resourceCount": resource_count,
        "computedAt": now,
    }


def _plan_workforce_sync(org_id: str, target_headcount: int, horizon_months: int, actor: str) -> dict[str, Any]:
    # stub handler
    return {
        "planId": str(uuid.uuid4()),
        "orgId": org_id,
        "targetHeadcount": target_headcount,
        "horizonMonths": horizon_months,
        "recommendations": [],
        "createdAt": datetime.utcnow().isoformat(),
    }


# ---------------------------------------------------------------------------
# Worker & Tasks
# ---------------------------------------------------------------------------

async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.ge.createOrg")
    async def task_create_org(**kwargs):
        return await asyncio.to_thread(
            _create_org_sync,
            kwargs.get("name", ""),
            kwargs.get("country", ""),
            kwargs.get("industry", ""),
            kwargs.get("ownerDid", "did:web:ge.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.ge.listOrgs")
    async def task_list_orgs(**kwargs):
        return await asyncio.to_thread(
            _list_orgs_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("country", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.ge.createProject")
    async def task_create_project(**kwargs):
        return await asyncio.to_thread(
            _create_project_sync,
            kwargs.get("orgId", ""),
            kwargs.get("name", ""),
            kwargs.get("description", ""),
            kwargs.get("ownerDid", "did:web:ge.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.ge.listProjects")
    async def task_list_projects(**kwargs):
        return await asyncio.to_thread(
            _list_projects_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("orgId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.ge.assignResource")
    async def task_assign_resource(**kwargs):
        return await asyncio.to_thread(
            _assign_resource_sync,
            kwargs.get("projectId", ""),
            kwargs.get("resourceDid", ""),
            kwargs.get("role", "member"),
            kwargs.get("ownerDid", "did:web:ge.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.ge.listResources")
    async def task_list_resources(**kwargs):
        return await asyncio.to_thread(
            _list_resources_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("projectId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.ge.getOrgMetrics")
    async def task_get_org_metrics(**kwargs):
        return await asyncio.to_thread(
            _get_org_metrics_sync,
            kwargs.get("orgId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.ge.planWorkforce")
    async def task_plan_workforce(**kwargs):
        return await asyncio.to_thread(
            _plan_workforce_sync,
            kwargs.get("orgId", ""),
            int(kwargs.get("targetHeadcount", 0)),
            int(kwargs.get("horizonMonths", 12)),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
