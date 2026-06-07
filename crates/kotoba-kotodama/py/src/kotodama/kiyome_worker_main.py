"""kiyome.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("KIYOME_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"kiyome-{safe}.db"


_DDL = """
CREATE TABLE IF NOT EXISTS vertex_kiyome_clearance (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    subject_did     TEXT NOT NULL DEFAULT '',
    clearance_type  TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_kiyome_audit_log (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    actor_did_ref   TEXT NOT NULL DEFAULT '',
    action          TEXT NOT NULL DEFAULT '',
    resource        TEXT NOT NULL DEFAULT '',
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


def _submit_clearance_sync(subject_did: str, clearance_type: str, description: str, owner_did: str, actor: str) -> dict[str, Any]:
    clearance_id = str(uuid.uuid4())
    vertex_id = f"kiyome:clearance:{clearance_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_kiyome_clearance
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, subject_did, clearance_type, description, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             clearance_id, subject_did, clearance_type, description, "pending",
             "did:web:kiyome.etzhayyim.com", "did:web:kiyome.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"clearanceId": clearance_id, "status": "pending"}


def _list_clearances_sync(limit: int, offset: int, status: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if status:
            rows = conn.execute(
                "SELECT id, subject_did, clearance_type, description, status, created_at "
                "FROM vertex_kiyome_clearance WHERE status = ? LIMIT ? OFFSET ?",
                (status, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kiyome_clearance WHERE status = ?",
                (status,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, subject_did, clearance_type, description, status, created_at "
                "FROM vertex_kiyome_clearance LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kiyome_clearance"
            ).fetchone()[0]

    return {
        "clearances": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _approve_clearance_sync(clearance_id: str, approver_did: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_kiyome_clearance SET status = 'approved', updated_at = ? WHERE id = ?",
            (now, clearance_id)
        )
        conn.commit()

    return {"clearanceId": clearance_id, "status": "approved", "approvedAt": now, "approverDid": approver_did}


def _reject_clearance_sync(clearance_id: str, reason: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_kiyome_clearance SET status = 'rejected', updated_at = ? WHERE id = ?",
            (now, clearance_id)
        )
        conn.commit()

    return {"clearanceId": clearance_id, "status": "rejected", "rejectedAt": now, "reason": reason}


def _create_audit_log_sync(actor_did_ref: str, action: str, resource: str, owner_did: str, actor: str) -> dict[str, Any]:
    log_id = str(uuid.uuid4())
    vertex_id = f"kiyome:audit_log:{log_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_kiyome_audit_log
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, actor_did_ref, action, resource,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             log_id, actor_did_ref, action, resource,
             "did:web:kiyome.etzhayyim.com", "did:web:kiyome.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"logId": log_id, "createdAt": now}


def _list_audit_logs_sync(limit: int, offset: int, actor_did_ref: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if actor_did_ref:
            rows = conn.execute(
                "SELECT id, actor_did_ref, action, resource, created_at "
                "FROM vertex_kiyome_audit_log WHERE actor_did_ref = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (actor_did_ref, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kiyome_audit_log WHERE actor_did_ref = ?",
                (actor_did_ref,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, actor_did_ref, action, resource, created_at "
                "FROM vertex_kiyome_audit_log ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kiyome_audit_log"
            ).fetchone()[0]

    return {
        "logs": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _get_compliance_status_sync(subject_did: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        pending = conn.execute(
            "SELECT COUNT(*) FROM vertex_kiyome_clearance WHERE subject_did = ? AND status = 'pending'",
            (subject_did,)
        ).fetchone()[0]
        approved = conn.execute(
            "SELECT COUNT(*) FROM vertex_kiyome_clearance WHERE subject_did = ? AND status = 'approved'",
            (subject_did,)
        ).fetchone()[0]
        rejected = conn.execute(
            "SELECT COUNT(*) FROM vertex_kiyome_clearance WHERE subject_did = ? AND status = 'rejected'",
            (subject_did,)
        ).fetchone()[0]

    return {
        "subjectDid": subject_did,
        "pendingClearances": pending,
        "approvedClearances": approved,
        "rejectedClearances": rejected,
        "compliant": pending == 0,
        "checkedAt": now,
    }


def _run_purification_sync(scope: str, dry_run: bool, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    run_id = str(uuid.uuid4())

    return {
        "runId": run_id,
        "scope": scope,
        "dryRun": dry_run,
        "status": "completed",
        "itemsPurified": 0,
        "completedAt": now,
    }


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.kiyome.submitClearance")
    async def task_submit_clearance(**kwargs):
        return await asyncio.to_thread(
            _submit_clearance_sync,
            kwargs.get("subjectDid", ""),
            kwargs.get("clearanceType", ""),
            kwargs.get("description", ""),
            kwargs.get("ownerDid", "did:web:kiyome.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kiyome.listClearances")
    async def task_list_clearances(**kwargs):
        return await asyncio.to_thread(
            _list_clearances_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("status", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kiyome.approveClearance")
    async def task_approve_clearance(**kwargs):
        return await asyncio.to_thread(
            _approve_clearance_sync,
            kwargs.get("clearanceId", ""),
            kwargs.get("approverDid", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kiyome.rejectClearance")
    async def task_reject_clearance(**kwargs):
        return await asyncio.to_thread(
            _reject_clearance_sync,
            kwargs.get("clearanceId", ""),
            kwargs.get("reason", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kiyome.createAuditLog")
    async def task_create_audit_log(**kwargs):
        return await asyncio.to_thread(
            _create_audit_log_sync,
            kwargs.get("actorDid", ""),
            kwargs.get("action", ""),
            kwargs.get("resource", ""),
            kwargs.get("ownerDid", "did:web:kiyome.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kiyome.listAuditLogs")
    async def task_list_audit_logs(**kwargs):
        return await asyncio.to_thread(
            _list_audit_logs_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actorDid", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kiyome.getComplianceStatus")
    async def task_get_compliance_status(**kwargs):
        return await asyncio.to_thread(
            _get_compliance_status_sync,
            kwargs.get("subjectDid", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kiyome.runPurification")
    async def task_run_purification(**kwargs):
        return await asyncio.to_thread(
            _run_purification_sync,
            kwargs.get("scope", "all"),
            kwargs.get("dryRun", False),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
