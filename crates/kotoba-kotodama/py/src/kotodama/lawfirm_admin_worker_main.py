"""lawfirm-admin.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv("DATABASE_URL", "REDACTED_USE_DATABASE_URL_ENV")

ACTOR_DID = "did:web:lawfirm-admin.etzhayyim.com"


async def get_db():
    return await asyncpg.connect(DB_URL)


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.createCase")
    async def task_create_case(**kwargs):
        title = kwargs.get("title", "")
        client_id = kwargs.get("clientId", "")
        case_type = kwargs.get("caseType", "")
        description = kwargs.get("description", "")

        case_id = str(uuid.uuid4())
        vertex_id = f"lawfirm_admin:case:{case_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_lawfirm_admin_case
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, title, client_id, case_type, status, description,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                case_id, title, client_id, case_type, "open", description,
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"caseId": case_id, "status": "open", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.updateCase")
    async def task_update_case(**kwargs):
        case_id = kwargs.get("caseId", "")
        status = kwargs.get("status", "")
        description = kwargs.get("description", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_lawfirm_admin_case SET status = $1, description = $2, updated_at = $3 WHERE id = $4",
                status, description, now, case_id,
            )
        finally:
            await db.close()

        return {"caseId": case_id, "status": status, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.listCases")
    async def task_list_cases(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))
        status = kwargs.get("status", "")

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT id, title, client_id, case_type, status, created_at FROM vertex_lawfirm_admin_case WHERE status = $1 LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_lawfirm_admin_case WHERE status = $1", status)
            else:
                rows = await db.fetch(
                    "SELECT id, title, client_id, case_type, status, created_at FROM vertex_lawfirm_admin_case LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_lawfirm_admin_case")
        finally:
            await db.close()

        return {"cases": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.getCase")
    async def task_get_case(**kwargs):
        case_id = kwargs.get("caseId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, client_id, case_type, status, description, created_at, updated_at FROM vertex_lawfirm_admin_case WHERE id = $1",
                case_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.createClient")
    async def task_create_client(**kwargs):
        name = kwargs.get("name", "")
        email = kwargs.get("email", "")
        phone = kwargs.get("phone", "")
        org_name = kwargs.get("orgName", "")

        client_id = str(uuid.uuid4())
        vertex_id = f"lawfirm_admin:client:{client_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_lawfirm_admin_client
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, email, phone, org_name, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                client_id, name, email, phone, org_name, "active",
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"clientId": client_id, "status": "active", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.updateClient")
    async def task_update_client(**kwargs):
        client_id = kwargs.get("clientId", "")
        name = kwargs.get("name", "")
        email = kwargs.get("email", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_lawfirm_admin_client SET name = $1, email = $2, updated_at = $3 WHERE id = $4",
                name, email, now, client_id,
            )
        finally:
            await db.close()

        return {"clientId": client_id, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.listClients")
    async def task_list_clients(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, name, email, phone, org_name, status, created_at FROM vertex_lawfirm_admin_client LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval("SELECT COUNT(*) FROM vertex_lawfirm_admin_client")
        finally:
            await db.close()

        return {"clients": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.lawfirmAdmin.getClient")
    async def task_get_client(**kwargs):
        client_id = kwargs.get("clientId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, email, phone, org_name, status, created_at, updated_at FROM vertex_lawfirm_admin_client WHERE id = $1",
                client_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
