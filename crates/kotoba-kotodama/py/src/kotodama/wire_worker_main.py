"""wire.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.wire.create.transfer")
    async def task_create_transfer(**kwargs):
        from_did = kwargs.get("fromDid", "")
        to_did = kwargs.get("toDid", "")
        amount = kwargs.get("amount", 0)
        currency = kwargs.get("currency", "USD")

        transfer_id = str(uuid.uuid4())
        vertex_id = f"wire:transfer:{transfer_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_wire_transfer
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, from_did, to_did, amount, currency, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, from_did,
                transfer_id, from_did, to_did, amount, currency, "pending",
                "did:web:wire.etzhayyim.com", "did:web:wire.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"transferId": transfer_id, "status": "pending"}

    @worker.task(task_type="com.etzhayyim.apps.wire.list.transfers")
    async def task_list_transfers(**kwargs):
        from_did = kwargs.get("fromDid", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            query = "SELECT id, from_did, to_did, amount, currency, status, created_at FROM vertex_wire_transfer"
            params = []
            if from_did:
                query += " WHERE from_did = $1"
                params.append(from_did)
            query += f" LIMIT {limit} OFFSET {offset}"
            rows = await db.fetch(query, *params)
        finally:
            await db.close()

        return {"transfers": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.wire.get.transfer")
    async def task_get_transfer(**kwargs):
        transfer_id = kwargs.get("transferId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, from_did, to_did, amount, currency, status, created_at FROM vertex_wire_transfer WHERE id = $1",
                transfer_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.wire.confirm.transfer")
    async def task_confirm_transfer(**kwargs):
        transfer_id = kwargs.get("transferId", "")
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_wire_transfer SET status = 'confirmed', updated_at = $1 WHERE id = $2",
                now, transfer_id,
            )
        finally:
            await db.close()

        return {"transferId": transfer_id, "status": "confirmed", "confirmedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.wire.create.message")
    async def task_create_message(**kwargs):
        from_did = kwargs.get("fromDid", "")
        to_did = kwargs.get("toDid", "")
        content = kwargs.get("content", "")

        message_id = str(uuid.uuid4())
        vertex_id = f"wire:message:{message_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_wire_message
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, from_did, to_did, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, from_did,
                message_id, from_did, to_did, "sent",
                "did:web:wire.etzhayyim.com", "did:web:wire.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"messageId": message_id, "status": "sent"}

    @worker.task(task_type="com.etzhayyim.apps.wire.list.messages")
    async def task_list_messages(**kwargs):
        from_did = kwargs.get("fromDid", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            query = "SELECT id, from_did, to_did, status, created_at FROM vertex_wire_message"
            params = []
            if from_did:
                query += " WHERE from_did = $1"
                params.append(from_did)
            query += f" LIMIT {limit} OFFSET {offset}"
            rows = await db.fetch(query, *params)
        finally:
            await db.close()

        return {"messages": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.wire.get.balance")
    async def task_get_balance(**kwargs):
        account_did = kwargs.get("accountDid", "")

        return {"accountDid": account_did, "balance": 0.0, "currency": "USD"}

    @worker.task(task_type="com.etzhayyim.apps.wire.get.transferHistory")
    async def task_get_transfer_history(**kwargs):
        account_did = kwargs.get("accountDid", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, from_did, to_did, amount, currency, status, created_at FROM vertex_wire_transfer "
                f"WHERE from_did = $1 OR to_did = $1 ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                account_did,
            )
        finally:
            await db.close()

        return {"history": [dict(r) for r in rows], "accountDid": account_did, "offset": offset, "limit": limit}

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
