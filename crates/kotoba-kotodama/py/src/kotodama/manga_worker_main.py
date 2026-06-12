"""manga.etzhayyim.com — LangServer worker (BPMN service task handlers).

12 methods: createTitle / createChapter / publishChapter / updateChapterStatus /
            recordReadingProgress / submitFromNarou / addTag / getTitle /
            listTitles / getChapter / listChapters / searchTitles
"""

import asyncio
import os
import uuid
from datetime import datetime, date

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")
DB_URL = os.getenv(
    "DATABASE_URL",
    "REDACTED_USE_DATABASE_URL_ENV",
)

ACTOR_DID = "did:web:manga.etzhayyim.com"


async def get_db():
    return await asyncpg.connect(DB_URL)


def _now_iso() -> str:
    return datetime.utcnow().isoformat()


def _today() -> date:
    return date.today()


def _vid(collection: str, id_: str) -> str:
    return f"at://{ACTOR_DID}/{collection}/{id_}"


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    # ── createTitle ──────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.createTitle")
    async def task_create_title(**kwargs):
        title_id = str(uuid.uuid4())
        series_id = str(uuid.uuid4())
        now = _now_iso()
        collection = "com.etzhayyim.apps.manga.title"
        vertex_id = _vid(collection, title_id)

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_manga_title
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    rkey, repo, did, collection, status,
                    id, series_id, user_id, title, description, genre,
                    thumbnail_key, coin_price, wait_free_hours, tags,
                    org_id, actor_id, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                           $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
                           $21,$22,$23,$24)""",
                vertex_id, 0, _today(), 0, ACTOR_DID,
                title_id, ACTOR_DID, ACTOR_DID, collection, "draft",
                title_id, series_id,
                kwargs.get("user_id", "anon"),
                kwargs.get("title", ""),
                kwargs.get("description", ""),
                kwargs.get("genre", ""),
                kwargs.get("thumbnail_key", ""),
                int(kwargs.get("coin_price", 0)),
                int(kwargs.get("wait_free_hours", 24)),
                "",
                kwargs.get("org_id", "anon"),
                ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"id": title_id, "series_id": series_id, "createdAt": now}

    # ── createChapter ─────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.createChapter")
    async def task_create_chapter(**kwargs):
        title_id = kwargs.get("title_id", "")
        if not title_id:
            return {"error": "title_id required"}

        chapter_id = str(uuid.uuid4())
        now = _now_iso()
        collection = "com.etzhayyim.apps.manga.chapter"
        vertex_id = _vid(collection, chapter_id)

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_manga_chapter
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    rkey, repo, did, collection, status,
                    id, title_id, user_id, chapter_num, episode_title,
                    asset_manifest_uri, page_count, published_at,
                    org_id, actor_id, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                           $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)""",
                vertex_id, 0, _today(), 0, ACTOR_DID,
                chapter_id, ACTOR_DID, ACTOR_DID, collection, "draft",
                chapter_id, title_id,
                kwargs.get("user_id", "anon"),
                int(kwargs.get("chapter_num", 1)),
                kwargs.get("episode_title", ""),
                kwargs.get("asset_manifest_uri", ""),
                int(kwargs.get("page_count", 0)),
                "",
                kwargs.get("org_id", "anon"),
                ACTOR_DID, now, now,
            )
        finally:
            await db.close()

        return {"id": chapter_id, "title_id": title_id, "createdAt": now}

    # ── publishChapter ────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.publishChapter")
    async def task_publish_chapter(**kwargs):
        chapter_id = kwargs.get("chapter_id", "")
        if not chapter_id:
            return {"error": "chapter_id required"}

        now = _now_iso()
        db = await get_db()
        try:
            await db.execute(
                "UPDATE vertex_manga_chapter "
                "SET status = $1, published_at = $2, updated_at = $3 "
                "WHERE id = $4",
                "published", now, now, chapter_id,
            )
        finally:
            await db.close()

        return {"chapter_id": chapter_id, "status": "published", "publishedAt": now}

    # ── updateChapterStatus ───────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.updateChapterStatus")
    async def task_update_chapter_status(**kwargs):
        chapter_id = kwargs.get("chapter_id", "")
        status = kwargs.get("status", "")
        if not chapter_id or not status:
            return {"error": "chapter_id and status required"}

        now = _now_iso()
        db = await get_db()
        try:
            asset_manifest_uri = kwargs.get("asset_manifest_uri")
            page_count = kwargs.get("page_count")
            if asset_manifest_uri is not None and page_count is not None:
                await db.execute(
                    "UPDATE vertex_manga_chapter "
                    "SET status = $1, asset_manifest_uri = $2, page_count = $3, updated_at = $4 "
                    "WHERE id = $5",
                    status, str(asset_manifest_uri), int(page_count), now, chapter_id,
                )
            elif asset_manifest_uri is not None:
                await db.execute(
                    "UPDATE vertex_manga_chapter "
                    "SET status = $1, asset_manifest_uri = $2, updated_at = $3 "
                    "WHERE id = $4",
                    status, str(asset_manifest_uri), now, chapter_id,
                )
            elif page_count is not None:
                await db.execute(
                    "UPDATE vertex_manga_chapter "
                    "SET status = $1, page_count = $2, updated_at = $3 "
                    "WHERE id = $4",
                    status, int(page_count), now, chapter_id,
                )
            else:
                await db.execute(
                    "UPDATE vertex_manga_chapter SET status = $1, updated_at = $2 WHERE id = $3",
                    status, now, chapter_id,
                )
        finally:
            await db.close()

        return {"chapter_id": chapter_id, "status": status, "updatedAt": now}

    # ── recordReadingProgress ─────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.recordReadingProgress")
    async def task_record_reading_progress(**kwargs):
        user_id = kwargs.get("user_id", "")
        title_id = kwargs.get("title_id", "")
        chapter_id = kwargs.get("chapter_id", "")
        if not user_id or not title_id or not chapter_id:
            return {"error": "user_id, title_id, chapter_id required"}

        progress_id = f"prog_{user_id}_{title_id}"
        now = _now_iso()
        last_page = int(kwargs.get("last_page", 0))
        collection = "com.etzhayyim.apps.manga.readingProgress"

        db = await get_db()
        try:
            existing = await db.fetchrow(
                "SELECT id FROM vertex_manga_reading_progress WHERE id = $1 LIMIT 1",
                progress_id,
            )
            if existing:
                await db.execute(
                    "UPDATE vertex_manga_reading_progress "
                    "SET chapter_id = $1, last_page = $2, updated_at = $3 "
                    "WHERE id = $4",
                    chapter_id, last_page, now, progress_id,
                )
            else:
                vertex_id = _vid(collection, progress_id)
                await db.execute(
                    """INSERT INTO vertex_manga_reading_progress
                       (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                        rkey, repo, did, collection, status,
                        id, user_id, chapter_id, title_id, last_page,
                        org_id, actor_id, created_at, updated_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                               $11,$12,$13,$14,$15,$16,$17,$18,$19)""",
                    vertex_id, 0, _today(), 1, ACTOR_DID,
                    progress_id, ACTOR_DID, ACTOR_DID, collection, "active",
                    progress_id, user_id, chapter_id, title_id, last_page,
                    kwargs.get("org_id", "anon"),
                    ACTOR_DID, now, now,
                )
        finally:
            await db.close()

        return {"id": progress_id, "user_id": user_id, "title_id": title_id, "chapter_id": chapter_id, "last_page": last_page}

    # ── submitFromNarou ───────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.submitFromNarou")
    async def task_submit_from_narou(**kwargs):
        narou_title_id = kwargs.get("narou_title_id", "")
        if not narou_title_id:
            return {"error": "narou_title_id required"}

        title_id = str(uuid.uuid4())
        series_id = f"series_{narou_title_id}"
        now = _now_iso()
        collection_title = "com.etzhayyim.apps.manga.title"

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_manga_title
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    rkey, repo, did, collection, status,
                    id, series_id, user_id, title, description, genre,
                    thumbnail_key, coin_price, wait_free_hours, tags,
                    org_id, actor_id, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                           $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,
                           $21,$22,$23,$24)""",
                _vid(collection_title, title_id), 0, _today(), 0, ACTOR_DID,
                title_id, ACTOR_DID, ACTOR_DID, collection_title, "draft",
                title_id, series_id,
                kwargs.get("user_id", "anon"),
                kwargs.get("title", ""),
                kwargs.get("description", ""),
                kwargs.get("genre", ""),
                kwargs.get("thumbnail_key", ""),
                0, 24, "",
                kwargs.get("org_id", "anon"),
                ACTOR_DID, now, now,
            )

            chapter_id = ""
            narou_chapter_id = kwargs.get("narou_chapter_id", "")
            if narou_chapter_id:
                chapter_id = str(uuid.uuid4())
                collection_chapter = "com.etzhayyim.apps.manga.chapter"
                await db.execute(
                    """INSERT INTO vertex_manga_chapter
                       (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                        rkey, repo, did, collection, status,
                        id, title_id, user_id, chapter_num, episode_title,
                        asset_manifest_uri, page_count, published_at,
                        org_id, actor_id, created_at, updated_at)
                       VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,
                               $11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22)""",
                    _vid(collection_chapter, chapter_id), 0, _today(), 0, ACTOR_DID,
                    chapter_id, ACTOR_DID, ACTOR_DID, collection_chapter, "draft",
                    chapter_id, title_id,
                    kwargs.get("user_id", "anon"),
                    1,
                    kwargs.get("episode_title", ""),
                    kwargs.get("asset_manifest_uri", ""),
                    int(kwargs.get("page_count", 0)),
                    "",
                    kwargs.get("org_id", "anon"),
                    ACTOR_DID, now, now,
                )
        finally:
            await db.close()

        return {"title_id": title_id, "chapter_id": chapter_id, "series_id": series_id}

    # ── addTag ────────────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.addTag")
    async def task_add_tag(**kwargs):
        title_id = kwargs.get("title_id", "")
        tag = kwargs.get("tag", "").lower().strip()
        if not title_id or not tag:
            return {"error": "title_id and tag required"}

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT tags FROM vertex_manga_title WHERE id = $1 LIMIT 1", title_id
            )
            existing = (row["tags"] or "") if row else ""
            tags = f"{existing},{tag}" if existing else tag
            now = _now_iso()
            await db.execute(
                "UPDATE vertex_manga_title SET tags = $1, updated_at = $2 WHERE id = $3",
                tags, now, title_id,
            )
        finally:
            await db.close()

        return {"title_id": title_id, "tag": tag}

    # ── getTitle ──────────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.getTitle")
    async def task_get_title(**kwargs):
        id_ = kwargs.get("id", "")
        if not id_:
            return {"error": "id required"}

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT * FROM vertex_manga_title WHERE id = $1 LIMIT 1", id_
            )
            if not row:
                return {"error": "not found"}
            chapter_count = await db.fetchval(
                "SELECT COUNT(*) FROM vertex_manga_chapter WHERE title_id = $1", id_
            )
        finally:
            await db.close()

        result = dict(row)
        result["chapter_count"] = int(chapter_count or 0)
        return result

    # ── listTitles ────────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.listTitles")
    async def task_list_titles(**kwargs):
        limit = min(int(kwargs.get("limit", 50)), 100)
        offset = int(kwargs.get("offset", 0))
        genre = kwargs.get("genre", "")
        status = kwargs.get("status", "")
        user_id = kwargs.get("user_id", "")

        conditions = []
        params = []
        param_idx = 1

        if genre:
            conditions.append(f"genre = ${param_idx}")
            params.append(genre)
            param_idx += 1
        if status:
            conditions.append(f"status = ${param_idx}")
            params.append(status)
            param_idx += 1
        if user_id:
            conditions.append(f"user_id = ${param_idx}")
            params.append(user_id)
            param_idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
        params.extend([limit, offset])

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT * FROM vertex_manga_title {where} "
                f"ORDER BY created_at DESC LIMIT ${param_idx} OFFSET ${param_idx + 1}",
                *params,
            )
            total = await db.fetchval(
                f"SELECT COUNT(*) FROM vertex_manga_title {where}",
                *params[:-2],
            )
        finally:
            await db.close()

        return {
            "titles": [dict(r) for r in rows],
            "total": int(total or 0),
            "offset": offset,
            "limit": limit,
        }

    # ── getChapter ────────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.getChapter")
    async def task_get_chapter(**kwargs):
        id_ = kwargs.get("id", "")
        if not id_:
            return {"error": "id required"}

        db = await get_db()
        try:
            row = await db.fetchrow(
                "SELECT * FROM vertex_manga_chapter WHERE id = $1 LIMIT 1", id_
            )
        finally:
            await db.close()

        if not row:
            return {"error": "not found"}
        return dict(row)

    # ── listChapters ──────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.listChapters")
    async def task_list_chapters(**kwargs):
        title_id = kwargs.get("title_id", "")
        if not title_id:
            return {"error": "title_id required"}

        limit = min(int(kwargs.get("limit", 50)), 200)
        offset = int(kwargs.get("offset", 0))
        status = kwargs.get("status", "")

        db = await get_db()
        try:
            if status:
                rows = await db.fetch(
                    "SELECT * FROM vertex_manga_chapter "
                    "WHERE title_id = $1 AND status = $2 "
                    f"ORDER BY chapter_num ASC LIMIT {limit} OFFSET {offset}",
                    title_id, status,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_manga_chapter WHERE title_id = $1 AND status = $2",
                    title_id, status,
                )
            else:
                rows = await db.fetch(
                    "SELECT * FROM vertex_manga_chapter "
                    "WHERE title_id = $1 "
                    f"ORDER BY chapter_num ASC LIMIT {limit} OFFSET {offset}",
                    title_id,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_manga_chapter WHERE title_id = $1",
                    title_id,
                )
        finally:
            await db.close()

        return {
            "chapters": [dict(r) for r in rows],
            "total": int(total or 0),
            "offset": offset,
            "limit": limit,
        }

    # ── searchTitles ──────────────────────────────────────────────────────────

    @worker.task(task_type="com.etzhayyim.apps.manga.searchTitles")
    async def task_search_titles(**kwargs):
        q = kwargs.get("q", "").lower()
        if not q:
            return {"error": "q required"}

        limit = min(int(kwargs.get("limit", 20)), 50)
        offset = int(kwargs.get("offset", 0))
        genre = kwargs.get("genre", "")
        tag = kwargs.get("tag", "").lower().strip()

        conditions = []
        params = []
        param_idx = 1

        if genre:
            conditions.append(f"genre = ${param_idx}")
            params.append(genre)
            param_idx += 1

        where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        db = await get_db()
        try:
            rows = await db.fetch(
                f"SELECT * FROM vertex_manga_title {where} ORDER BY created_at DESC LIMIT 500",
                *params,
            )
        finally:
            await db.close()

        filtered = [
            r for r in rows
            if (
                q in (r["title"] or "").lower()
                or q in (r["description"] or "").lower()
                or q in (r["tags"] or "").lower()
                or (tag and tag in (r["tags"] or "").lower())
            )
        ]
        titles = filtered[offset: offset + limit]
        return {
            "titles": [dict(r) for r in titles],
            "total": len(filtered),
            "offset": offset,
            "limit": limit,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
