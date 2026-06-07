"""fleamarket.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.createListing")
    async def task_create_listing(**kwargs):
        title = kwargs.get("title", "")
        seller_did = kwargs.get("sellerDid", "did:web:fleamarket.etzhayyim.com")
        price = float(kwargs.get("price", 0))
        currency = kwargs.get("currency", "JPY")
        description = kwargs.get("description", "")
        category = kwargs.get("category", "")

        listing_id = str(uuid.uuid4())
        vertex_id = f"fleamarket:listing:{listing_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_fleamarket_listing
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, title, seller_did, price, currency, description, category, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17)""",
                vertex_id, 0, date.today(), 0, seller_did,
                listing_id, title, seller_did, price, currency, description, category, "active",
                "did:web:fleamarket.etzhayyim.com", "did:web:fleamarket.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"listingId": listing_id, "title": title, "status": "active", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.listListings")
    async def task_list_listings(**kwargs):
        category = kwargs.get("category", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if category:
                rows = await db.fetch(
                    "SELECT id, title, seller_did, price, currency, category, status, created_at "
                    "FROM vertex_fleamarket_listing WHERE category = $1 AND status = 'active' "
                    "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    category, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_fleamarket_listing WHERE category = $1 AND status = 'active'", category
                )
            else:
                rows = await db.fetch(
                    "SELECT id, title, seller_did, price, currency, category, status, created_at "
                    "FROM vertex_fleamarket_listing WHERE status = 'active' "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_fleamarket_listing WHERE status = 'active'"
                )
        finally:
            await db.close()

        return {
            "listings": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.getListing")
    async def task_get_listing(**kwargs):
        listing_id = kwargs.get("listingId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, seller_did, price, currency, description, category, status, created_at "
                "FROM vertex_fleamarket_listing WHERE id = $1",
                listing_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.createBid")
    async def task_create_bid(**kwargs):
        listing_id = kwargs.get("listingId", "")
        bidder_did = kwargs.get("bidderDid", "did:web:fleamarket.etzhayyim.com")
        amount = float(kwargs.get("amount", 0))

        bid_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        return {"bidId": bid_id, "listingId": listing_id, "bidderDid": bidder_did, "amount": amount, "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.listBids")
    async def task_list_bids(**kwargs):
        listing_id = kwargs.get("listingId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        return {
            "bids": [],
            "total": 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.closeListing")
    async def task_close_listing(**kwargs):
        listing_id = kwargs.get("listingId", "")
        outcome = kwargs.get("outcome", "sold")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_fleamarket_listing SET status = $1, updated_at = $2 WHERE id = $3",
                outcome, now, listing_id,
            )
        finally:
            await db.close()

        return {"listingId": listing_id, "status": outcome, "closedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.createTransaction")
    async def task_create_transaction(**kwargs):
        listing_id = kwargs.get("listingId", "")
        buyer_did = kwargs.get("buyerDid", "did:web:fleamarket.etzhayyim.com")
        seller_did = kwargs.get("sellerDid", "did:web:fleamarket.etzhayyim.com")
        amount = float(kwargs.get("amount", 0))
        currency = kwargs.get("currency", "JPY")

        tx_id = str(uuid.uuid4())
        vertex_id = f"fleamarket:transaction:{tx_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_fleamarket_transaction
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, listing_id, buyer_did, seller_did, amount, currency, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16)""",
                vertex_id, 0, date.today(), 0, buyer_did,
                tx_id, listing_id, buyer_did, seller_did, amount, currency, "pending",
                "did:web:fleamarket.etzhayyim.com", "did:web:fleamarket.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"transactionId": tx_id, "listingId": listing_id, "amount": amount, "status": "pending", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.fleamarket.listTransactions")
    async def task_list_transactions(**kwargs):
        actor_did = kwargs.get("actorDid", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if actor_did:
                rows = await db.fetch(
                    "SELECT id, listing_id, buyer_did, seller_did, amount, currency, status, created_at "
                    "FROM vertex_fleamarket_transaction "
                    "WHERE buyer_did = $1 OR seller_did = $1 "
                    "ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    actor_did, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_fleamarket_transaction WHERE buyer_did = $1 OR seller_did = $1",
                    actor_did,
                )
            else:
                rows = await db.fetch(
                    "SELECT id, listing_id, buyer_did, seller_did, amount, currency, status, created_at "
                    "FROM vertex_fleamarket_transaction ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_fleamarket_transaction")
        finally:
            await db.close()

        return {
            "transactions": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
