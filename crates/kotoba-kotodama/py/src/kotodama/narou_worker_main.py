"""
narou_worker_main.py — Narou Web Novel Platform LangServer worker.

Handles 11 BPMN task types for narou.etzhayyim.com:
  com.etzhayyim.apps.narou.createNovel
  com.etzhayyim.apps.narou.createChapter
  com.etzhayyim.apps.narou.generateChapter
  com.etzhayyim.apps.narou.publishChapter
  com.etzhayyim.apps.narou.createCharacter
  com.etzhayyim.apps.narou.createWorldSetting
  com.etzhayyim.apps.narou.getNovel
  com.etzhayyim.apps.narou.listNovels
  com.etzhayyim.apps.narou.getChapter
  com.etzhayyim.apps.narou.listChapters
  com.etzhayyim.apps.narou.searchNovels

Tables (RisingWave via asyncpg):
  vertex_narou_novel:         vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                              rkey, repo, did, collection, status, id, title, description,
                              genre, tags, user_id, org_id, actor_id, created_at, updated_at
  vertex_narou_chapter:       vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                              rkey, repo, did, collection, status, id, novel_id, chapter_num,
                              title, content, word_count, user_id, published_at,
                              asset_manifest_uri, org_id, actor_id, created_at, updated_at
  vertex_narou_character:     vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                              rkey, repo, did, collection, status, id, novel_id, name,
                              role, description, user_id, org_id, actor_id, created_at, updated_at
  vertex_narou_world_setting: vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                              rkey, repo, did, collection, status, id, novel_id, name,
                              description, user_id, org_id, actor_id, created_at, updated_at

RW rule: LIMIT must be f-string interpolated (not parameterized) per
[[conventions]] rw-psycopg3-no-param-limit.
"""

import asyncio
import logging
import os
import random
import string
import sqlite3
from datetime import date, datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

ACTOR_DID = "did:web:narou.etzhayyim.com"

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("NAROU_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"narou-{safe}.db"


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS vertex_narou_novel (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    rkey            TEXT NOT NULL DEFAULT '',
    repo            TEXT NOT NULL DEFAULT '',
    did             TEXT NOT NULL DEFAULT '',
    collection      TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    title           TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    genre           TEXT NOT NULL DEFAULT '',
    tags            TEXT NOT NULL DEFAULT '',
    user_id         TEXT NOT NULL DEFAULT '',
    org_id          TEXT NOT NULL DEFAULT '',
    actor_id        TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_narou_chapter (
    vertex_id          TEXT PRIMARY KEY,
    _seq               INTEGER NOT NULL DEFAULT 0,
    created_date       TEXT NOT NULL DEFAULT '',
    sensitivity_ord    INTEGER NOT NULL DEFAULT 0,
    owner_did          TEXT NOT NULL DEFAULT '',
    rkey               TEXT NOT NULL DEFAULT '',
    repo               TEXT NOT NULL DEFAULT '',
    did                TEXT NOT NULL DEFAULT '',
    collection         TEXT NOT NULL DEFAULT '',
    status             TEXT NOT NULL DEFAULT '',
    id                 TEXT NOT NULL DEFAULT '',
    novel_id           TEXT NOT NULL DEFAULT '',
    chapter_num        INTEGER NOT NULL DEFAULT 0,
    title              TEXT NOT NULL DEFAULT '',
    content            TEXT NOT NULL DEFAULT '',
    word_count         INTEGER NOT NULL DEFAULT 0,
    user_id            TEXT NOT NULL DEFAULT '',
    published_at       TEXT NOT NULL DEFAULT '',
    asset_manifest_uri TEXT NOT NULL DEFAULT '',
    org_id             TEXT NOT NULL DEFAULT '',
    actor_id           TEXT NOT NULL DEFAULT '',
    created_at         TEXT NOT NULL DEFAULT '',
    updated_at         TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_narou_character (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    rkey            TEXT NOT NULL DEFAULT '',
    repo            TEXT NOT NULL DEFAULT '',
    did             TEXT NOT NULL DEFAULT '',
    collection      TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    novel_id        TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    role            TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    user_id         TEXT NOT NULL DEFAULT '',
    org_id          TEXT NOT NULL DEFAULT '',
    actor_id        TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_narou_world_setting (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    rkey            TEXT NOT NULL DEFAULT '',
    repo            TEXT NOT NULL DEFAULT '',
    did             TEXT NOT NULL DEFAULT '',
    collection      TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    novel_id        TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    user_id         TEXT NOT NULL DEFAULT '',
    org_id          TEXT NOT NULL DEFAULT '',
    actor_id        TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);
"""

def _ensure_schema(conn: sqlite3.Connection) -> None:
    conn.executescript(_DDL)
    conn.commit()


def _open(actor: str = _ACTOR) -> sqlite3.Connection:
    path = _db_path(actor)
    path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(path))
    conn.row_factory = sqlite3.Row
    _ensure_schema(conn)
    return conn



# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _today() -> str:
    return date.today().isoformat()


def _gid(prefix: str) -> str:
    suffix = "".join(random.choices(string.ascii_lowercase + string.digits, k=8))
    return f"{prefix}_{int(datetime.now(timezone.utc).timestamp() * 1000):x}_{suffix}"


def _vid(collection: str, rkey: str) -> str:
    return f"at://{ACTOR_DID}/{collection}/{rkey}"


def _str(v) -> str:
    return v if isinstance(v, str) else ""


def _int(v, default: int = 0) -> int:
    try:
        return int(v)
    except (TypeError, ValueError):
        return default





# ---------------------------------------------------------------------------
# Task handlers
# ---------------------------------------------------------------------------

def _task_narou_create_novel_sync(variables: dict, actor: str) -> dict:
    """Create a new novel record."""
    title = _str(variables.get("title"))
    description = _str(variables.get("description"))
    genre = _str(variables.get("genre"))
    tags = _str(variables.get("tags"))
    user_id = _str(variables.get("user_id")) or "anon"
    org_id = _str(variables.get("org_id")) or "anon"

    novel_id = _gid("novel")
    rkey = novel_id
    now = _now_iso()

    with _open(actor) as conn:
        conn.execute(
            """
            INSERT INTO vertex_narou_novel
              (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
               rkey, repo, did, collection, status, id, title, description,
               genre, tags, user_id, org_id, actor_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (_vid("com.etzhayyim.apps.narou.novel", rkey),
            int(datetime.now(timezone.utc).timestamp() * 1000),
            _today(),
            0,
            ACTOR_DID,
            rkey,
            ACTOR_DID,
            ACTOR_DID,
            "com.etzhayyim.apps.narou.novel",
            "draft",
            novel_id,
            title,
            description,
            genre,
            tags,
            user_id,
            org_id,
            ACTOR_DID,
            now,
            now),
        )
        conn.commit()

    return {"id": novel_id, "status": "draft"}


def _task_narou_create_chapter_sync(variables: dict, actor: str) -> dict:
    """Create a chapter draft under a novel."""
    novel_id = _str(variables.get("novel_id"))
    if not novel_id:
        return {"error": "novel_id required"}

    title = _str(variables.get("title"))
    content = _str(variables.get("content"))
    chapter_num = _int(variables.get("chapter_num"), 1)
    user_id = _str(variables.get("user_id")) or "anon"
    org_id = _str(variables.get("org_id")) or "anon"

    chapter_id = _gid("chap")
    rkey = chapter_id
    now = _now_iso()

    with _open(actor) as conn:
        conn.execute(
            """
            INSERT INTO vertex_narou_chapter
              (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
               rkey, repo, did, collection, status, id, novel_id, chapter_num,
               title, content, word_count, user_id, published_at, asset_manifest_uri,
               org_id, actor_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (_vid("com.etzhayyim.apps.narou.chapter", rkey),
            int(datetime.now(timezone.utc).timestamp() * 1000),
            _today(),
            0,
            ACTOR_DID,
            rkey,
            ACTOR_DID,
            ACTOR_DID,
            "com.etzhayyim.apps.narou.chapter",
            "draft",
            chapter_id,
            novel_id,
            chapter_num,
            title,
            content,
            len(content),
            user_id,
            "",
            "",
            org_id,
            ACTOR_DID,
            now,
            now),
        )
        conn.commit()

    return {"id": chapter_id, "status": "draft"}


def _task_narou_generate_chapter_sync(variables: dict, actor: str) -> dict:
    """Generate placeholder chapter content (no LLM call — insert content placeholder)."""
    chapter_id = _str(variables.get("chapter_id"))
    if not chapter_id:
        return {"error": "chapter_id required"}

    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, title, chapter_num, novel_id FROM vertex_narou_chapter WHERE id = ? LIMIT 1",
            (chapter_id,)
        ).fetchone()
        
        if not row:
            return {"error": "not found"}

        content = (
            f"Generated chapter placeholder — chapter {row['chapter_num']}: {row['title'] or 'Untitled'}. "
            "This content was automatically generated by the Narou BPMN worker. "
            "Replace with actual LLM-generated content via the generateChapter task."
        )
        now = _now_iso()

        conn.execute(
            "UPDATE vertex_narou_chapter SET content = ?, word_count = ?, updated_at = ? WHERE id = ?",
            (content, len(content), now, chapter_id)
        )
        conn.commit()

    return {"chapter_id": chapter_id, "word_count": len(content)}


def _task_narou_publish_chapter_sync(variables: dict, actor: str) -> dict:
    """Publish a chapter (set status=published, published_at=now)."""
    chapter_id = _str(variables.get("chapter_id"))
    if not chapter_id:
        return {"error": "chapter_id required"}

    asset_manifest_uri = _str(variables.get("asset_manifest_uri"))
    now = _now_iso()

    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, status FROM vertex_narou_chapter WHERE id = ? LIMIT 1",
            (chapter_id,)
        ).fetchone()
        
        if not row:
            return {"error": "not found"}

        conn.execute(
            """
            UPDATE vertex_narou_chapter
            SET status = ?, published_at = ?, asset_manifest_uri = ?, updated_at = ?
            WHERE id = ?
            """,
            ("published", now, asset_manifest_uri, now, chapter_id)
        )
        conn.commit()

    return {"chapter_id": chapter_id, "status": "published"}


def _task_narou_create_character_sync(variables: dict, actor: str) -> dict:
    """Create a character for a novel."""
    novel_id = _str(variables.get("novel_id"))
    if not novel_id:
        return {"error": "novel_id required"}

    name = _str(variables.get("name"))
    role = _str(variables.get("role")) or "supporting"
    description = _str(variables.get("description"))
    user_id = _str(variables.get("user_id")) or "anon"
    org_id = _str(variables.get("org_id")) or "anon"

    char_id = _gid("char")
    rkey = char_id
    now = _now_iso()

    with _open(actor) as conn:
        conn.execute(
            """
            INSERT INTO vertex_narou_character
              (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
               rkey, repo, did, collection, status, id, novel_id, name,
               role, description, user_id, org_id, actor_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (_vid("com.etzhayyim.apps.narou.character", rkey),
            int(datetime.now(timezone.utc).timestamp() * 1000),
            _today(),
            0,
            ACTOR_DID,
            rkey,
            ACTOR_DID,
            ACTOR_DID,
            "com.etzhayyim.apps.narou.character",
            "active",
            char_id,
            novel_id,
            name,
            role,
            description,
            user_id,
            org_id,
            ACTOR_DID,
            now,
            now),
        )
        conn.commit()

    return {"id": char_id}


def _task_narou_create_world_setting_sync(variables: dict, actor: str) -> dict:
    """Create a world setting for a novel."""
    novel_id = _str(variables.get("novel_id"))
    if not novel_id:
        return {"error": "novel_id required"}

    name = _str(variables.get("name"))
    description = _str(variables.get("description"))
    user_id = _str(variables.get("user_id")) or "anon"
    org_id = _str(variables.get("org_id")) or "anon"

    world_id = _gid("world")
    rkey = world_id
    now = _now_iso()

    with _open(actor) as conn:
        conn.execute(
            """
            INSERT INTO vertex_narou_world_setting
              (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
               rkey, repo, did, collection, status, id, novel_id, name,
               description, user_id, org_id, actor_id, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            (_vid("com.etzhayyim.apps.narou.worldSetting", rkey),
            int(datetime.now(timezone.utc).timestamp() * 1000),
            _today(),
            0,
            ACTOR_DID,
            rkey,
            ACTOR_DID,
            ACTOR_DID,
            "com.etzhayyim.apps.narou.worldSetting",
            "active",
            world_id,
            novel_id,
            name,
            description,
            user_id,
            org_id,
            ACTOR_DID,
            now,
            now),
        )
        conn.commit()

    return {"id": world_id}


def _task_narou_get_novel_sync(variables: dict, actor: str) -> dict:
    """Get a novel by ID."""
    novel_id = _str(variables.get("id"))
    if not novel_id:
        return {"error": "id required"}

    with _open(actor) as conn:
        row = conn.execute(
            "SELECT * FROM vertex_narou_novel WHERE id = ? LIMIT 1",
            (novel_id,)
        ).fetchone()
        
        if not row:
            return {"error": "not found"}

        chapter_count_row = conn.execute(
            "SELECT count(id) AS cnt FROM vertex_narou_chapter WHERE novel_id = ?",
            (novel_id,)
        ).fetchone()
        
        chapter_count = int(chapter_count_row["cnt"]) if chapter_count_row else 0

    return {"novel": dict(row), "chapter_count": chapter_count}


def _task_narou_list_novels_sync(variables: dict, actor: str) -> dict:
    """List novel works with optional filters."""
    limit = min(_int(variables.get("limit"), 50), 100)
    offset = _int(variables.get("offset"), 0)
    genre = _str(variables.get("genre"))
    status = _str(variables.get("status"))
    user_id = _str(variables.get("user_id"))

    conditions = []
    params: list = []

    if genre:
        conditions.append("genre = ?")
        params.append(genre)
    if status:
        conditions.append("status = ?")
        params.append(status)
    if user_id:
        conditions.append("user_id = ?")
        params.append(user_id)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    sql = f"SELECT * FROM vertex_narou_novel {where_clause} ORDER BY created_at DESC LIMIT {limit} OFFSET {offset}"

    with _open(actor) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    novels = [dict(r) for r in rows]
    return {"novels": novels, "total": len(novels), "offset": offset, "limit": limit}


def _task_narou_get_chapter_sync(variables: dict, actor: str) -> dict:
    """Get a chapter by ID."""
    chapter_id = _str(variables.get("id"))
    if not chapter_id:
        return {"error": "id required"}

    with _open(actor) as conn:
        row = conn.execute(
            "SELECT * FROM vertex_narou_chapter WHERE id = ? LIMIT 1",
            (chapter_id,)
        ).fetchone()

    if not row:
        return {"error": "not found"}
    return {"chapter": dict(row)}


def _task_narou_list_chapters_sync(variables: dict, actor: str) -> dict:
    """List chapters for a novel."""
    novel_id = _str(variables.get("novel_id"))
    if not novel_id:
        return {"error": "novel_id required"}

    limit = min(_int(variables.get("limit"), 50), 200)
    offset = _int(variables.get("offset"), 0)
    status = _str(variables.get("status"))

    conditions = ["novel_id = ?"]
    params: list = [novel_id]

    if status:
        conditions.append("status = ?")
        params.append(status)

    where_clause = "WHERE " + " AND ".join(conditions)
    sql = f"SELECT * FROM vertex_narou_chapter {where_clause} ORDER BY chapter_num ASC LIMIT {limit} OFFSET {offset}"

    with _open(actor) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    chapters = [dict(r) for r in rows]
    return {"chapters": chapters, "total": len(chapters), "offset": offset, "limit": limit}


def _task_narou_search_novels_sync(variables: dict, actor: str) -> dict:
    """Search novels by keyword (app-layer post-filter; no SQL CONTAINS/LIKE per lint rule)."""
    q = _str(variables.get("q")).lower()
    if not q:
        return {"error": "q required"}

    limit = min(_int(variables.get("limit"), 20), 50)
    offset = _int(variables.get("offset"), 0)
    genre = _str(variables.get("genre"))
    tag = _str(variables.get("tag")).lower()

    conditions = []
    params: list = []

    if genre:
        conditions.append("genre = ?")
        params.append(genre)

    where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    # Fetch a wider set then post-filter in Python (no CONTAINS/STARTS WITH per lint rule)
    sql = f"SELECT * FROM vertex_narou_novel {where_clause} ORDER BY created_at DESC LIMIT 500"

    with _open(actor) as conn:
        rows = conn.execute(sql, tuple(params)).fetchall()

    def _matches(row: dict) -> bool:
        title = (row.get("title") or "").lower()
        desc = (row.get("description") or "").lower()
        tags = (row.get("tags") or "").lower()
        if q in title or q in desc or q in tags:
            return True
        if tag and tag in tags:
            return True
        return False

    all_rows = [dict(r) for r in rows]
    filtered = [r for r in all_rows if _matches(r)]
    novels = filtered[offset: offset + limit]
    return {"novels": novels, "total": len(filtered), "offset": offset, "limit": limit}














# ---------------------------------------------------------------------------
# Worker registration
# ---------------------------------------------------------------------------

def register_narou_tasks(worker):
    """Register all narou task handlers with a LangServerWorker instance."""
    from kotodama.langserver_compat import LangServerJob as Job, LangServerWorker

    _w: LangServerWorker = worker

    @_w.task(task_type="com.etzhayyim.apps.narou.createNovel", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _create_novel(job: Job):
        result = await asyncio.to_thread(_task_narou_create_novel_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.createChapter", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _create_chapter(job: Job):
        result = await asyncio.to_thread(_task_narou_create_chapter_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.generateChapter", timeout_ms=60_000, max_jobs_to_activate=3)
    async def _generate_chapter(job: Job):
        result = await asyncio.to_thread(_task_narou_generate_chapter_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.publishChapter", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _publish_chapter(job: Job):
        result = await asyncio.to_thread(_task_narou_publish_chapter_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.createCharacter", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _create_character(job: Job):
        result = await asyncio.to_thread(_task_narou_create_character_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.createWorldSetting", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _create_world_setting(job: Job):
        result = await asyncio.to_thread(_task_narou_create_world_setting_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.getNovel", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _get_novel(job: Job):
        result = await asyncio.to_thread(_task_narou_get_novel_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.listNovels", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _list_novels(job: Job):
        result = await asyncio.to_thread(_task_narou_list_novels_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.getChapter", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _get_chapter(job: Job):
        result = await asyncio.to_thread(_task_narou_get_chapter_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.listChapters", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _list_chapters(job: Job):
        result = await asyncio.to_thread(_task_narou_list_chapters_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    @_w.task(task_type="com.etzhayyim.apps.narou.searchNovels", timeout_ms=30_000, max_jobs_to_activate=5)
    async def _search_novels(job: Job):
        result = await asyncio.to_thread(_task_narou_search_novels_sync, dict(job.variables), _ACTOR)
        await job.set_success_status(variables=result)

    logger.info("Narou tasks registered (11 handlers).")


# ---------------------------------------------------------------------------
# Standalone entry point (for local testing)
# ---------------------------------------------------------------------------

async def _smoke_test():
    """Quick local smoke test — creates a novel and lists it back."""
    novel_result = await asyncio.to_thread(_task_narou_create_novel_sync, {
        "title": "Test Novel",
        "description": "A test novel for smoke testing",
        "genre": "fantasy",
        "tags": "test,fantasy",
        "user_id": "test_user",
        "org_id": "anon",
    }, _ACTOR)
    print("createNovel:", novel_result)

    if "id" in novel_result:
        chapter_result = await asyncio.to_thread(_task_narou_create_chapter_sync, {
            "novel_id": novel_result["id"],
            "title": "Chapter 1",
            "content": "Once upon a time...",
            "chapter_num": 1,
        }, _ACTOR)
        print("createChapter:", chapter_result)

        if "id" in chapter_result:
            gen_result = await asyncio.to_thread(_task_narou_generate_chapter_sync, {"chapter_id": chapter_result["id"]}, _ACTOR)
            print("generateChapter:", gen_result)

    list_result = await asyncio.to_thread(_task_narou_list_novels_sync, {"limit": 5, "offset": 0}, _ACTOR)
    print(f"listNovels: {len(list_result.get('novels', []))} novels returned")


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(_smoke_test())
