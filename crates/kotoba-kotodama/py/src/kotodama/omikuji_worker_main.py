"""omikuji.etzhayyim.com — LangServer worker (BPMN service task handlers)."""

import asyncio
import os
import random
import sqlite3
import uuid
from datetime import datetime, date
from pathlib import Path
from typing import Any

from kotodama.langserver_compat import LangServerWorker, create_langserver_channel

AGENTGATEWAY_MCP_URL = os.getenv("AGENTGATEWAY_MCP_URL", "localhost:8080")

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("OMIKUJI_ACTOR", "default")
ACTOR_DID = "did:web:omikuji.etzhayyim.com"

FORTUNE_RESULTS = ["大吉", "吉", "中吉", "小吉", "末吉", "凶", "大凶"]


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"omikuji-{safe}.db"


_DDL = """
CREATE TABLE IF NOT EXISTS vertex_omikuji_fortune_draw (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    shrine_id       TEXT NOT NULL DEFAULT '',
    user_did        TEXT NOT NULL DEFAULT '',
    result          TEXT NOT NULL DEFAULT '',
    drawn_at        TEXT NOT NULL DEFAULT '',
    actor_did       TEXT NOT NULL DEFAULT '',
    org_did         TEXT NOT NULL DEFAULT '',
    created_at      TEXT NOT NULL DEFAULT '',
    updated_at      TEXT NOT NULL DEFAULT ''
);

CREATE TABLE IF NOT EXISTS vertex_omikuji_shrine (
    vertex_id       TEXT PRIMARY KEY,
    _seq            INTEGER NOT NULL DEFAULT 0,
    created_date    TEXT NOT NULL DEFAULT '',
    sensitivity_ord INTEGER NOT NULL DEFAULT 0,
    owner_did       TEXT NOT NULL DEFAULT '',
    id              TEXT NOT NULL DEFAULT '',
    name            TEXT NOT NULL DEFAULT '',
    location        TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',
    status          TEXT NOT NULL DEFAULT '',
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


def _draw_fortune_sync(shrine_id: str, user_did: str, actor: str) -> dict[str, Any]:
    fortune_result = random.choice(FORTUNE_RESULTS)
    draw_id = str(uuid.uuid4())
    vertex_id = f"omikuji:fortune_draw:{draw_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_omikuji_fortune_draw
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, shrine_id, user_did, result, drawn_at,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, ACTOR_DID,
             draw_id, shrine_id, user_did, fortune_result, now,
             ACTOR_DID, ACTOR_DID, now, now)
        )
        conn.commit()

    return {"drawId": draw_id, "result": fortune_result, "drawnAt": now}


def _list_fortunes_sync(limit: int, offset: int, shrine_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        if shrine_id:
            rows = conn.execute(
                "SELECT id, shrine_id, user_did, result, drawn_at FROM vertex_omikuji_fortune_draw "
                "WHERE shrine_id = ? LIMIT ? OFFSET ?",
                (shrine_id, limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_omikuji_fortune_draw WHERE shrine_id = ?",
                (shrine_id,)
            ).fetchone()[0]
        else:
            rows = conn.execute(
                "SELECT id, shrine_id, user_did, result, drawn_at FROM vertex_omikuji_fortune_draw "
                "LIMIT ? OFFSET ?",
                (limit, offset)
            ).fetchall()
            total = conn.execute(
                "SELECT COUNT(*) FROM vertex_omikuji_fortune_draw"
            ).fetchone()[0]

    return {"fortunes": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}


def _get_fortune_sync(draw_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, shrine_id, user_did, result, drawn_at, created_at FROM vertex_omikuji_fortune_draw WHERE id = ?",
            (draw_id,)
        ).fetchone()

    if not row:
        return {"error": "not found"}
    return dict(row)


def _reset_fortune_sync(user_did: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()
    return {"userDid": user_did, "resetAt": now, "ok": True}


def _create_shrine_sync(name: str, location: str, description: str, actor: str) -> dict[str, Any]:
    shrine_id = str(uuid.uuid4())
    vertex_id = f"omikuji:shrine:{shrine_id}"
    now = datetime.utcnow().isoformat()
    today = date.today().isoformat()

    with _open(actor) as conn:
        conn.execute(
            """INSERT INTO vertex_omikuji_shrine
               (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                id, name, location, description, status,
                actor_did, org_did, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (vertex_id, 0, today, 0, ACTOR_DID,
             shrine_id, name, location, description, "active",
             ACTOR_DID, ACTOR_DID, now, now)
        )
        conn.commit()

    return {"shrineId": shrine_id, "status": "active", "createdAt": now}


def _update_shrine_sync(shrine_id: str, name: str, description: str, actor: str) -> dict[str, Any]:
    now = datetime.utcnow().isoformat()

    with _open(actor) as conn:
        conn.execute(
            "UPDATE vertex_omikuji_shrine SET name = ?, description = ?, updated_at = ? WHERE id = ?",
            (name, description, now, shrine_id)
        )
        conn.commit()

    return {"shrineId": shrine_id, "updatedAt": now}


def _list_shrines_sync(limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, name, location, status, created_at FROM vertex_omikuji_shrine LIMIT ? OFFSET ?",
            (limit, offset)
        ).fetchall()
        total = conn.execute("SELECT COUNT(*) FROM vertex_omikuji_shrine").fetchone()[0]

    return {"shrines": [dict(r) for r in rows], "total": total or 0, "offset": offset, "limit": limit}


def _get_shrine_sync(shrine_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, name, location, description, status, created_at, updated_at FROM vertex_omikuji_shrine WHERE id = ?",
            (shrine_id,)
        ).fetchone()

    if not row:
        return {"error": "not found"}
    return dict(row)


async def run_worker():
    channel = create_langserver_channel(grpc_address=AGENTGATEWAY_MCP_URL)
    worker = LangServerWorker(channel)

    @worker.task(task_type="com.etzhayyim.apps.omikuji.drawFortune")
    async def task_draw_fortune(**kwargs):
        return await asyncio.to_thread(
            _draw_fortune_sync,
            kwargs.get("shrineId", ""),
            kwargs.get("userDid", ACTOR_DID),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.omikuji.listFortunes")
    async def task_list_fortunes(**kwargs):
        return await asyncio.to_thread(
            _list_fortunes_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("shrineId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.omikuji.getFortune")
    async def task_get_fortune(**kwargs):
        return await asyncio.to_thread(
            _get_fortune_sync,
            kwargs.get("drawId", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.omikuji.resetFortune")
    async def task_reset_fortune(**kwargs):
        return await asyncio.to_thread(
            _reset_fortune_sync,
            kwargs.get("userDid", ACTOR_DID),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.omikuji.createShrine")
    async def task_create_shrine(**kwargs):
        return await asyncio.to_thread(
            _create_shrine_sync,
            kwargs.get("name", ""),
            kwargs.get("location", ""),
            kwargs.get("description", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.omikuji.updateShrine")
    async def task_update_shrine(**kwargs):
        return await asyncio.to_thread(
            _update_shrine_sync,
            kwargs.get("shrineId", ""),
            kwargs.get("name", ""),
            kwargs.get("description", ""),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.omikuji.listShrines")
    async def task_list_shrines(**kwargs):
        return await asyncio.to_thread(
            _list_shrines_sync,
            int(kwargs.get("limit", 50)),
            int(kwargs.get("offset", 0)),
            kwargs.get("actor", _ACTOR)
        )

    @worker.task(task_type="com.etzhayyim.apps.omikuji.getShrine")
    async def task_get_shrine(**kwargs):
        return await asyncio.to_thread(
            _get_shrine_sync,
            kwargs.get("shrineId", ""),
            kwargs.get("actor", _ACTOR)
        )

    await worker.work()


if __name__ == "__main__":
    asyncio.run(run_worker())
