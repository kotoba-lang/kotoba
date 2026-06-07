"""
anime LangServer worker — Anime Intelligence Platform.

Subscribes to Zeebe job types matching the BPMN service tasks in
60-apps/etzhayyim-project-anime/bpmn/ingest-anime.bpmn.

Job types:
  com.etzhayyim.apps.anime.createTitle      — persist new anime title
  com.etzhayyim.apps.anime.createSeason     — persist season under a title
  com.etzhayyim.apps.anime.createEpisode    — persist episode under a season
  com.etzhayyim.apps.anime.createSchedule   — persist broadcast schedule slot
  com.etzhayyim.apps.anime.submitReview     — persist viewer review
  com.etzhayyim.apps.anime.listTitles       — query title list
  com.etzhayyim.apps.anime.getTitle         — query single title with seasons
  com.etzhayyim.apps.anime.listEpisodes     — query episodes for a season
  com.etzhayyim.apps.anime.searchTitles     — keyword + genre search
  com.etzhayyim.apps.anime.listSchedules    — query broadcast schedules

Run inside cluster:
    python -m kotodama.anime_worker_main

Env:
  AGENTGATEWAY_MCP_URL    — AgentGateway MCP URL (default agentgateway-mcp.mitama-udf.svc.cluster.local:8080)
  ZEEBE_TIMEOUT_SEC — per-job activation timeout (default 300)
  DATABASE_URL     — RisingWave Hyperdrive PG URL
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import time
from typing import Any

import asyncpg
from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

LOG = logging.getLogger("anime_worker")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

GATEWAY = os.environ.get("AGENTGATEWAY_MCP_URL", "agentgateway-mcp.mitama-udf.svc.cluster.local:8080")
ACTIVATION_TIMEOUT = int(os.environ.get("ZEEBE_TIMEOUT_SEC", "300"))
DATABASE_URL = os.environ.get("DATABASE_URL", "")

# ─── DB helpers ──────────────────────────────────────────────────────────

async def _conn() -> asyncpg.Connection:
    return await asyncpg.connect(DATABASE_URL)


def _gid(prefix: str) -> str:
    import random, string
    return f"{prefix}_{int(time.time() * 1000):x}_{''.join(random.choices(string.ascii_lowercase + string.digits, k=8))}"


def _now() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


def _vid(collection: str, rkey: str) -> str:
    return f"at://did:web:anime.etzhayyim.com/{collection}/{rkey}"


# ─── Mutation tasks ───────────────────────────────────────────────────────

async def task_create_title(
    title: str = "",
    title_ja: str = "",
    genre: str = "",
    tags: str = "",
    synopsis: str = "",
    studio: str = "",
    source_type: str = "",
    status: str = "ongoing",
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    if not title:
        return {"error": "title required"}
    id_ = _gid("title")
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            """
            INSERT INTO vertex_anime_title (
                vertex_id, _seq, created_date, sensitivity_ord,
                owner_did, rkey, repo, did, collection, status,
                id, title, title_ja, genre, tags, synopsis, studio,
                source_type, org_id, user_id, actor_id, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
            """,
            _vid("com.etzhayyim.apps.anime.title", id_),
            int(time.time() * 1000), now[:10], 0,
            "did:web:anime.etzhayyim.com", id_,
            "did:web:anime.etzhayyim.com", "did:web:anime.etzhayyim.com",
            "com.etzhayyim.apps.anime.title", status,
            id_, title, title_ja, genre, tags, synopsis, studio, source_type,
            org_id, user_id, "did:web:anime.etzhayyim.com", now, now,
        )
    finally:
        await db.close()
    return {"id": id_}


async def task_create_season(
    title_id: str = "",
    season_num: int = 1,
    year: int = 0,
    cour: str = "",
    episode_count: int = 0,
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    if not title_id:
        return {"error": "title_id required"}
    id_ = _gid("season")
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            """
            INSERT INTO vertex_anime_season (
                vertex_id, _seq, created_date, sensitivity_ord,
                owner_did, rkey, repo, did, collection, status,
                id, title_id, season_num, year, cour, episode_count,
                org_id, user_id, actor_id, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
            """,
            _vid("com.etzhayyim.apps.anime.season", id_),
            int(time.time() * 1000), now[:10], 0,
            "did:web:anime.etzhayyim.com", id_,
            "did:web:anime.etzhayyim.com", "did:web:anime.etzhayyim.com",
            "com.etzhayyim.apps.anime.season", "active",
            id_, title_id, season_num, year, cour, episode_count,
            org_id, user_id, "did:web:anime.etzhayyim.com", now, now,
        )
    finally:
        await db.close()
    return {"id": id_}


async def task_create_episode(
    season_id: str = "",
    episode_num: int = 1,
    title: str = "",
    air_date: str = "",
    duration_sec: int = 0,
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    if not season_id:
        return {"error": "season_id required"}
    id_ = _gid("ep")
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            """
            INSERT INTO vertex_anime_episode (
                vertex_id, _seq, created_date, sensitivity_ord,
                owner_did, rkey, repo, did, collection, status,
                id, season_id, episode_num, title, air_date, duration_sec,
                org_id, user_id, actor_id, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21)
            """,
            _vid("com.etzhayyim.apps.anime.episode", id_),
            int(time.time() * 1000), now[:10], 0,
            "did:web:anime.etzhayyim.com", id_,
            "did:web:anime.etzhayyim.com", "did:web:anime.etzhayyim.com",
            "com.etzhayyim.apps.anime.episode", "aired",
            id_, season_id, episode_num, title, air_date, duration_sec,
            org_id, user_id, "did:web:anime.etzhayyim.com", now, now,
        )
    finally:
        await db.close()
    return {"id": id_}


async def task_create_schedule(
    title_id: str = "",
    season_id: str = "",
    channel: str = "",
    day_of_week: str = "",
    time_slot: str = "",
    start_date: str = "",
    end_date: str = "",
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    if not title_id:
        return {"error": "title_id required"}
    id_ = _gid("sched")
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            """
            INSERT INTO vertex_anime_schedule (
                vertex_id, _seq, created_date, sensitivity_ord,
                owner_did, rkey, repo, did, collection, status,
                id, title_id, season_id, channel, day_of_week,
                time_slot, start_date, end_date,
                org_id, user_id, actor_id, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20,$21,$22,$23)
            """,
            _vid("com.etzhayyim.apps.anime.schedule", id_),
            int(time.time() * 1000), now[:10], 0,
            "did:web:anime.etzhayyim.com", id_,
            "did:web:anime.etzhayyim.com", "did:web:anime.etzhayyim.com",
            "com.etzhayyim.apps.anime.schedule", "active",
            id_, title_id, season_id or "", channel, day_of_week,
            time_slot, start_date, end_date,
            org_id, user_id, "did:web:anime.etzhayyim.com", now, now,
        )
    finally:
        await db.close()
    return {"id": id_}


async def task_submit_review(
    title_id: str = "",
    reviewer_did: str = "",
    rating: int = 0,
    body: str = "",
    org_id: str = "anon",
    user_id: str = "anon",
) -> dict[str, Any]:
    if not title_id:
        return {"error": "title_id required"}
    id_ = _gid("rev")
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            """
            INSERT INTO vertex_anime_review (
                vertex_id, _seq, created_date, sensitivity_ord,
                owner_did, rkey, repo, did, collection, status,
                id, title_id, reviewer_did, rating, body,
                org_id, user_id, actor_id, created_at, updated_at
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15,$16,$17,$18,$19,$20)
            """,
            _vid("com.etzhayyim.apps.anime.review", id_),
            int(time.time() * 1000), now[:10], 0,
            reviewer_did or "did:web:anime.etzhayyim.com", id_,
            "did:web:anime.etzhayyim.com", reviewer_did or "did:web:anime.etzhayyim.com",
            "com.etzhayyim.apps.anime.review", "published",
            id_, title_id, reviewer_did, max(0, min(10, rating)), body,
            org_id, user_id, "did:web:anime.etzhayyim.com", now, now,
        )
    finally:
        await db.close()
    return {"id": id_}


# ─── Query tasks ──────────────────────────────────────────────────────────

async def task_list_titles(
    genre: str = "",
    status: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    db = await _conn()
    try:
        clauses, params = [], []
        if genre:
            clauses.append(f"genre = ${len(params)+1}")
            params.append(genre)
        if status:
            clauses.append(f"status = ${len(params)+1}")
            params.append(status)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = min(limit, 200)
        params.extend([limit, offset])
        rows = await db.fetch(
            f"SELECT * FROM vertex_anime_title {where} ORDER BY created_at DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
            *params,
        )
        return {"titles": [dict(r) for r in rows], "offset": offset, "limit": limit}
    finally:
        await db.close()


async def task_get_title(id: str = "") -> dict[str, Any]:
    if not id:
        return {"error": "id required"}
    db = await _conn()
    try:
        row = await db.fetchrow("SELECT * FROM vertex_anime_title WHERE id = $1 LIMIT 1", id)
        if not row:
            return {"error": "not found"}
        seasons = await db.fetch(
            "SELECT * FROM vertex_anime_season WHERE title_id = $1 ORDER BY season_num ASC LIMIT 50", id
        )
        return {"title": dict(row), "seasons": [dict(s) for s in seasons]}
    finally:
        await db.close()


async def task_list_episodes(
    season_id: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    if not season_id:
        return {"error": "season_id required"}
    db = await _conn()
    try:
        limit = min(limit, 200)
        rows = await db.fetch(
            "SELECT * FROM vertex_anime_episode WHERE season_id = $1 ORDER BY episode_num ASC LIMIT $2 OFFSET $3",
            season_id, limit, offset,
        )
        return {"episodes": [dict(r) for r in rows], "offset": offset, "limit": limit}
    finally:
        await db.close()


async def task_search_titles(
    q: str = "",
    genre: str = "",
    limit: int = 20,
    offset: int = 0,
) -> dict[str, Any]:
    if not q:
        return {"error": "q required"}
    db = await _conn()
    try:
        limit = min(limit, 50)
        rows = await db.fetch(
            "SELECT * FROM vertex_anime_title ORDER BY created_at DESC LIMIT 500"
        )
        ql = q.lower()
        filtered = [
            dict(r) for r in rows
            if ql in (r["title"] or "").lower()
            or ql in (r["title_ja"] or "").lower()
            or ql in (r["tags"] or "").lower()
            or ql in (r["synopsis"] or "").lower()
        ]
        if genre:
            filtered = [r for r in filtered if r.get("genre") == genre]
        return {
            "titles": filtered[offset: offset + limit],
            "total": len(filtered),
            "offset": offset,
            "limit": limit,
        }
    finally:
        await db.close()


async def task_list_schedules(
    title_id: str = "",
    day_of_week: str = "",
    limit: int = 50,
    offset: int = 0,
) -> dict[str, Any]:
    db = await _conn()
    try:
        clauses, params = [], []
        if title_id:
            clauses.append(f"title_id = ${len(params)+1}")
            params.append(title_id)
        if day_of_week:
            clauses.append(f"day_of_week = ${len(params)+1}")
            params.append(day_of_week)
        where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
        limit = min(limit, 200)
        params.extend([limit, offset])
        rows = await db.fetch(
            f"SELECT * FROM vertex_anime_schedule {where} ORDER BY start_date DESC LIMIT ${len(params)-1} OFFSET ${len(params)}",
            *params,
        )
        return {"schedules": [dict(r) for r in rows], "offset": offset, "limit": limit}
    finally:
        await db.close()


# ─── Worker entrypoint ────────────────────────────────────────────────────

async def run_worker() -> None:
    channel = create_langserver_channel(grpc_address=GATEWAY)
    worker = LangServerWorker(channel)

    registrations = {
        "com.etzhayyim.apps.anime.createTitle":    task_create_title,
        "com.etzhayyim.apps.anime.createSeason":   task_create_season,
        "com.etzhayyim.apps.anime.createEpisode":  task_create_episode,
        "com.etzhayyim.apps.anime.createSchedule": task_create_schedule,
        "com.etzhayyim.apps.anime.submitReview":   task_submit_review,
        "com.etzhayyim.apps.anime.listTitles":     task_list_titles,
        "com.etzhayyim.apps.anime.getTitle":       task_get_title,
        "com.etzhayyim.apps.anime.listEpisodes":   task_list_episodes,
        "com.etzhayyim.apps.anime.searchTitles":   task_search_titles,
        "com.etzhayyim.apps.anime.listSchedules":  task_list_schedules,
    }

    for task_type, fn in registrations.items():
        worker.task(task_type=task_type, single_value=False, timeout_ms=ACTIVATION_TIMEOUT * 1000)(fn)
        LOG.info("registered: %s", task_type)

    LOG.info("anime worker starting (gateway=%s)", GATEWAY)
    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
