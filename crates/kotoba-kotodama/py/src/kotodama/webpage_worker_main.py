"""webpage.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.webpage.create.page")
    async def task_create_page(**kwargs):
        title = kwargs.get("title", "")
        content = kwargs.get("content", "")
        author_did = kwargs.get("authorDid", "did:web:webpage.etzhayyim.com")

        page_id = str(uuid.uuid4())
        vertex_id = f"webpage:page:{page_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_webpage_page
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, title, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                vertex_id, 0, date.today(), 0, author_did,
                page_id, title, "draft",
                "did:web:webpage.etzhayyim.com", "did:web:webpage.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"pageId": page_id, "status": "draft"}

    @worker.task(task_type="com.etzhayyim.apps.webpage.list.pages")
    async def task_list_pages(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, title, status, created_at FROM vertex_webpage_page LIMIT {limit} OFFSET {offset}"
            )
        finally:
            await db.close()

        return {"pages": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.webpage.get.page")
    async def task_get_page(**kwargs):
        page_id = kwargs.get("pageId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, status, created_at, updated_at FROM vertex_webpage_page WHERE id = $1",
                page_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    @worker.task(task_type="com.etzhayyim.apps.webpage.update.page")
    async def task_update_page(**kwargs):
        page_id = kwargs.get("pageId", "")
        title = kwargs.get("title", "")
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_webpage_page SET title = $1, updated_at = $2 WHERE id = $3",
                title, now, page_id,
            )
        finally:
            await db.close()

        return {"pageId": page_id, "updatedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.webpage.publish.page")
    async def task_publish_page(**kwargs):
        page_id = kwargs.get("pageId", "")

        publish_id = str(uuid.uuid4())
        vertex_id = f"webpage:publish:{publish_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_webpage_page SET status = 'published', updated_at = $1 WHERE id = $2",
                now, page_id,
            )
            await db.execute(
                """INSERT INTO vertex_webpage_publish
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, page_id, status,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12)""",
                vertex_id, 0, date.today(), 0, "did:web:webpage.etzhayyim.com",
                publish_id, page_id, "published",
                "did:web:webpage.etzhayyim.com", "did:web:webpage.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"pageId": page_id, "publishId": publish_id, "status": "published"}

    @worker.task(task_type="com.etzhayyim.apps.webpage.list.published")
    async def task_list_published(**kwargs):
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, page_id, status, created_at FROM vertex_webpage_publish LIMIT {limit} OFFSET {offset}"
            )
        finally:
            await db.close()

        return {"published": [dict(r) for r in rows], "offset": offset, "limit": limit}

    @worker.task(task_type="com.etzhayyim.apps.webpage.get.pageStats")
    async def task_get_page_stats(**kwargs):
        page_id = kwargs.get("pageId", "")

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT id, title, status FROM vertex_webpage_page WHERE id = $1",
                page_id,
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return {"pageId": page_id, "stats": {"views": 0, "status": row["status"]}}

    @worker.task(task_type="com.etzhayyim.apps.webpage.search.pages")
    async def task_search_pages(**kwargs):
        query_str = kwargs.get("query", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT id, title, status, created_at FROM vertex_webpage_page "
                f"WHERE title LIKE $1 LIMIT {limit} OFFSET {offset}",
                f"%{query_str}%",
            )
        finally:
            await db.close()

        return {"pages": [dict(r) for r in rows], "query": query_str, "offset": offset, "limit": limit}

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
