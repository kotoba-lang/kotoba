"""cards.etzhayyim.com — standalone LangServer worker (BPMN service task handlers).

Tables used (RisingWave via asyncpg):
  vertex_cards_cardholder   — cardholder registry
  vertex_cards_issued_card  — issued card records
  vertex_cards_transaction  — transaction log
  vertex_cards_authorization — authorization events
  vertex_cards_dispute       — dispute records
"""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv(
    "DATABASE_URL",
    "REDACTED_USE_DATABASE_URL_ENV",
)

ACTOR_DID = "did:web:cards.etzhayyim.com"


async def get_db() -> asyncpg.Connection:
    return await asyncpg.connect(DB_URL)


def _now() -> str:
    return datetime.utcnow().isoformat()


def _today() -> date:
    return date.today()


async def run_worker() -> None:
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    # ── createCardholder ──────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.createCardholder")
    async def task_create_cardholder(**kwargs):
        name = kwargs.get("name", "")
        email = kwargs.get("email", "")
        phone = kwargs.get("phone", "")
        billing_address = kwargs.get("billingAddress", "")
        org_did = kwargs.get("orgDid", ACTOR_DID)

        cardholder_id = str(uuid.uuid4())
        vertex_id = f"cards:cardholder:{cardholder_id}"
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_cards_cardholder
                   (vertex_id, _seq, created_date, sensitivity_ord,
                    cardholder_id, name, email, phone, billing_address,
                    status, actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, _today(), 0,
                cardholder_id, name, email, phone, billing_address,
                "active", ACTOR_DID, org_did, now, now,
            )
        finally:
            await db.close()

        return {"ok": True, "cardholderId": cardholder_id, "createdAt": now}

    # ── issueCard ─────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.issueCard")
    async def task_issue_card(**kwargs):
        cardholder_id = kwargs.get("cardholderId", "")
        card_type = kwargs.get("cardType", "virtual")
        currency = kwargs.get("currency", "USD")
        spending_limit = float(kwargs.get("spendingLimit", 0))
        org_did = kwargs.get("orgDid", ACTOR_DID)

        card_id = str(uuid.uuid4())
        vertex_id = f"cards:card:{card_id}"
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_cards_issued_card
                   (vertex_id, _seq, created_date, sensitivity_ord,
                    card_id, cardholder_id, card_type, currency,
                    spending_limit, status, actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, _today(), 0,
                card_id, cardholder_id, card_type, currency,
                spending_limit, "active", ACTOR_DID, org_did, now, now,
            )
        finally:
            await db.close()

        return {"ok": True, "cardId": card_id, "status": "active", "createdAt": now}

    # ── assignCardCredits ─────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.assignCardCredits")
    async def task_assign_card_credits(**kwargs):
        card_id = kwargs.get("cardId", "")
        amount = float(kwargs.get("amount", 0))
        currency = kwargs.get("currency", "USD")

        now = _now()

        db = await get_db()
        try:
            await db.execute(
                """UPDATE vertex_cards_issued_card
                   SET spending_limit = spending_limit + $1, updated_at = $2
                   WHERE card_id = $3""",
                amount, now, card_id,
            )
        finally:
            await db.close()

        return {"ok": True, "cardId": card_id, "addedAmount": amount, "currency": currency, "updatedAt": now}

    # ── getCardCredits ────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.getCardCredits")
    async def task_get_card_credits(**kwargs):
        card_id = kwargs.get("cardId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT card_id, spending_limit, currency FROM vertex_cards_issued_card WHERE card_id = $1",
                card_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return {"cardId": row["card_id"], "spendingLimit": float(row["spending_limit"]), "currency": row["currency"]}

    # ── handleAuthorization ───────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.handleAuthorization")
    async def task_handle_authorization(**kwargs):
        card_id = kwargs.get("cardId", "")
        merchant = kwargs.get("merchant", "")
        amount = float(kwargs.get("amount", 0))
        currency = kwargs.get("currency", "USD")
        org_did = kwargs.get("orgDid", ACTOR_DID)

        auth_id = str(uuid.uuid4())
        vertex_id = f"cards:auth:{auth_id}"
        now = _now()

        db = await get_db()
        try:
            # Check card exists and is active
            card = await db.fetchrow(
                "SELECT card_id, spending_limit, status FROM vertex_cards_issued_card WHERE card_id = $1",
                card_id,
            )
            decision = "declined"
            if card and card["status"] == "active" and float(card["spending_limit"]) >= amount:
                decision = "approved"

            await db.execute(
                """INSERT INTO vertex_cards_authorization
                   (vertex_id, _seq, created_date, sensitivity_ord,
                    auth_id, card_id, merchant, amount, currency,
                    decision, actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, _today(), 0,
                auth_id, card_id, merchant, amount, currency,
                decision, ACTOR_DID, org_did, now, now,
            )
        finally:
            await db.close()

        return {"ok": True, "authId": auth_id, "decision": decision, "createdAt": now}

    # ── listCards ─────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.listCards")
    async def task_list_cards(**kwargs):
        cardholder_id = kwargs.get("cardholderId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if cardholder_id:
                rows = await db.fetch(
                    f"SELECT card_id, cardholder_id, card_type, currency, spending_limit, status, created_at "
                    f"FROM vertex_cards_issued_card WHERE cardholder_id = $1 "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                    cardholder_id,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_cards_issued_card WHERE cardholder_id = $1",
                    cardholder_id,
                )
            else:
                rows = await db.fetch(
                    f"SELECT card_id, cardholder_id, card_type, currency, spending_limit, status, created_at "
                    f"FROM vertex_cards_issued_card "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_cards_issued_card")
        finally:
            await db.close()

        return {"cards": [dict(r) for r in rows], "total": total, "offset": offset, "limit": limit}

    # ── getCard ───────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.getCard")
    async def task_get_card(**kwargs):
        card_id = kwargs.get("cardId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT card_id, cardholder_id, card_type, currency, spending_limit, status, created_at "
                "FROM vertex_cards_issued_card WHERE card_id = $1",
                card_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    # ── freezeCard ────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.freezeCard")
    async def task_freeze_card(**kwargs):
        card_id = kwargs.get("cardId", "")
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_cards_issued_card SET status = 'frozen', updated_at = $1 WHERE card_id = $2",
                now, card_id,
            )
        finally:
            await db.close()

        return {"ok": True, "cardId": card_id, "status": "frozen", "updatedAt": now}

    # ── unfreezeCard ──────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.unfreezeCard")
    async def task_unfreeze_card(**kwargs):
        card_id = kwargs.get("cardId", "")
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_cards_issued_card SET status = 'active', updated_at = $1 WHERE card_id = $2",
                now, card_id,
            )
        finally:
            await db.close()

        return {"ok": True, "cardId": card_id, "status": "active", "updatedAt": now}

    # ── cancelCard ────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.cancelCard")
    async def task_cancel_card(**kwargs):
        card_id = kwargs.get("cardId", "")
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_cards_issued_card SET status = 'cancelled', updated_at = $1 WHERE card_id = $2",
                now, card_id,
            )
        finally:
            await db.close()

        return {"ok": True, "cardId": card_id, "status": "cancelled", "updatedAt": now}

    # ── listTransactions ──────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.listTransactions")
    async def task_list_transactions(**kwargs):
        card_id = kwargs.get("cardId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if card_id:
                rows = await db.fetch(
                    f"SELECT txn_id, card_id, merchant, amount, currency, status, created_at "
                    f"FROM vertex_cards_transaction WHERE card_id = $1 "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                    card_id,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_cards_transaction WHERE card_id = $1",
                    card_id,
                )
            else:
                rows = await db.fetch(
                    f"SELECT txn_id, card_id, merchant, amount, currency, status, created_at "
                    f"FROM vertex_cards_transaction "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_cards_transaction")
        finally:
            await db.close()

        return {"transactions": [dict(r) for r in rows], "total": total, "offset": offset, "limit": limit}

    # ── getTransaction ────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.getTransaction")
    async def task_get_transaction(**kwargs):
        txn_id = kwargs.get("txnId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT txn_id, card_id, merchant, amount, currency, status, created_at "
                "FROM vertex_cards_transaction WHERE txn_id = $1",
                txn_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    # ── listAuthorizations ────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.listAuthorizations")
    async def task_list_authorizations(**kwargs):
        card_id = kwargs.get("cardId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if card_id:
                rows = await db.fetch(
                    f"SELECT auth_id, card_id, merchant, amount, currency, decision, created_at "
                    f"FROM vertex_cards_authorization WHERE card_id = $1 "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                    card_id,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_cards_authorization WHERE card_id = $1",
                    card_id,
                )
            else:
                rows = await db.fetch(
                    f"SELECT auth_id, card_id, merchant, amount, currency, decision, created_at "
                    f"FROM vertex_cards_authorization "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_cards_authorization")
        finally:
            await db.close()

        return {"authorizations": [dict(r) for r in rows], "total": total, "offset": offset, "limit": limit}

    # ── approveAuthorization ──────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.approveAuthorization")
    async def task_approve_authorization(**kwargs):
        auth_id = kwargs.get("authId", "")
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_cards_authorization SET decision = 'approved', updated_at = $1 WHERE auth_id = $2",
                now, auth_id,
            )
        finally:
            await db.close()

        return {"ok": True, "authId": auth_id, "decision": "approved", "updatedAt": now}

    # ── declineAuthorization ──────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.declineAuthorization")
    async def task_decline_authorization(**kwargs):
        auth_id = kwargs.get("authId", "")
        reason = kwargs.get("reason", "")
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_cards_authorization SET decision = 'declined', updated_at = $1 WHERE auth_id = $2",
                now, auth_id,
            )
        finally:
            await db.close()

        return {"ok": True, "authId": auth_id, "decision": "declined", "reason": reason, "updatedAt": now}

    # ── updateSpendingLimit ───────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.updateSpendingLimit")
    async def task_update_spending_limit(**kwargs):
        card_id = kwargs.get("cardId", "")
        new_limit = float(kwargs.get("spendingLimit", 0))
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_cards_issued_card SET spending_limit = $1, updated_at = $2 WHERE card_id = $3",
                new_limit, now, card_id,
            )
        finally:
            await db.close()

        return {"ok": True, "cardId": card_id, "spendingLimit": new_limit, "updatedAt": now}

    # ── topUp ─────────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.topUp")
    async def task_top_up(**kwargs):
        card_id = kwargs.get("cardId", "")
        amount = float(kwargs.get("amount", 0))
        currency = kwargs.get("currency", "USD")
        org_did = kwargs.get("orgDid", ACTOR_DID)

        txn_id = str(uuid.uuid4())
        vertex_id = f"cards:txn:{txn_id}"
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_cards_transaction
                   (vertex_id, _seq, created_date, sensitivity_ord,
                    txn_id, card_id, merchant, amount, currency,
                    status, actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, _today(), 0,
                txn_id, card_id, "top-up", amount, currency,
                "settled", ACTOR_DID, org_did, now, now,
            )
            await db.execute(
                "UPDATE vertex_cards_issued_card SET spending_limit = spending_limit + $1, updated_at = $2 WHERE card_id = $3",
                amount, now, card_id,
            )
        finally:
            await db.close()

        return {"ok": True, "txnId": txn_id, "cardId": card_id, "amount": amount, "currency": currency, "createdAt": now}

    # ── getBalance ────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.getBalance")
    async def task_get_balance(**kwargs):
        card_id = kwargs.get("cardId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT card_id, spending_limit, currency FROM vertex_cards_issued_card WHERE card_id = $1",
                card_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return {"cardId": row["card_id"], "balance": float(row["spending_limit"]), "currency": row["currency"]}

    # ── listDisputes ──────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.listDisputes")
    async def task_list_disputes(**kwargs):
        card_id = kwargs.get("cardId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if card_id:
                rows = await db.fetch(
                    f"SELECT dispute_id, card_id, txn_id, reason, status, created_at "
                    f"FROM vertex_cards_dispute WHERE card_id = $1 "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                    card_id,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_cards_dispute WHERE card_id = $1",
                    card_id,
                )
            else:
                rows = await db.fetch(
                    f"SELECT dispute_id, card_id, txn_id, reason, status, created_at "
                    f"FROM vertex_cards_dispute "
                    f"ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}",
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_cards_dispute")
        finally:
            await db.close()

        return {"disputes": [dict(r) for r in rows], "total": total, "offset": offset, "limit": limit}

    # ── createDispute ─────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.createDispute")
    async def task_create_dispute(**kwargs):
        card_id = kwargs.get("cardId", "")
        txn_id = kwargs.get("txnId", "")
        reason = kwargs.get("reason", "")
        org_did = kwargs.get("orgDid", ACTOR_DID)

        dispute_id = str(uuid.uuid4())
        vertex_id = f"cards:dispute:{dispute_id}"
        now = _now()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_cards_dispute
                   (vertex_id, _seq, created_date, sensitivity_ord,
                    dispute_id, card_id, txn_id, reason,
                    status, actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, _today(), 0,
                dispute_id, card_id, txn_id, reason,
                "open", ACTOR_DID, org_did, now, now,
            )
        finally:
            await db.close()

        return {"ok": True, "disputeId": dispute_id, "status": "open", "createdAt": now}

    # ── summarize ─────────────────────────────────────────────────────────────
    @worker.task(task_type="com.etzhayyim.apps.cards.summarize")
    async def task_summarize(**kwargs):
        org_did = kwargs.get("orgDid", "")

        db = await get_db()
        try:
            total_cards = await db.fetchval("SELECT COUNT(*) FROM vertex_cards_issued_card") or 0
            active_cards = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_cards_issued_card WHERE status = 'active'"
            ) or 0
            total_cardholders = await db.fetchval("SELECT COUNT(*) FROM vertex_cards_cardholder") or 0
            total_txns = await db.fetchval("SELECT COUNT(*) FROM vertex_cards_transaction") or 0
            open_disputes = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_cards_dispute WHERE status = 'open'"
            ) or 0
            pending_auths = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_cards_authorization WHERE decision = 'pending'"
            ) or 0
        finally:
            await db.close()

        return {
            "totalCards": total_cards,
            "activeCards": active_cards,
            "totalCardholders": total_cardholders,
            "totalTransactions": total_txns,
            "openDisputes": open_disputes,
            "pendingAuthorizations": pending_auths,
            "computedAt": _now(),
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
