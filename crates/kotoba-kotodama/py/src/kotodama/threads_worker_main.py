"""threads.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.threads.createThread")
    async def task_create_thread(**kwargs):
        title = kwargs.get("title", "")
        body = kwargs.get("body", "")
        author_did = kwargs.get("authorDid", "did:web:threads.etzhayyim.com")

        thread_id = str(uuid.uuid4())
        vertex_id = f"threads:thread:{thread_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_threads_thread
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, title, author_did, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)""",
                vertex_id, 0, date.today(), 0, author_did,
                thread_id, title, author_did, "open",
                "did:web:threads.etzhayyim.com", "did:web:threads.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"id": thread_id, "status": "open", "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.threads.getThread")
    async def task_get_thread(**kwargs):
        thread_id = kwargs.get("id", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, author_did, status, created_at, updated_at "
                "FROM vertex_threads_thread WHERE id = $1",
                thread_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.threads.replyThread")
    async def task_reply_thread(**kwargs):
        thread_id = kwargs.get("threadId", "")
        body = kwargs.get("body", "")
        author_did = kwargs.get("authorDid", "did:web:threads.etzhayyim.com")

        reply_id = str(uuid.uuid4())
        vertex_id = f"threads:reply:{reply_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_threads_reply
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, thread_id, author_did,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                vertex_id, 0, date.today(), 0, author_did,
                reply_id, thread_id, author_did,
                "did:web:threads.etzhayyim.com", "did:web:threads.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"replyId": reply_id, "threadId": thread_id, "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.threads.closeThread")
    async def task_close_thread(**kwargs):
        thread_id = kwargs.get("id", "")

        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_threads_thread SET status = 'closed', updated_at = $1 WHERE id = $2",
                now, thread_id,
            )
        finally:
            await db.close()

        return {"id": thread_id, "status": "closed", "closedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.threads.listThreads")
    async def task_list_threads(**kwargs):
        status = kwargs.get("status", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT id, title, author_did, status, created_at FROM vertex_threads_thread "
                    "WHERE status = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                    status, limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_threads_thread WHERE status = $1", status
                )
            else:
                rows = await db.fetch(
                    "SELECT id, title, author_did, status, created_at FROM vertex_threads_thread "
                    "ORDER BY created_at DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total_row = await db.fetchrow(
                    "SELECT COUNT(*) AS cnt FROM vertex_threads_thread"
                )
        finally:
            await db.close()

        return {
            "threads": [dict(r) for r in rows],
            "total": total_row["cnt"] if total_row else 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.threads.searchThreads")
    async def task_search_threads(**kwargs):
        query = kwargs.get("query", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                "SELECT id, title, author_did, status, created_at FROM vertex_threads_thread "
                "WHERE title = $1 ORDER BY created_at DESC LIMIT $2 OFFSET $3",
                query, limit, offset,
            )
        finally:
            await db.close()

        return {
            "threads": [dict(r) for r in rows],
            "query": query,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.threads.pinThread")
    async def task_pin_thread(**kwargs):
        thread_id = kwargs.get("id", "")
        pinned = kwargs.get("pinned", True)

        now = datetime.utcnow().isoformat()

        return {"id": thread_id, "pinned": pinned, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.threads.threadStats")
    async def task_thread_stats(**kwargs):
        thread_id = kwargs.get("id", "")

        db = await get_db()
        try:
            reply_row = await db.fetchrow(
                "SELECT COUNT(*) AS reply_count FROM vertex_threads_reply WHERE thread_id = $1",
                thread_id,
            )
        finally:
            await db.close()

        return {
            "threadId": thread_id,
            "replyCount": reply_row["reply_count"] if reply_row else 0,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
