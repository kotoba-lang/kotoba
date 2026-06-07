"""lo.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv("DATABASE_URL", "REDACTED_USE_DATABASE_URL_ENV")

ACTOR_DID = "did:web:lo.etzhayyim.com"


async def get_db():
    return await asyncpg.connect(DB_URL)


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.lo.createShipment")
    async def task_create_shipment(**kwargs):
        origin = kwargs.get("origin", "")
        destination = kwargs.get("destination", "")
        cargo_type = kwargs.get("cargoType", "")
        weight_kg = float(kwargs.get("weightKg", 0))

        shipment_id = str(uuid.uuid4())
        vertex_id = f"lo:shipment:{shipment_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_lo_shipment
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, origin, destination, cargo_type, weight_kg, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                shipment_id, origin, destination, cargo_type, weight_kg, "pending",
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"shipmentId": shipment_id, "status": "pending", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lo.updateShipment")
    async def task_update_shipment(**kwargs):
        shipment_id = kwargs.get("shipmentId", "")
        status = kwargs.get("status", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_lo_shipment SET status = $1, updated_at = $2 WHERE id = $3",
                status, now, shipment_id,
            )
        finally:
            await db.close()

        return {"shipmentId": shipment_id, "status": status, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lo.listShipments")
    async def task_list_shipments(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, origin, destination, cargo_type, status, created_at FROM vertex_lo_shipment LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval("SELECT COUNT(*) FROM vertex_lo_shipment")
        finally:
            await db.close()

        return {"shipments": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.lo.getShipment")
    async def task_get_shipment(**kwargs):
        shipment_id = kwargs.get("shipmentId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, origin, destination, cargo_type, weight_kg, status, created_at, updated_at FROM vertex_lo_shipment WHERE id = $1",
                shipment_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.lo.createRoute")
    async def task_create_route(**kwargs):
        name = kwargs.get("name", "")
        origin = kwargs.get("origin", "")
        destination = kwargs.get("destination", "")
        distance_km = float(kwargs.get("distanceKm", 0))

        route_id = str(uuid.uuid4())
        vertex_id = f"lo:route:{route_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_lo_route
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, origin, destination, distance_km, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                route_id, name, origin, destination, distance_km, "active",
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"routeId": route_id, "status": "active", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lo.updateRoute")
    async def task_update_route(**kwargs):
        route_id = kwargs.get("routeId", "")
        status = kwargs.get("status", "")
        name = kwargs.get("name", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_lo_route SET status = $1, name = $2, updated_at = $3 WHERE id = $4",
                status, name, now, route_id,
            )
        finally:
            await db.close()

        return {"routeId": route_id, "status": status, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.lo.listRoutes")
    async def task_list_routes(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, name, origin, destination, distance_km, status, created_at FROM vertex_lo_route LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval("SELECT COUNT(*) FROM vertex_lo_route")
        finally:
            await db.close()

        return {"routes": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.lo.getRoute")
    async def task_get_route(**kwargs):
        route_id = kwargs.get("routeId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, origin, destination, distance_km, status, created_at, updated_at FROM vertex_lo_route WHERE id = $1",
                route_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
