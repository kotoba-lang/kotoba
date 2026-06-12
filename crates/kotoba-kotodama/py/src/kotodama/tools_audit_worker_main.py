"""Generic-primitive worker for com.etzhayyim.tools.audit.* — RW-free port.

Tranche F gate (a) W9 — audit log pattern.

Each invocation writes one row to ``audit_commit`` in a per-repo SQLite
database at ``${ORGANISM_SQLITE_DIR}/audit-{repo}.db``.  The table schema
mirrors the legacy ``vertex_repo_commit`` table (append-only OCEL trail).

No psycopg / RW_URL dependency.  Uses sqlite3 from the standard library.
Blocking I/O is wrapped with ``asyncio.to_thread`` so the async task handler
never blocks the event loop.
"""

from __future__ import annotations

import asyncio
import json
import os
import sqlite3
import time
import uuid
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)


def _db_path(repo: str) -> Path:
    """Return the path to the per-repo audit SQLite database."""
    safe = repo.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"audit-{safe}.db"


# ---------------------------------------------------------------------------
# Schema helpers
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS audit_commit (
    vertex_id    TEXT PRIMARY KEY,
    repo         TEXT NOT NULL,
    collection   TEXT NOT NULL,
    rkey         TEXT NOT NULL,
    action       TEXT NOT NULL,
    ts_ms        INTEGER NOT NULL,
    record_json  TEXT NOT NULL DEFAULT '{}'
);
CREATE INDEX IF NOT EXISTS idx_audit_commit_repo    ON audit_commit (repo);
CREATE INDEX IF NOT EXISTS idx_audit_commit_ts_ms   ON audit_commit (ts_ms);
"""


def _ensure_schema(conn: sqlite3.Connection) -> None:
    """Create the audit_commit table and indices if they do not exist."""
    conn.executescript(_DDL)
    conn.commit()


# ---------------------------------------------------------------------------
# Synchronous core (called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _emit_sync(
    repo: str,
    collection: str,
    rkey: str,
    action: str,
    record_json: str,
    vertex_id: str,
    ts_ms: int,
) -> None:
    """Open the per-repo SQLite DB and INSERT OR REPLACE the audit row."""
    db_path = _db_path(repo)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(str(db_path)) as conn:
        _ensure_schema(conn)
        conn.execute(
            """
            INSERT OR REPLACE INTO audit_commit
              (vertex_id, repo, collection, rkey, action, ts_ms, record_json)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (vertex_id, repo, collection, rkey, action, ts_ms, record_json),
        )
        conn.commit()


# ---------------------------------------------------------------------------
# Async task handler (public API)
# ---------------------------------------------------------------------------

async def task_audit_emit(
    *,
    repo: str = "",
    collection: str = "",
    rkey: str = "",
    action: str = "",
    recordJson: Any | None = None,
    **_ignored: Any,
) -> dict[str, Any]:
    """Insert one OCEL audit row into audit_commit (per-repo SQLite).

    Best-effort: swallows DB errors and returns ``{"error": str(exc)}`` so
    audit emission never blocks an actor cycle.  Same external semantics as
    the vendor ``emit_audit`` nodes it replaces.
    """
    if not repo or not collection or not action:
        return {"error": "repo / collection / action required"}

    rk = rkey or str(uuid.uuid4())
    ts_ms = int(time.time() * 1000)
    payload = recordJson if isinstance(recordJson, dict) else {}
    record_json = json.dumps(payload, separators=(",", ":"))
    vertex_id = f"{repo}:{collection}:{rk}:{action}"

    try:
        await asyncio.to_thread(
            _emit_sync,
            repo, collection, rk, action, record_json, vertex_id, ts_ms,
        )
    except Exception as exc:  # pragma: no cover — defensive
        return {"vertexId": vertex_id, "rkey": rk, "error": str(exc)}

    return {"vertexId": vertex_id, "rkey": rk}
