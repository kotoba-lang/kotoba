"""scheduler.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.scheduler.createJob")
    async def task_create_job(**kwargs):
        name = kwargs.get("name", "")
        cron = kwargs.get("cron", "")
        owner_did = kwargs.get("ownerDid", "did:web:scheduler.etzhayyim.com")

        job_id = str(uuid.uuid4())
        vertex_id = f"scheduler:job:{job_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_scheduler_job
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, cron, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, owner_did,
                job_id, name, cron, "active",
                "did:web:scheduler.etzhayyim.com", "did:web:scheduler.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"id": job_id, "status": "active", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.scheduler.getJob")
    async def task_get_job(**kwargs):
        job_id = kwargs.get("id", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, cron, status, created_at, updated_at "
                "FROM vertex_scheduler_job WHERE id = $1",
                job_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.scheduler.updateJob")
    async def task_update_job(**kwargs):
        job_id = kwargs.get("id", "")
        name = kwargs.get("name", "")
        cron = kwargs.get("cron", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_scheduler_job SET name = $1, cron = $2, updated_at = $3 WHERE id = $4",
                name, cron, now, job_id,
            )
        finally:
            await db.close()

        return {"id": job_id, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.scheduler.deleteJob")
    async def task_delete_job(**kwargs):
        job_id = kwargs.get("id", "")

        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM vertex_scheduler_job WHERE id = $1",
                job_id,
            )
        finally:
            await db.close()

        return {"id": job_id, "deleted": True}

    @worker.task(task_type="com.etzhayyim.apps.scheduler.listJobs")
    async def task_list_jobs(**kwargs):
        status = kwargs.get("status", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT id, name, cron, status, created_at FROM vertex_scheduler_job "
                    "WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_scheduler_job WHERE status = $1", status
                )
            else:
                rows = await db.fetch(
                    "SELECT id, name, cron, status, created_at FROM vertex_scheduler_job "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_scheduler_job"
                )
        finally:
            await db.close()

        return {
            "jobs": [dict(r) for r in rows],
            "total": total_row["cnt"] if total_row else 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.scheduler.pauseJob")
    async def task_pause_job(**kwargs):
        job_id = kwargs.get("id", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_scheduler_job SET status = 'paused', updated_at = $1 WHERE id = $2",
                now, job_id,
            )
        finally:
            await db.close()

        return {"id": job_id, "status": "paused", "pausedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.scheduler.resumeJob")
    async def task_resume_job(**kwargs):
        job_id = kwargs.get("id", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_scheduler_job SET status = 'active', updated_at = $1 WHERE id = $2",
                now, job_id,
            )
        finally:
            await db.close()

        return {"id": job_id, "status": "active", "resumedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.scheduler.jobStatus")
    async def task_job_status(**kwargs):
        job_id = kwargs.get("id", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, cron, status, created_at, updated_at "
                "FROM vertex_scheduler_job WHERE id = $1",
                job_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
