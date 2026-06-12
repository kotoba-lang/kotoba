"""kareyanagi.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("KAREYANAGI_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"kareyanagi-{safe}.db"


_DDL = """
CREATE TABLE IF NOT EXISTS vertex_kareyanagi_listing (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    seller_did      TEXT NOT NULL DEFAULT '',
    product_name    TEXT NOT NULL DEFAULT '',
    price           REAL NOT NULL DEFAULT 0.0,
    currency        TEXT NOT NULL DEFAULT '',
    quantity        INTEGER NOT NULL DEFAULT 0,
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_kareyanagi_order (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    buyer_did       TEXT NOT NULL DEFAULT '',
    listing_id      TEXT NOT NULL DEFAULT '',
    quantity        INTEGER NOT NULL DEFAULT 0,
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


def _create_listing_sync(seller_did: str, product_name: str, price: float, currency: str, quantity: int, owner_did: str, actor: str) -> dict[str, Any]:
    listing_id = str(uuid.uuid4())
    vertex_id = f"kareyanagi:listing:{listing_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_kareyanagi_listing
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, seller_did, product_name, price, currency, quantity, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             listing_id, seller_did, product_name, price, currency, quantity, "active",
             "did:web:kareyanagi.etzhayyim.com", "did:web:kareyanagi.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"listingId": listing_id, "status": "active"}


def _list_listings_sync(limit: int, offset: int, seller_did: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if seller_did:
            rows = conn.execute(
                "SELECT id, seller_did, product_name, price, currency, quantity, status, created_at "
                "FROM vertex_kareyanagi_listing WHERE seller_did = ? LIMIT ? OFFSET ?",
                (seller_did, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kareyanagi_listing WHERE seller_did = ?",
                (seller_did,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, seller_did, product_name, price, currency, quantity, status, created_at "
                "FROM vertex_kareyanagi_listing LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kareyanagi_listing"
            ).fetchone()[0]

    return {
        "listings": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _create_order_sync(buyer_did: str, listing_id: str, quantity: int, owner_did: str, actor: str) -> dict[str, Any]:
    order_id = str(uuid.uuid4())
    vertex_id = f"kareyanagi:order:{order_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_kareyanagi_order
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, buyer_did, listing_id, quantity, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, owner_did,
             order_id, buyer_did, listing_id, quantity, "pending",
             "did:web:kareyanagi.etzhayyim.com", "did:web:kareyanagi.etzhayyim.com", now, now)
        )
        conn.commit()

    return {"orderId": order_id, "status": "pending"}


def _list_orders_sync(limit: int, offset: int, buyer_did: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if buyer_did:
            rows = conn.execute(
                "SELECT id, buyer_did, listing_id, quantity, status, created_at "
                "FROM vertex_kareyanagi_order WHERE buyer_did = ? LIMIT ? OFFSET ?",
                (buyer_did, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kareyanagi_order WHERE buyer_did = ?",
                (buyer_did,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, buyer_did, listing_id, quantity, status, created_at "
                "FROM vertex_kareyanagi_order LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kareyanagi_order"
            ).fetchone()[0]

    return {
        "orders": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _update_inventory_sync(listing_id: str, delta: int, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_kareyanagi_listing SET quantity = quantity + ?, updated_at = ? WHERE id = ?",
            (delta, now, listing_id)
        )
        conn.commit()

    return {"listingId": listing_id, "delta": delta, "updatedAt": now}


def _get_inventory_sync(listing_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, product_name, quantity, status FROM vertex_kareyanagi_listing WHERE id = ?",
            (listing_id,)
        ).fetchone()

    if not row:
        return {"error": "not found"}
    return dict(row)


def _process_trade_sync(order_id: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_kareyanagi_order SET status = 'completed', updated_at = ? WHERE id = ?",
            (now, order_id)
        )
        conn.commit()

    return {"orderId": order_id, "status": "completed", "processedAt": now}


def _get_trade_history_sync(limit: int, offset: int, seller_did: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if seller_did:
            rows = conn.execute(
                "SELECT o.id, o.buyer_did, o.listing_id, o.quantity, o.status, o.created_at "
                "FROM vertex_kareyanagi_order o "
                "JOIN vertex_kareyanagi_listing l ON o.listing_id = l.id "
                "WHERE l.seller_did = ? ORDER BY o.created_at DESC LIMIT ? OFFSET ?",
                (seller_did, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kareyanagi_order o "
                "JOIN vertex_kareyanagi_listing l ON o.listing_id = l.id WHERE l.seller_did = ?",
                (seller_did,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, buyer_did, listing_id, quantity, status, created_at "
                "FROM vertex_kareyanagi_order ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_kareyanagi_order"
            ).fetchone()[0]

    return {
        "trades": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.createListing")
    async def task_create_listing(**kwargs):
        return await asyncio.to_thread(
            _create_listing_sync,
            kwargs.get("sellerDid", ""),
            kwargs.get("productName", ""),
            float(kwargs.get("price", 0.0)),
            kwargs.get("currency", "JPY"),
            int(kwargs.get("quantity", 0)),
            kwargs.get("ownerDid", "did:web:kareyanagi.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.listListings")
    async def task_list_listings(**kwargs):
        return await asyncio.to_thread(
            _list_listings_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("sellerDid", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.createOrder")
    async def task_create_order(**kwargs):
        return await asyncio.to_thread(
            _create_order_sync,
            kwargs.get("buyerDid", ""),
            kwargs.get("listingId", ""),
            int(kwargs.get("quantity", 1)),
            kwargs.get("ownerDid", "did:web:kareyanagi.etzhayyim.com"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.listOrders")
    async def task_list_orders(**kwargs):
        return await asyncio.to_thread(
            _list_orders_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("buyerDid", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.updateInventory")
    async def task_update_inventory(**kwargs):
        return await asyncio.to_thread(
            _update_inventory_sync,
            kwargs.get("listingId", ""),
            int(kwargs.get("delta", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.getInventory")
    async def task_get_inventory(**kwargs):
        return await asyncio.to_thread(
            _get_inventory_sync,
            kwargs.get("listingId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.processTrade")
    async def task_process_trade(**kwargs):
        return await asyncio.to_thread(
            _process_trade_sync,
            kwargs.get("orderId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.kareyanagi.getTradeHistory")
    async def task_get_trade_history(**kwargs):
        return await asyncio.to_thread(
            _get_trade_history_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("sellerDid", ""),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
