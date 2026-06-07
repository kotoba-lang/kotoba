"""po.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.po.create.po")
    async def task_create_po(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:po.etzhayyim.com")
        supplier_id = kwargs.get("supplierId", "")
        items = kwargs.get("items", [])
        total_amount = float(kwargs.get("totalAmount", 0.0))

        po_id = str(uuid.uuid4())
        vertex_id = f"po:purchase_order:{po_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_po_purchase_order
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, supplier_id, total_amount, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, actor_did,
                po_id, supplier_id, total_amount, "draft",
                "did:web:po.etzhayyim.com", "did:web:po.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"poId": po_id, "status": "draft"}

    @worker.task(task_type="com.etzhayyim.apps.po.list.pos")
    async def task_list_pos(**kwargs):
        status = kwargs.get("status", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT id, supplier_id, total_amount, status, created_at FROM vertex_po_purchase_order "
                    "WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_po_purchase_order WHERE status = $1", status
                )
            else:
                rows = await db.fetch(
                    "SELECT id, supplier_id, total_amount, status, created_at FROM vertex_po_purchase_order "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_po_purchase_order")
        finally:
            await db.close()

        return {
            "pos": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.po.get.po")
    async def task_get_po(**kwargs):
        po_id = kwargs.get("poId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, supplier_id, total_amount, status, created_at, updated_at "
                "FROM vertex_po_purchase_order WHERE id = $1",
                po_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.po.approve.po")
    async def task_approve_po(**kwargs):
        po_id = kwargs.get("poId", "")
        approver_did = kwargs.get("approverDid", "did:web:po.etzhayyim.com")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_po_purchase_order SET status = 'approved', updated_at = $1 WHERE id = $2",
                now, po_id,
            )
        finally:
            await db.close()

        return {"poId": po_id, "status": "approved", "approvedAt": now, "approverDid": approver_did}

    @worker.task(task_type="com.etzhayyim.apps.po.list.suppliers")
    async def task_list_suppliers(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, name, status, created_at FROM vertex_po_supplier "
                "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval("SELECT COUNT(*) FROM vertex_po_supplier")
        finally:
            await db.close()

        return {
            "suppliers": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.po.create.supplier")
    async def task_create_supplier(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:po.etzhayyim.com")
        name = kwargs.get("name", "")
        contact_email = kwargs.get("contactEmail", "")
        address = kwargs.get("address", "")

        supplier_id = str(uuid.uuid4())
        vertex_id = f"po:supplier:{supplier_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_po_supplier
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, contact_email, address, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, actor_did,
                supplier_id, name, contact_email, address, "active",
                "did:web:po.etzhayyim.com", "did:web:po.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"supplierId": supplier_id, "status": "active"}

    @worker.task(task_type="com.etzhayyim.apps.po.record.receipt")
    async def task_record_receipt(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:po.etzhayyim.com")
        po_id = kwargs.get("poId", "")
        received_items = kwargs.get("receivedItems", [])

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_po_purchase_order SET status = 'received', updated_at = $1 WHERE id = $2",
                now, po_id,
            )
        finally:
            await db.close()

        return {"poId": po_id, "status": "received", "receivedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.po.list.receipts")
    async def task_list_receipts(**kwargs):
        supplier_id = kwargs.get("supplierId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if supplier_id:
                rows = await db.fetch(
                    "SELECT id, supplier_id, total_amount, status, updated_at FROM vertex_po_purchase_order "
                    "WHERE supplier_id = $1 AND status = 'received' ORDER BY updated_at DESC LIMIT $2 OFFSET $3",
                    supplier_id, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_po_purchase_order WHERE supplier_id = $1 AND status = 'received'",
                    supplier_id,
                )
            else:
                rows = await db.fetch(
                    "SELECT id, supplier_id, total_amount, status, updated_at FROM vertex_po_purchase_order "
                    "WHERE status = 'received' ORDER BY updated_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_po_purchase_order WHERE status = 'received'"
                )
        finally:
            await db.close()

        return {
            "receipts": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
