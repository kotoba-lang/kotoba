"""web4.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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
_ACTOR = os.getenv("WEB4_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"web4-{safe}.db"


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS vertex_web4_expert (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    did             TEXT NOT NULL DEFAULT '',
    specialization  TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_web4_inference_job (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    expert_id       TEXT NOT NULL DEFAULT '',
    model           TEXT NOT NULL DEFAULT '',
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

def _create_expert_sync(name: str, did: str, specialization: str, actor: str) -> dict[str, Any]:
    expert_id = str(uuid.uuid4())
    vertex_id = f"web4:expert:{expert_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_web4_expert
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, name, did, specialization, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, did,
             expert_id, name, did, specialization, "active",
             "did:web:web4.etzhayyim.com", "did:web:web4.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"expertId": expert_id, "status": "active"}


def _list_experts_sync(limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, name, did, specialization, status, created_at "
            "FROM vertex_web4_expert LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        
    return {
        "experts": [dict(r) for r in rows],
        "offset": offset,
        "limit": limit,
    }


def _submit_inference_sync(expert_id: str, model: str, input_data: dict, actor: str) -> dict[str, Any]:
    job_id = str(uuid.uuid4())
    vertex_id = f"web4:inference_job:{job_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_web4_inference_job
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, expert_id, model, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, "did:web:web4.etzhayyim.com",
             job_id, expert_id, model, "pending",
             "did:web:web4.etzhayyim.com", "did:web:web4.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"jobId": job_id, "status": "pending"}


def _get_inference_result_sync(job_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, expert_id, model, status, created_at FROM vertex_web4_inference_job WHERE id = ?",
            (job_id,)
        ).fetchone()
        
    if not row:
        return {"error": "not found"}
    return dict(row)


def _list_jobs_sync(limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, expert_id, model, status, created_at FROM vertex_web4_inference_job LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        
    return {
        "jobs": [dict(r) for r in rows],
        "offset": offset,
        "limit": limit,
    }


def _get_job_status_sync(job_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, status, updated_at FROM vertex_web4_inference_job WHERE id = ?",
            (job_id,)
        ).fetchone()
        
    if not row:
        return {"error": "not found"}
    return dict(row)


def _get_cluster_stats_sync(actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        expert_count = conn.execute(
            "SELECT COUNT(*) FROM vertex_web4_expert WHERE status = 'active'"
        ).fetchone()[0]
        job_count = conn.execute(
            "SELECT COUNT(*) FROM vertex_web4_inference_job"
        ).fetchone()[0]
        
    return {"activeExperts": expert_count or 0, "totalJobs": job_count or 0}


def _update_expert_sync(expert_id: str, status: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_web4_expert SET status = ?, updated_at = ? WHERE id = ?",
            (status, now, expert_id)
        )
        conn.commit()
        
    return {"expertId": expert_id, "status": status, "updatedAt": now}


# ---------------------------------------------------------------------------
# Worker & Tasks
# ---------------------------------------------------------------------------

async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.web4.register.expert")
    async def task_register_expert(**kwargs):
        return await asyncio.to_thread(
            _create_expert_sync,
            kwargs.get("name", ""),
            kwargs.get("did", ""),
            kwargs.get("specialization", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.web4.list.experts")
    async def task_list_experts(**kwargs):
        return await asyncio.to_thread(
            _list_experts_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.web4.submit.inference")
    async def task_submit_inference(**kwargs):
        return await asyncio.to_thread(
            _submit_inference_sync,
            kwargs.get("expertId", ""),
            kwargs.get("model", ""),
            kwargs.get("input", {}),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.web4.get.inferenceResult")
    async def task_get_inference_result(**kwargs):
        return await asyncio.to_thread(
            _get_inference_result_sync,
            kwargs.get("jobId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.web4.list.jobs")
    async def task_list_jobs(**kwargs):
        return await asyncio.to_thread(
            _list_jobs_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.web4.get.jobStatus")
    async def task_get_job_status(**kwargs):
        return await asyncio.to_thread(
            _get_job_status_sync,
            kwargs.get("jobId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.web4.get.clusterStats")
    async def task_get_cluster_stats(**kwargs):
        return await asyncio.to_thread(
            _get_cluster_stats_sync,
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.web4.update.expert")
    async def task_update_expert(**kwargs):
        return await asyncio.to_thread(
            _update_expert_sync,
            kwargs.get("expertId", ""),
            kwargs.get("status", "active"),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
