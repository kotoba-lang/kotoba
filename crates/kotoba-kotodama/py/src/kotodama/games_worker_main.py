"""games.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

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

    @worker.task(task_type="com.etzhayyim.apps.games.createTitle")
    async def task_create_title(**kwargs):
        name = kwargs.get("name", "")
        genre = kwargs.get("genre", "")
        publisher_did = kwargs.get("publisherDid", "did:web:games.etzhayyim.com")
        platform = kwargs.get("platform", "")

        title_id = str(uuid.uuid4())
        vertex_id = f"games:title:{title_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_games_title
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, name, genre, publisher_did, platform,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14)""",
                vertex_id, 0, date.today(), 0, publisher_did,
                title_id, name, genre, publisher_did, platform,
                "did:web:games.etzhayyim.com", "did:web:games.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"titleId": title_id, "name": name, "genre": genre, "createdAt": now}

    @worker.task(task_type="com.etzhayyim.apps.games.listTitles")
    async def task_list_titles(**kwargs):
        genre = kwargs.get("genre", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if genre:
                rows = await db.fetch(
                    "SELECT id, name, genre, publisher_did, platform, created_at FROM vertex_games_title "
                    "WHERE genre = $1 ORDER BY name LIMIT $2 OFFSET $3",
                    genre, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_games_title WHERE genre = $1", genre
                )
            else:
                rows = await db.fetch(
                    "SELECT id, name, genre, publisher_did, platform, created_at FROM vertex_games_title "
                    "ORDER BY name LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_games_title")
        finally:
            await db.close()

        return {
            "titles": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.games.recordScore")
    async def task_record_score(**kwargs):
        title_id = kwargs.get("titleId", "")
        player_did = kwargs.get("playerDid", "did:web:games.etzhayyim.com")
        score = int(kwargs.get("score", 0))
        level = kwargs.get("level", "")
        mode = kwargs.get("mode", "")

        score_id = str(uuid.uuid4())
        vertex_id = f"games:score:{score_id}"
        now = datetime.utcnow().isoformat()

        db = await get_db()
        try:
            await db.execute(
                """INSERT INTO vertex_games_score
                   (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                    id, title_id, player_did, score, level, mode,
                    actor_did, org_did, created_at, updated_at)
                   VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13,$14,$15)""",
                vertex_id, 0, date.today(), 0, player_did,
                score_id, title_id, player_did, score, level, mode,
                "did:web:games.etzhayyim.com", "did:web:games.etzhayyim.com", now, now,
            )
        finally:
            await db.close()

        return {"scoreId": score_id, "titleId": title_id, "playerDid": player_did, "score": score, "recordedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.games.listScores")
    async def task_list_scores(**kwargs):
        title_id = kwargs.get("titleId", "")
        player_did = kwargs.get("playerDid", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        db = await get_db()
        try:
            if title_id:
                rows = await db.fetch(
                    "SELECT id, title_id, player_did, score, level, mode, created_at FROM vertex_games_score "
                    "WHERE title_id = $1 ORDER BY score DESC LIMIT $2 OFFSET $3",
                    title_id, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_games_score WHERE title_id = $1", title_id
                )
            elif player_did:
                rows = await db.fetch(
                    "SELECT id, title_id, player_did, score, level, mode, created_at FROM vertex_games_score "
                    "WHERE player_did = $1 ORDER BY score DESC LIMIT $2 OFFSET $3",
                    player_did, limit, offset,
                )
                total = await db.fetchval(
                    "SELECT COUNT(*) FROM vertex_games_score WHERE player_did = $1", player_did
                )
            else:
                rows = await db.fetch(
                    "SELECT id, title_id, player_did, score, level, mode, created_at FROM vertex_games_score "
                    "ORDER BY score DESC LIMIT $1 OFFSET $2",
                    limit, offset,
                )
                total = await db.fetchval("SELECT COUNT(*) FROM vertex_games_score")
        finally:
            await db.close()

        return {
            "scores": [dict(r) for r in rows],
            "total": total,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.games.getLeaderboard")
    async def task_get_leaderboard(**kwargs):
        title_id = kwargs.get("titleId", "")
        mode = kwargs.get("mode", "")
        limit = int(kwargs.get("limit", 100))

        db = await get_db()
        try:
            if mode:
                rows = await db.fetch(
                    "SELECT player_did, MAX(score) AS best_score, COUNT(*) AS play_count "
                    "FROM vertex_games_score WHERE title_id = $1 AND mode = $2 "
                    "GROUP BY player_did ORDER BY best_score DESC LIMIT $3",
                    title_id, mode, limit,
                )
            else:
                rows = await db.fetch(
                    "SELECT player_did, MAX(score) AS best_score, COUNT(*) AS play_count "
                    "FROM vertex_games_score WHERE title_id = $1 "
                    "GROUP BY player_did ORDER BY best_score DESC LIMIT $2",
                    title_id, limit,
                )
        finally:
            await db.close()

        entries = []
        for i, r in enumerate(rows):
            entries.append({"rank": i + 1, "playerDid": r["player_did"], "bestScore": r["best_score"], "playCount": r["play_count"]})

        return {"titleId": title_id, "entries": entries, "total": len(entries)}

    @worker.task(task_type="com.etzhayyim.apps.games.createSession")
    async def task_create_session(**kwargs):
        title_id = kwargs.get("titleId", "")
        player_did = kwargs.get("playerDid", "did:web:games.etzhayyim.com")
        mode = kwargs.get("mode", "")

        session_id = str(uuid.uuid4())
        now = datetime.utcnow().isoformat()

        return {"sessionId": session_id, "titleId": title_id, "playerDid": player_did, "mode": mode, "startedAt": now}

    @worker.task(task_type="com.etzhayyim.apps.games.listSessions")
    async def task_list_sessions(**kwargs):
        player_did = kwargs.get("playerDid", "")
        limit = int(kwargs.get("limit", 50))
        offset = int(kwargs.get("offset", 0))

        return {
            "sessions": [],
            "total": 0,
            "offset": offset,
            "limit": limit,
        }

    @worker.task(task_type="com.etzhayyim.apps.games.getAchievements")
    async def task_get_achievements(**kwargs):
        player_did = kwargs.get("playerDid", "")
        title_id = kwargs.get("titleId", "")

        return {
            "playerDid": player_did,
            "titleId": title_id,
            "achievements": [],
            "total": 0,
        }

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
