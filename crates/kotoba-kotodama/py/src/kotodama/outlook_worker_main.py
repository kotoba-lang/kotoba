"""outlook.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.outlook.get.oauth.config")
    async def task_get_oauth_config(**kwargs):
        return {
            "authorizationUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/authorize",
            "tokenUrl": "https://login.microsoftonline.com/common/oauth2/v2.0/token",
            "scopes": ["https://graph.microsoft.com/Mail.Read", "https://graph.microsoft.com/Mail.Send"],
            "responseType": "code",
        }

    @worker.task(task_type="com.etzhayyim.apps.outlook.start.auth")
    async def task_start_auth(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:outlook.etzhayyim.com")
        redirect_uri = kwargs.get("redirectUri", "")

        state = str(uuid.uuid4())
        auth_url = (
            f"https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
            f"?client_id=placeholder&response_type=code&redirect_uri={redirect_uri}"
            f"&scope=https%3A%2F%2Fgraph.microsoft.com%2FMail.Read&state={state}"
        )

        return {"authUrl": auth_url, "state": state}

    @worker.task(task_type="com.etzhayyim.apps.outlook.exchange.code")
    async def task_exchange_code(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:outlook.etzhayyim.com")
        code = kwargs.get("code", "")
        state = kwargs.get("state", "")

        connection_id = str(uuid.uuid4())
        vertex_id = f"outlook:connection:{connection_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_outlook_connection
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, status, upn,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                vertex_id, 0, date.today(), 0, actor_did,
                connection_id, "connected", "",
                "did:web:outlook.etzhayyim.com", "did:web:outlook.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"connectionId": connection_id, "status": "connected"}

    @worker.task(task_type="com.etzhayyim.apps.outlook.get.auth.status")
    async def task_get_auth_status(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:outlook.etzhayyim.com")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, status, upn, created_at FROM vertex_outlook_connection "
                "WHERE actor_did = $1 ORDER BY created_at DESC LIMIT 1",
                actor_did,
            )
        finally:
            await db.close()

        if not row:
            return {"status": "disconnected", "connectionId": None}
        return {"status": row["status"], "connectionId": row["id"], "upn": row["upn"]}

    @worker.task(task_type="com.etzhayyim.apps.outlook.get.connection")
    async def task_get_connection(**kwargs):
        connection_id = kwargs.get("connectionId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, status, upn, created_at, updated_at FROM vertex_outlook_connection WHERE id = $1",
                connection_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.outlook.sync.mailbox")
    async def task_sync_mailbox(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:outlook.etzhayyim.com")
        connection_id = kwargs.get("connectionId", "")

        mailbox_id = str(uuid.uuid4())
        vertex_id = f"outlook:mailbox:{mailbox_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_outlook_mailbox
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, connection_id, last_sync_at, message_count,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, actor_did,
                mailbox_id, connection_id, now, 0,
                "did:web:outlook.etzhayyim.com", "did:web:outlook.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"mailboxId": mailbox_id, "connectionId": connection_id, "syncedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.outlook.card.home")
    async def task_card_home(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:outlook.etzhayyim.com")

        db = await get_db()
        try:
            conn_row = await db.fetchrow(
                "SELECT id, status, upn FROM vertex_outlook_connection "
                "WHERE actor_did = $1 ORDER BY created_at DESC LIMIT 1",
                actor_did,
            )
            mailbox_row = None
            if conn_row:
                mailbox_row = await db.fetchrow(
                    "SELECT id, message_count, last_sync_at FROM vertex_outlook_mailbox "
                    "WHERE connection_id = $1 ORDER BY created_at DESC LIMIT 1",
                    conn_row["id"],
                )
        finally:
            await db.close()

        return {
            "connection": dict(conn_row) if conn_row else None,
            "mailbox": dict(mailbox_row) if mailbox_row else None,
        }

    @worker.task(task_type="com.etzhayyim.apps.outlook.card.action")
    async def task_card_action(**kwargs):
        action = kwargs.get("action", "")
        payload = kwargs.get("payload", {})

        now = datetime.utcnow().isoformat()

        return {
            "action": action,
            "result": "ok",
            "executedAt": now,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
