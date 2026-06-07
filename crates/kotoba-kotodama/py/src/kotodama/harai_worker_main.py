"""harai.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.harai.createPayment")
    async def task_create_payment(**kwargs):
        payer_did = kwargs.get("payerDid", "")
        payee_did = kwargs.get("payeeDid", "")
        amount = float(kwargs.get("amount", 0.0))
        currency = kwargs.get("currency", "JPY")
        owner_did = kwargs.get("ownerDid", "did:web:harai.etzhayyim.com")

        payment_id = str(uuid.uuid4())
        vertex_id = f"harai:payment:{payment_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_harai_payment
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, payer_did, payee_did, amount, currency, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, owner_did,
                payment_id, payer_did, payee_did, amount, currency, "pending",
                "did:web:harai.etzhayyim.com", "did:web:harai.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"paymentId": payment_id, "status": "pending"}

    @worker.task(task_type="com.etzhayyim.apps.harai.listPayments")
    async def task_list_payments(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))
        payer_did = kwargs.get("payerDid", "")

        db = await get_db()
        try:
            if payer_did:
                rows = await db.fetch(
                    "SELECT id, payer_did, payee_did, amount, currency, status, created_at "
                    "FROM vertex_harai_payment WHERE payer_did = $1 LIMIT $2 OFFSET $3",
                    payer_did, limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_harai_payment WHERE payer_did = $1", payer_did
                )
            else:
                rows = await db.fetch(
                    "SELECT id, payer_did, payee_did, amount, currency, status, created_at "
                    "FROM vertex_harai_payment LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total_row = await db.fetchrow("SELECT COUNT(*) AS cnt FROM vertex_harai_payment")
        finally:
            await db.close()

        return {
            "payments": [dict(r) for r in rows],
            "total": total_row["cnt"] if total_row else 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.harai.settlePayment")
    async def task_settle_payment(**kwargs):
        payment_id = kwargs.get("paymentId", "")
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_harai_payment SET status = 'settled', updated_at = $1 WHERE id = $2",
                now, payment_id,
            )
        finally:
            await db.close()

        return {"paymentId": payment_id, "status": "settled", "settledAt": now}

    @worker.task(task_type="com.etzhayyim.apps.harai.refundPayment")
    async def task_refund_payment(**kwargs):
        payment_id = kwargs.get("paymentId", "")
        reason = kwargs.get("reason", "")
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_harai_payment SET status = 'refunded', updated_at = $1 WHERE id = $2",
                now, payment_id,
            )
        finally:
            await db.close()

        return {"paymentId": payment_id, "status": "refunded", "refundedAt": now, "reason": reason}

    @worker.task(task_type="com.etzhayyim.apps.harai.getBalance")
    async def task_get_balance(**kwargs):
        account_did = kwargs.get("accountDid", "")
        currency = kwargs.get("currency", "JPY")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT SUM(CASE WHEN payee_did = $1 AND status = 'settled' THEN amount ELSE 0 END) "
                "- SUM(CASE WHEN payer_did = $1 AND status = 'settled' THEN amount ELSE 0 END) AS balance "
                "FROM vertex_harai_payment WHERE currency = $2 AND (payer_did = $1 OR payee_did = $1)",
                account_did, currency,
            )
        finally:
            await db.close()

        balance = float(row["balance"]) if row and row["balance"] is not None else 0.0
        return {"accountDid": account_did, "currency": currency, "balance": balance}

    @worker.task(task_type="com.etzhayyim.apps.harai.transferFunds")
    async def task_transfer_funds(**kwargs):
        from_did = kwargs.get("fromDid", "")
        to_did = kwargs.get("toDid", "")
        amount = float(kwargs.get("amount", 0.0))
        currency = kwargs.get("currency", "JPY")

        transfer_id = str(uuid.uuid4())
        vertex_id = f"harai:payment:{transfer_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_harai_payment
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, payer_did, payee_did, amount, currency, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, from_did,
                transfer_id, from_did, to_did, amount, currency, "settled",
                "did:web:harai.etzhayyim.com", "did:web:harai.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"transferId": transfer_id, "status": "settled", "transferredAt": now}

    @worker.task(task_type="com.etzhayyim.apps.harai.listTransactions")
    async def task_list_transactions(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))
        account_did = kwargs.get("accountDid", "")

        db = await get_db()
        try:
            if account_did:
                rows = await db.fetch(
                    "SELECT id, payer_did, payee_did, amount, currency, status, created_at "
                    "FROM vertex_harai_payment "
                    "WHERE payer_did = $1 OR payee_did = $1 "
                    "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    account_did, limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_harai_payment WHERE payer_did = $1 OR payee_did = $1",
                    account_did,
                )
            else:
                rows = await db.fetch(
                    "SELECT id, payer_did, payee_did, amount, currency, status, created_at "
                    "FROM vertex_harai_payment ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total_row = await db.fetchrow("SELECT COUNT(*) AS cnt FROM vertex_harai_payment")
        finally:
            await db.close()

        return {
            "transactions": [dict(r) for r in rows],
            "total": total_row["cnt"] if total_row else 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.harai.closeAccount")
    async def task_close_account(**kwargs):
        account_did = kwargs.get("accountDid", "")
        reason = kwargs.get("reason", "")
        now = datetime.utcnow().isoformat()

        return {
            "accountDid": account_did,
            "status": "closed",
            "closedAt": now,
            "reason": reason,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
