"""videos-legacy.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.list.videos")
    async def task_list_videos(**kwargs):
        channel_id = kwargs.get("channelId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            query = "SELECT id, channel_id, title, status, created_at FROM vertex_videos_legacy_video"
            params = []
            if channel_id:
                query += " WHERE channel_id = $1"
                params.append(channel_id)
            query += f" LIMIT {limit} OFFSET {offset}"
            rows = await db.fetch(query, *params)
        finally:
            await db.close()

        return {"videos": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.get.video")
    async def task_get_video(**kwargs):
        video_id = kwargs.get("videoId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, channel_id, title, status, created_at FROM vertex_videos_legacy_video WHERE id = $1",
                video_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.migrate.video")
    async def task_migrate_video(**kwargs):
        source_url = kwargs.get("sourceUrl", "")
        channel_id = kwargs.get("channelId", "")
        title = kwargs.get("title", "")

        video_id = str(uuid.uuid4())
        vertex_id = f"videos_legacy:video:{video_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_videos_legacy_video
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, channel_id, title, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, "did:web:videos-legacy.etzhayyim.com",
                video_id, channel_id, title, "migrated",
                "did:web:videos-legacy.etzhayyim.com", "did:web:videos-legacy.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"videoId": video_id, "status": "migrated", "sourceUrl": source_url}

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.list.channels")
    async def task_list_channels(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, name, status, created_at FROM vertex_videos_legacy_channel LIMIT {limit} OFFSET {offset}"
            )
        finally:
            await db.close()

        return {"channels": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.get.channel")
    async def task_get_channel(**kwargs):
        channel_id = kwargs.get("channelId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, name, status, created_at FROM vertex_videos_legacy_channel WHERE id = $1",
                channel_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.search.videos")
    async def task_search_videos(**kwargs):
        query_str = kwargs.get("query", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, channel_id, title, status, created_at FROM vertex_videos_legacy_video "
                f"WHERE title LIKE $1 LIMIT {limit} OFFSET {offset}",
                f"%{query_str}%",
            )
        finally:
            await db.close()

        return {"videos": [dict(r) for r in rows], "query": query_str, "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.get.metadata")
    async def task_get_metadata(**kwargs):
        video_id = kwargs.get("videoId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, channel_id, title, status, created_at, updated_at FROM vertex_videos_legacy_video WHERE id = $1",
                video_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return {"metadata": dict(row)}

    @worker.task(task_type="com.etzhayyim.apps.videosLegacy.list.playlists")
    async def task_list_playlists(**kwargs):
        channel_id = kwargs.get("channelId", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        return {
            "playlists": [],
            "channelId": channel_id,
            "offset": offset,
            "limit": limit,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
