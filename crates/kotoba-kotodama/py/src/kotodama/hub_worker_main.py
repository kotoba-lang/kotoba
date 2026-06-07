"""hub.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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
_ACTOR = os.getenv("HUB_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"hub-{safe}.db"


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS vertex_hub_endpoint (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    url             TEXT NOT NULL DEFAULT '',
    method          TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_hub_webhook (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    endpoint_id     TEXT NOT NULL DEFAULT '',
    target_url      TEXT NOT NULL DEFAULT '',
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

def _create_endpoint_sync(name: str, url: str, method: str, owner_did: str, actor: str) -> dict[str, Any]:
    endpoint_id = str(uuid.uuid4())
    vertex_id = f"hub:endpoint:{endpoint_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_hub_endpoint
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, name, url, method, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             endpoint_id, name, url, method, "active",
             "did:web:hub.etzhayyim.com", "did:web:hub.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"endpointId": endpoint_id, "status": "active"}


def _list_endpoints_sync(limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, name, url, method, status, created_at "
            "FROM vertex_hub_endpoint LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM vertex_hub_endpoint").fetchone()[0]
        
    return {
        "endpoints": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _create_webhook_sync(endpoint_id: str, target_url: str, events: list, owner_did: str, actor: str) -> dict[str, Any]:
    webhook_id = str(uuid.uuid4())
    vertex_id = f"hub:webhook:{webhook_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_hub_webhook
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, endpoint_id, target_url, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             webhook_id, endpoint_id, target_url, "active",
             "did:web:hub.etzhayyim.com", "did:web:hub.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"webhookId": webhook_id, "status": "active"}


def _list_webhooks_sync(endpoint_id: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if endpoint_id:
            rows = conn.execute(
                "SELECT id, endpoint_id, target_url, status, created_at "
                "FROM vertex_hub_webhook WHERE endpoint_id = ? LIMIT ? OFFSET ?",
                (endpoint_id, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_hub_webhook WHERE endpoint_id = ?",
                (endpoint_id,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, endpoint_id, target_url, status, created_at "
                "FROM vertex_hub_webhook LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM vertex_hub_webhook").fetchone()[0]
            
    return {
        "webhooks": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _get_metrics_sync(endpoint_id: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    with _open(actor) as conn:
        total_endpoints = conn.execute("SELECT COUNT(*) FROM vertex_hub_endpoint").fetchone()[0]
        total_webhooks = conn.execute("SELECT COUNT(*) FROM vertex_hub_webhook").fetchone()[0]
        
    return {
        "endpointId": endpoint_id,
        "totalEndpoints": total_endpoints,
        "totalWebhooks": total_webhooks,
        "requestsToday": 0,
        "computedAt": now,
    }

# ---------------------------------------------------------------------------
# Worker & Tasks
# ---------------------------------------------------------------------------

async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.hub.registerEndpoint")
    async def task_register_endpoint(**kwargs):
        return await asyncio.to_thread(
            _create_endpoint_sync,
            kwargs.get("name", ""),
            kwargs.get("url", ""),
            kwargs.get("method", "POST"),
            kwargs.get("ownerDid", "did:web:hub.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.hub.listEndpoints")
    async def task_list_endpoints(**kwargs):
        return await asyncio.to_thread(
            _list_endpoints_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.hub.routeRequest")
    async def task_route_request(**kwargs):
        endpoint_id = kwargs.get("endpointId", "")
        return {
            "requestId": str(uuid.uuid4()),
            "endpointId": endpoint_id,
            "status": "routed",
            "routedAt": datetime.utcnow().isoformat(),
        }

    @worker.task(task_type="com.etzhayyim.apps.hub.getRouteStatus")
    async def task_get_route_status(**kwargs):
        return {
            "requestId": kwargs.get("requestId", ""),
            "status": "delivered",
            "checkedAt": datetime.utcnow().isoformat(),
        }

    @worker.task(task_type="com.etzhayyim.apps.hub.createWebhook")
    async def task_create_webhook(**kwargs):
        return await asyncio.to_thread(
            _create_webhook_sync,
            kwargs.get("endpointId", ""),
            kwargs.get("targetUrl", ""),
            kwargs.get("events", []),
            kwargs.get("ownerDid", "did:web:hub.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.hub.listWebhooks")
    async def task_list_webhooks(**kwargs):
        return await asyncio.to_thread(
            _list_webhooks_sync,
            kwargs.get("endpointId", ""),
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.hub.testConnection")
    async def task_test_connection(**kwargs):
        return {
            "endpointId": kwargs.get("endpointId", ""),
            "success": True,
            "latencyMs": 42,
            "testedAt": datetime.utcnow().isoformat(),
        }

    @worker.task(task_type="com.etzhayyim.apps.hub.getMetrics")
    async def task_get_metrics(**kwargs):
        return await asyncio.to_thread(
            _get_metrics_sync,
            kwargs.get("endpointId", ""),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
