"""ops.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv("DATABASE_URL", "REDACTED_USE_DATABASE_URL_ENV")

ACTOR_DID = "did:web:ops.etzhayyim.com"


async def get_db():
    return await asyncpg.connect(DB_URL)


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.ops.createProcessRun")
    async def task_create_process_run(**kwargs):
        process_name = kwargs.get("processName", "")
        automation_id = kwargs.get("automationId", "")
        trigger = kwargs.get("trigger", "manual")
        params = kwargs.get("params", {})

        run_id = str(uuid.uuid4())
        vertex_id = f"ops:process_run:{run_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_ops_process_run
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, process_name, automation_id, trigger, status, started_at,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                run_id, process_name, automation_id, trigger, "running", now,
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"runId": run_id, "status": "running", "startedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.ops.updateProcessRun")
    async def task_update_process_run(**kwargs):
        run_id = kwargs.get("runId", "")
        status = kwargs.get("status", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_ops_process_run SET status = $1, updated_at = $2 WHERE id = $3",
                status, now, run_id,
            )
        finally:
            await db.close()

        return {"runId": run_id, "status": status, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.ops.listProcessRuns")
    async def task_list_process_runs(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))
        status = kwargs.get("status", "")

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT id, process_name, automation_id, trigger, status, started_at FROM vertex_ops_process_run WHERE status = $1 LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_ops_process_run WHERE status = $1", status)
            else:
                rows = await db.fetch(
                    "SELECT id, process_name, automation_id, trigger, status, started_at FROM vertex_ops_process_run LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_ops_process_run")
        finally:
            await db.close()

        return {"runs": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.ops.getProcessRun")
    async def task_get_process_run(**kwargs):
        run_id = kwargs.get("runId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, process_name, automation_id, trigger, status, started_at, created_at, updated_at FROM vertex_ops_process_run WHERE id = $1",
                run_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.ops.createAutomation")
    async def task_create_automation(**kwargs):
        name = kwargs.get("name", "")
        description = kwargs.get("description", "")
        trigger_type = kwargs.get("triggerType", "manual")
        schedule = kwargs.get("schedule", "")

        automation_id = str(uuid.uuid4())
        vertex_id = f"ops:automation:{automation_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_ops_automation
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, description, trigger_type, schedule, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                automation_id, name, description, trigger_type, schedule, "active",
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"automationId": automation_id, "status": "active", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.ops.updateAutomation")
    async def task_update_automation(**kwargs):
        automation_id = kwargs.get("automationId", "")
        name = kwargs.get("name", "")
        status = kwargs.get("status", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_ops_automation SET name = $1, status = $2, updated_at = $3 WHERE id = $4",
                name, status, now, automation_id,
            )
        finally:
            await db.close()

        return {"automationId": automation_id, "status": status, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.ops.listAutomations")
    async def task_list_automations(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, name, description, trigger_type, schedule, status, created_at FROM vertex_ops_automation LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval("SELECT COUNT(*) FROM vertex_ops_automation")
        finally:
            await db.close()

        return {"automations": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.ops.getAutomation")
    async def task_get_automation(**kwargs):
        automation_id = kwargs.get("automationId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, description, trigger_type, schedule, status, created_at, updated_at FROM vertex_ops_automation WHERE id = $1",
                automation_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
