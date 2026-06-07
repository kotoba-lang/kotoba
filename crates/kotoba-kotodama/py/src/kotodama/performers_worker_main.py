"""performers.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.performers.create.profile")
    async def task_create_profile(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:performers.etzhayyim.com")
        display_name = kwargs.get("displayName", "")
        genre = kwargs.get("genre", "")
        bio = kwargs.get("bio", "")

        profile_id = str(uuid.uuid4())
        vertex_id = f"performers:profile:{profile_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_performers_profile
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, display_name, genre, bio, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, actor_did,
                profile_id, display_name, genre, bio, "active",
                "did:web:performers.etzhayyim.com", "did:web:performers.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"profileId": profile_id, "status": "active"}

    @worker.task(task_type="com.etzhayyim.apps.performers.list.profiles")
    async def task_list_profiles(**kwargs):
        genre = kwargs.get("genre", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if genre:
                rows = await db.fetch(
                    "SELECT id, display_name, genre, status, created_at FROM vertex_performers_profile "
                    "WHERE genre = $1 AND status = 'active' ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    genre, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_performers_profile WHERE genre = $1 AND status = 'active'", genre
                )
            else:
                rows = await db.fetch(
                    "SELECT id, display_name, genre, status, created_at FROM vertex_performers_profile "
                    "WHERE status = 'active' ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_performers_profile WHERE status = 'active'"
                )
        finally:
            await db.close()

        return {
            "profiles": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.performers.get.profile")
    async def task_get_profile(**kwargs):
        profile_id = kwargs.get("profileId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, display_name, genre, bio, status, created_at, updated_at "
                "FROM vertex_performers_profile WHERE id = $1",
                profile_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.performers.create.booking")
    async def task_create_booking(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:performers.etzhayyim.com")
        profile_id = kwargs.get("profileId", "")
        event_date = kwargs.get("eventDate", "")
        venue = kwargs.get("venue", "")

        booking_id = str(uuid.uuid4())
        vertex_id = f"performers:booking:{booking_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_performers_booking
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, profile_id, event_date, venue, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, actor_did,
                booking_id, profile_id, event_date, venue, "pending",
                "did:web:performers.etzhayyim.com", "did:web:performers.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"bookingId": booking_id, "status": "pending"}

    @worker.task(task_type="com.etzhayyim.apps.performers.list.bookings")
    async def task_list_bookings(**kwargs):
        profile_id = kwargs.get("profileId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if profile_id:
                rows = await db.fetch(
                    "SELECT id, profile_id, event_date, venue, status, created_at FROM vertex_performers_booking "
                    "WHERE profile_id = $1 ORDER BY event_date DESC LIMIT $2 OFFSET $3",
                    profile_id, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_performers_booking WHERE profile_id = $1", profile_id
                )
            else:
                rows = await db.fetch(
                    "SELECT id, profile_id, event_date, venue, status, created_at FROM vertex_performers_booking "
                    "ORDER BY event_date DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_performers_booking")
        finally:
            await db.close()

        return {
            "bookings": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.performers.record.performance")
    async def task_record_performance(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:performers.etzhayyim.com")
        booking_id = kwargs.get("bookingId", "")
        notes = kwargs.get("notes", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_performers_booking SET status = 'completed', updated_at = $1 WHERE id = $2",
                now, booking_id,
            )
        finally:
            await db.close()

        return {"bookingId": booking_id, "status": "completed", "recordedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.performers.list.performances")
    async def task_list_performances(**kwargs):
        profile_id = kwargs.get("profileId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, profile_id, event_date, venue, status, created_at FROM vertex_performers_booking "
                "WHERE status = 'completed' AND profile_id = $1 ORDER BY event_date DESC LIMIT $2 OFFSET $3",
                profile_id, limit, offset,
            )
            total = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_performers_booking WHERE status = 'completed' AND profile_id = $1",
                profile_id,
            )
        finally:
            await db.close()

        return {
            "performances": [dict(r) for r in rows],
            "total": total or 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.performers.submit.review")
    async def task_submit_review(**kwargs):
        actor_did = kwargs.get("actorDid", "did:web:performers.etzhayyim.com")
        profile_id = kwargs.get("profileId", "")
        rating = int(kwargs.get("rating", 5))
        comment = kwargs.get("comment", "")

        review_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        return {
            "reviewId": review_id,
            "profileId": profile_id,
            "rating": rating,
            "submittedAt": now,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
