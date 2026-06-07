"""videos.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.videos.uploadVideo")
    async def task_upload_video(**kwargs):
        title = kwargs.get("title", "")
        owner_did = kwargs.get("ownerDid", "did:web:videos.etzhayyim.com")
        blob_key = kwargs.get("blobKey", "")

        video_id = str(uuid.uuid4())
        vertex_id = f"videos:video:{video_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_videos_video
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, title, blob_key, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, owner_did,
                video_id, title, blob_key, "uploaded",
                "did:web:videos.etzhayyim.com", "did:web:videos.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"id": video_id, "status": "uploaded", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.videos.getVideo")
    async def task_get_video(**kwargs):
        video_id = kwargs.get("id", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, blob_key, status, created_at, updated_at "
                "FROM vertex_videos_video WHERE id = $1",
                video_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.videos.updateVideo")
    async def task_update_video(**kwargs):
        video_id = kwargs.get("id", "")
        title = kwargs.get("title", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_videos_video SET title = $1, updated_at = $2 WHERE id = $3",
                title, now, video_id,
            )
        finally:
            await db.close()

        return {"id": video_id, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.videos.deleteVideo")
    async def task_delete_video(**kwargs):
        video_id = kwargs.get("id", "")

        db = await get_db()
        try:
            await db.execute(
                "DELETE FROM vertex_videos_video WHERE id = $1",
                video_id,
            )
        finally:
            await db.close()

        return {"id": video_id, "deleted": True}

    @worker.task(task_type="com.etzhayyim.apps.videos.listVideos")
    async def task_list_videos(**kwargs):
        status = kwargs.get("status", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT id, title, blob_key, status, created_at FROM vertex_videos_video "
                    "WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_videos_video WHERE status = $1", status
                )
            else:
                rows = await db.fetch(
                    "SELECT id, title, blob_key, status, created_at FROM vertex_videos_video "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_videos_video"
                )
        finally:
            await db.close()

        return {
            "videos": [dict(r) for r in rows],
            "total": total_row["cnt"] if total_row else 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.videos.transcodeVideo")
    async def task_transcode_video(**kwargs):
        video_id = kwargs.get("id", "")
        target_format = kwargs.get("targetFormat", "mp4")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_videos_video SET status = 'transcoding', updated_at = $1 WHERE id = $2",
                now, video_id,
            )
        finally:
            await db.close()

        return {"id": video_id, "status": "transcoding", "targetFormat": target_format, "startedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.videos.publishVideo")
    async def task_publish_video(**kwargs):
        video_id = kwargs.get("id", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_videos_video SET status = 'published', updated_at = $1 WHERE id = $2",
                now, video_id,
            )
        finally:
            await db.close()

        return {"id": video_id, "status": "published", "publishedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.videos.videoStats")
    async def task_video_stats(**kwargs):
        video_id = kwargs.get("id", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, status, created_at FROM vertex_videos_video WHERE id = $1",
                video_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return {"videoId": video_id, "status": row["status"], "views": 0, "createdAt": str(row["created_at"])}

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
