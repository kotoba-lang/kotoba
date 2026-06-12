"""oshiete.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("OSHIETE_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"oshiete-{safe}.db"


# ---------------------------------------------------------------------------
# Schema bootstrap
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS vertex_oshiete_question (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    title           TEXT NOT NULL DEFAULT '',
    body            TEXT NOT NULL DEFAULT '',
    topic           TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_oshiete_answer (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    question_id     TEXT NOT NULL DEFAULT '',
    body            TEXT NOT NULL DEFAULT '',
    vote_count      INTEGER NOT NULL DEFAULT 0,
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
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
# Synchronous helpers
# ---------------------------------------------------------------------------

def _submit_question_sync(actor_did: str, title: str, body: str, topic: str, actor: str) -> dict[str, Any]:
    question_id = str(uuid.uuid4())
    vertex_id = f"oshiete:question:{question_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_oshiete_question
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, title, body, topic, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, actor_did,
             question_id, title, body, topic, "open",
             "did:web:oshiete.etzhayyim.com", "did:web:oshiete.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"questionId": question_id, "status": "open"}


def _list_questions_sync(topic: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if topic:
            rows = conn.execute(
                "SELECT id, title, topic, status, created_at FROM vertex_oshiete_question "
                "WHERE topic = ? ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (topic, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_oshiete_question WHERE topic = ?",
                (topic,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, title, topic, status, created_at FROM vertex_oshiete_question "
                "ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute("SELECT COUNT(*) FROM vertex_oshiete_question").fetchone()[0]
            
    return {
        "questions": [dict(r) for r in rows],
        "total": total or 0,
        "offset": offset,
        "limit": limit,
    }


def _get_question_sync(question_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, title, body, topic, status, created_at, updated_at "
            "FROM vertex_oshiete_question WHERE id = ?",
            (question_id,)
        ).fetchone()
        
    if not row:
        return {"error": "not found"}
    return dict(row)


def _submit_answer_sync(actor_did: str, question_id: str, body: str, actor: str) -> dict[str, Any]:
    answer_id = str(uuid.uuid4())
    vertex_id = f"oshiete:answer:{answer_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()
    
    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_oshiete_answer
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, question_id, body, vote_count,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, actor_did,
             answer_id, question_id, body, 0,
             "did:web:oshiete.etzhayyim.com", "did:web:oshiete.etzhayyim.com", now, now)
        )
        conn.commit()
        
    return {"answerId": answer_id, "questionId": question_id}


def _list_answers_sync(question_id: str, limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, question_id, body, vote_count, created_at FROM vertex_oshiete_answer "
            "WHERE question_id = ? ORDER BY vote_count DESC, created_at ASC LIMIT ? OFFSET ?",
            (question_id, limit, offset)
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM vertex_oshiete_answer WHERE question_id = ?",
            (question_id,)
        ).fetchone()[0]
            
    return {
        "answers": [dict(r) for r in rows],
        "total": total or 0,
        "offset": offset,
        "limit": limit,
    }


def _vote_answer_sync(answer_id: str, direction: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    with _open(actor) as conn:
        if direction == "up":
            conn.execute(
                "UPDATE vertex_oshiete_answer SET vote_count = vote_count + 1, updated_at = ? WHERE id = ?",
                (now, answer_id)
            )
        else:
            conn.execute(
                "UPDATE vertex_oshiete_answer SET vote_count = vote_count - 1, updated_at = ? WHERE id = ?",
                (now, answer_id)
            )
        conn.commit()
        
        row = conn.execute(
            "SELECT id, vote_count FROM vertex_oshiete_answer WHERE id = ?",
            (answer_id,)
        ).fetchone()
        
    if not row:
        return {"error": "not found"}
    return {"answerId": answer_id, "voteCount": row["vote_count"], "direction": direction}


def _list_topics_sync(limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT topic, COUNT(*) AS question_count FROM vertex_oshiete_question "
            "WHERE topic IS NOT NULL AND topic != '' "
            "GROUP BY topic ORDER BY question_count DESC LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
            
    return {
        "topics": [dict(r) for r in rows],
        "offset": offset,
        "limit": limit,
    }


def _get_expert_sync(topic: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT a.actor_did, COUNT(*) AS answer_count, SUM(a.vote_count) AS total_votes "
            "FROM vertex_oshiete_answer a "
            "JOIN vertex_oshiete_question q ON q.id = a.question_id "
            "WHERE q.topic = ? "
            "GROUP BY a.actor_did ORDER BY total_votes DESC LIMIT 10",
            (topic,)
        ).fetchall()
            
    return {
        "topic": topic,
        "experts": [dict(r) for r in rows],
    }


# ---------------------------------------------------------------------------
# Worker & Tasks
# ---------------------------------------------------------------------------

async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.oshiete.submit.question")
    async def task_submit_question(**kwargs):
        return await asyncio.to_thread(
            _submit_question_sync,
            kwargs.get("actorDid", "did:web:oshiete.etzhayyim.com"),
            kwargs.get("title", ""),
            kwargs.get("body", ""),
            kwargs.get("topic", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.oshiete.list.questions")
    async def task_list_questions(**kwargs):
        return await asyncio.to_thread(
            _list_questions_sync,
            kwargs.get("topic", ""),
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.oshiete.get.question")
    async def task_get_question(**kwargs):
        return await asyncio.to_thread(
            _get_question_sync,
            kwargs.get("questionId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.oshiete.submit.answer")
    async def task_submit_answer(**kwargs):
        return await asyncio.to_thread(
            _submit_answer_sync,
            kwargs.get("actorDid", "did:web:oshiete.etzhayyim.com"),
            kwargs.get("questionId", ""),
            kwargs.get("body", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.oshiete.list.answers")
    async def task_list_answers(**kwargs):
        return await asyncio.to_thread(
            _list_answers_sync,
            kwargs.get("questionId", ""),
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.oshiete.vote.answer")
    async def task_vote_answer(**kwargs):
        return await asyncio.to_thread(
            _vote_answer_sync,
            kwargs.get("answerId", ""),
            kwargs.get("direction", "up"),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.oshiete.list.topics")
    async def task_list_topics(**kwargs):
        return await asyncio.to_thread(
            _list_topics_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.oshiete.get.expert")
    async def task_get_expert(**kwargs):
        return await asyncio.to_thread(
            _get_expert_sync,
            kwargs.get("topic", ""),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
