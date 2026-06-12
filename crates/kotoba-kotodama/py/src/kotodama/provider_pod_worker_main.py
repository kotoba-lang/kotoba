"""provider-pod.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv("DATABASE_URL", "REDACTED_USE_DATABASE_URL_ENV")


async def get_db():
    return await asyncpg.connect(DB_URL)


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.providerPod.register.provider")
    async def task_register_provider(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:provider-pod.etzhayyim.com")
        name = kwargs.get("name", "")
        endpoint = kwargs.get("endpoint", "")
        capabilities = kwargs.get("capabilities", [])

        provider_id = str(uuid.uuid4())
        vertex_id = f"provider_pod:provider:{provider_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_provider_pod_provider
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, endpoint, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, actor_did,
                provider_id, name, endpoint, "registered",
                "did:web:provider-pod.etzhayyim.com", "did:web:provider-pod.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"providerId": provider_id, "status": "registered"}

    @worker.task(task_type="com.etzhayyim.apps.providerPod.list.providers")
    async def task_list_providers(**kwargs):
        status = kwargs.get("status", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT id, name, endpoint, status, created_at FROM vertex_provider_pod_provider "
                    "WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_provider_pod_provider WHERE status = $1", status
                )
            else:
                rows = await db.fetch(
                    "SELECT id, name, endpoint, status, created_at FROM vertex_provider_pod_provider "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_provider_pod_provider")
        finally:
            await db.close()

        return {
            "providers": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.providerPod.get.provider")
    async def task_get_provider(**kwargs):
        provider_id = kwargs.get("providerId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, endpoint, status, created_at, updated_at "
                "FROM vertex_provider_pod_provider WHERE id = $1",
                provider_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.providerPod.update.health")
    async def task_update_health(**kwargs):
        provider_id = kwargs.get("providerId", "")
        health_status = kwargs.get("healthStatus", "healthy")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_provider_pod_provider SET status = $1, updated_at = $2 WHERE id = $3",
                health_status, now, provider_id,
            )
        finally:
            await db.close()

        return {"providerId": provider_id, "healthStatus": health_status, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.providerPod.list.capabilities")
    async def task_list_capabilities(**kwargs):
        provider_id = kwargs.get("providerId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, endpoint FROM vertex_provider_pod_provider WHERE id = $1",
                provider_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found", "capabilities": []}

        return {
            "providerId": provider_id,
            "capabilities": [],
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.providerPod.create.pod")
    async def task_create_pod(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:provider-pod.etzhayyim.com")
        provider_id = kwargs.get("providerId", "")
        pod_name = kwargs.get("podName", "")
        config = kwargs.get("config", {})

        pod_id = str(uuid.uuid4())
        vertex_id = f"provider_pod:pod:{pod_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_provider_pod_pod
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, provider_id, pod_name, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, actor_did,
                pod_id, provider_id, pod_name, "pending",
                "did:web:provider-pod.etzhayyim.com", "did:web:provider-pod.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"podId": pod_id, "providerId": provider_id, "status": "pending"}

    @worker.task(task_type="com.etzhayyim.apps.providerPod.list.pods")
    async def task_list_pods(**kwargs):
        provider_id = kwargs.get("providerId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if provider_id:
                rows = await db.fetch(
                    "SELECT id, provider_id, pod_name, status, created_at FROM vertex_provider_pod_pod "
                    "WHERE provider_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    provider_id, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_provider_pod_pod WHERE provider_id = $1", provider_id
                )
            else:
                rows = await db.fetch(
                    "SELECT id, provider_id, pod_name, status, created_at FROM vertex_provider_pod_pod "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_provider_pod_pod")
        finally:
            await db.close()

        return {
            "pods": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.providerPod.get.pod.status")
    async def task_get_pod_status(**kwargs):
        pod_id = kwargs.get("podId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, provider_id, pod_name, status, created_at, updated_at "
                "FROM vertex_provider_pod_pod WHERE id = $1",
                pod_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
