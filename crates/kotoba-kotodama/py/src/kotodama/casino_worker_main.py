"""casino.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.casino.listCasinos")
    async def task_list_casinos(**kwargs):
        city = kwargs.get("city", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if city:
                rows = await db.fetch(
                    "SELECT id, name, city, country, license_status, created_at FROM vertex_casino_casino "
                    "WHERE city = $1 ORDER BY name LIMIT $2 OFFSET $3",
                    city, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_casino_casino WHERE city = $1", city
                )
            else:
                rows = await db.fetch(
                    "SELECT id, name, city, country, license_status, created_at FROM vertex_casino_casino "
                    "ORDER BY name LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_casino_casino")
        finally:
            await db.close()

        return {
            "casinos": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.casino.getCasino")
    async def task_get_casino(**kwargs):
        casino_id = kwargs.get("casinoId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, city, country, license_status, description, created_at "
                "FROM vertex_casino_casino WHERE id = $1",
                casino_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.casino.createReview")
    async def task_create_review(**kwargs):
        casino_id = kwargs.get("casinoId", "")
        reviewer_did = kwargs.get("reviewerDid", "did:web:casino.etzhayyim.com")
        rating = int(kwargs.get("rating", 3))
        content = kwargs.get("content", "")

        review_id = str(uuid.uuid4())
        vertex_id = f"casino:review:{review_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_casino_review
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, casino_id, reviewer_did, rating, content,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, reviewer_did,
                review_id, casino_id, reviewer_did, rating, content,
                "did:web:casino.etzhayyim.com", "did:web:casino.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"reviewId": review_id, "casinoId": casino_id, "rating": rating, "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.casino.listReviews")
    async def task_list_reviews(**kwargs):
        casino_id = kwargs.get("casinoId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, casino_id, reviewer_did, rating, content, created_at FROM vertex_casino_review "
                "WHERE casino_id = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                casino_id, limit, offset,
            )
            total = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_casino_review WHERE casino_id = $1", casino_id
            )
        finally:
            await db.close()

        return {
            "reviews": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.casino.listJurisdictions")
    async def task_list_jurisdictions(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        jurisdictions = [
            {"code": "MGA", "name": "Malta Gaming Authority", "country": "MT", "status": "active"},
            {"code": "UKGC", "name": "UK Gambling Commission", "country": "GB", "status": "active"},
            {"code": "GGC", "name": "Gibraltar Gambling Commission", "country": "GI", "status": "active"},
            {"code": "CGA", "name": "Curaçao Gaming Authority", "country": "CW", "status": "active"},
        ]

        return {
            "jurisdictions": jurisdictions[offset:offset + limit],
            "total": len(jurisdictions),
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.casino.getJurisdiction")
    async def task_get_jurisdiction(**kwargs):
        jurisdiction_code = kwargs.get("jurisdictionCode", "")

        jurisdictions = {
            "MGA": {"code": "MGA", "name": "Malta Gaming Authority", "country": "MT", "status": "active", "established": "2001"},
            "UKGC": {"code": "UKGC", "name": "UK Gambling Commission", "country": "GB", "status": "active", "established": "2005"},
        }

        result = jurisdictions.get(jurisdiction_code)
        if not result:
            return {"error": "not found"}
        return result

    @worker.task(task_type="com.etzhayyim.apps.casino.searchCasinos")
    async def task_search_casinos(**kwargs):
        query = kwargs.get("query", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, name, city, country, license_status, created_at FROM vertex_casino_casino "
                "WHERE name ILIKE $1 ORDER BY name LIMIT $2 OFFSET $3",
                f"%{query}%", limit, offset,
            )
            total = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_casino_casino WHERE name ILIKE $1",
                f"%{query}%",
            )
        finally:
            await db.close()

        return {
            "casinos": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.casino.listCities")
    async def task_list_cities(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT DISTINCT city, country FROM vertex_casino_casino ORDER BY city LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval(
                "SELECT COUNT(DISTINCT city) FROM vertex_casino_casino"
            )
        finally:
            await db.close()

        return {
            "cities": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
