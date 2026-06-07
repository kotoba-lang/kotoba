"""music.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv("DATABASE_URL", "REDACTED_USE_DATABASE_URL_ENV")

ACTOR_DID = "did:web:music.etzhayyim.com"


async def get_db():
    return await asyncpg.connect(DB_URL)


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.music.createTrack")
    async def task_create_track(**kwargs):
        title = kwargs.get("title", "")
        artist_id = kwargs.get("artistId", "")
        duration_sec = int(kwargs.get("durationSec", 0))
        genre = kwargs.get("genre", "")

        track_id = str(uuid.uuid4())
        vertex_id = f"music:track:{track_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_music_track
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, title, artist_id, duration_sec, genre, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                track_id, title, artist_id, duration_sec, genre, "active",
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"trackId": track_id, "status": "active", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.music.updateTrack")
    async def task_update_track(**kwargs):
        track_id = kwargs.get("trackId", "")
        title = kwargs.get("title", "")
        genre = kwargs.get("genre", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_music_track SET title = $1, genre = $2, updated_at = $3 WHERE id = $4",
                title, genre, now, track_id,
            )
        finally:
            await db.close()

        return {"trackId": track_id, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.music.listTracks")
    async def task_list_tracks(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))
        genre = kwargs.get("genre", "")

        db = await get_db()
        try:
            if genre:
                rows = await db.fetch(
                    "SELECT id, title, artist_id, duration_sec, genre, status, created_at FROM vertex_music_track WHERE genre = $1 LIMIT $2 OFFSET $3",
                    genre, limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_music_track WHERE genre = $1", genre)
            else:
                rows = await db.fetch(
                    "SELECT id, title, artist_id, duration_sec, genre, status, created_at FROM vertex_music_track LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_music_track")
        finally:
            await db.close()

        return {"tracks": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.music.getTrack")
    async def task_get_track(**kwargs):
        track_id = kwargs.get("trackId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, artist_id, duration_sec, genre, status, created_at, updated_at FROM vertex_music_track WHERE id = $1",
                track_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.music.createArtist")
    async def task_create_artist(**kwargs):
        name = kwargs.get("name", "")
        genre = kwargs.get("genre", "")
        country = kwargs.get("country", "")

        artist_id = str(uuid.uuid4())
        vertex_id = f"music:artist:{artist_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_music_artist
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, genre, country, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, ACTOR_DID,
                artist_id, name, genre, country, "active",
                ACTOR_DID, ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"artistId": artist_id, "status": "active", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.music.updateArtist")
    async def task_update_artist(**kwargs):
        artist_id = kwargs.get("artistId", "")
        name = kwargs.get("name", "")
        genre = kwargs.get("genre", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_music_artist SET name = $1, genre = $2, updated_at = $3 WHERE id = $4",
                name, genre, now, artist_id,
            )
        finally:
            await db.close()

        return {"artistId": artist_id, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.music.listArtists")
    async def task_list_artists(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, name, genre, country, status, created_at FROM vertex_music_artist LIMIT $1 OFFSET $2",
                limit, offset,
            )
            total = await db.fetchval("SELECT COUNT(*) FROM vertex_music_artist")
        finally:
            await db.close()

        return {"artists": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.music.getArtist")
    async def task_get_artist(**kwargs):
        artist_id = kwargs.get("artistId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, genre, country, status, created_at, updated_at FROM vertex_music_artist WHERE id = $1",
                artist_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
