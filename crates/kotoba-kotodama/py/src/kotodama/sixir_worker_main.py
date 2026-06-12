"""6ir.etzhayyim.com — read-cache worker (BPMN service task handlers).

Tranche F gate (a) W10 — read-cache pattern.

Serves SELECT-only queries against per-actor SQLite databases at:
    ``${ORGANISM_SQLITE_DIR}/sixir-{actor}.db``

Tables (mirroring legacy vertex_sixir_* names for migration parity):
    vertex_sixir_company  — id, ticker, name, exchange, sector, created_at
    vertex_sixir_filing   — id, company_id, filing_type, period, filed_at,
                            summary, created_at
    vertex_sixir_earnings — id, company_id, period, eps_actual,
                            eps_estimate, revenue_actual, revenue_estimate,
                            created_at

The external ingest path that seeds rows is out of scope for this worker.
Blocking SQLite calls are wrapped with ``asyncio.to_thread``.

No asyncpg / psycopg / RW_URL dependency.
ILIKE → LIKE … COLLATE NOCASE (SQLite does not have ILIKE).
"""

from __future__ import annotations

import asyncio
import os
import sqlite3
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

_ORGANISM_SQLITE_DIR = Path(
    os.getenv("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
)
_ACTOR = os.getenv("SIXIR_ACTOR", "default")


def _db_path(actor: str = _ACTOR) -> Path:
    safe = actor.replace("/", "_").replace(":", "_")
    return _ORGANISM_SQLITE_DIR / f"sixir-{safe}.db"


# ---------------------------------------------------------------------------
# Schema bootstrap (idempotent — called on first open)
# ---------------------------------------------------------------------------

_DDL = """
CREATE TABLE IF NOT EXISTS vertex_sixir_company (
    id          TEXT PRIMARY KEY,
    ticker      TEXT NOT NULL DEFAULT '',
    name        TEXT NOT NULL DEFAULT '',
    exchange    TEXT NOT NULL DEFAULT '',
    sector      TEXT NOT NULL DEFAULT '',
    created_at  TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sixir_company_created_at ON vertex_sixir_company (created_at);
CREATE INDEX IF NOT EXISTS idx_sixir_company_name       ON vertex_sixir_company (name);
CREATE INDEX IF NOT EXISTS idx_sixir_company_ticker     ON vertex_sixir_company (ticker);

CREATE TABLE IF NOT EXISTS vertex_sixir_filing (
    id           TEXT PRIMARY KEY,
    company_id   TEXT NOT NULL DEFAULT '',
    filing_type  TEXT NOT NULL DEFAULT '',
    period       TEXT NOT NULL DEFAULT '',
    filed_at     TEXT NOT NULL DEFAULT '',
    summary      TEXT NOT NULL DEFAULT '',
    created_at   TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sixir_filing_company_id ON vertex_sixir_filing (company_id);
CREATE INDEX IF NOT EXISTS idx_sixir_filing_filed_at   ON vertex_sixir_filing (filed_at);
CREATE INDEX IF NOT EXISTS idx_sixir_filing_period     ON vertex_sixir_filing (period);

CREATE TABLE IF NOT EXISTS vertex_sixir_earnings (
    id               TEXT PRIMARY KEY,
    company_id       TEXT NOT NULL DEFAULT '',
    period           TEXT NOT NULL DEFAULT '',
    eps_actual       REAL,
    eps_estimate     REAL,
    revenue_actual   REAL,
    revenue_estimate REAL,
    created_at       TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS idx_sixir_earnings_company_id ON vertex_sixir_earnings (company_id);
CREATE INDEX IF NOT EXISTS idx_sixir_earnings_period     ON vertex_sixir_earnings (period);
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
# Synchronous helpers (called via asyncio.to_thread)
# ---------------------------------------------------------------------------

def _list_companies_sync(limit: int, offset: int, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, ticker, name, exchange, sector, created_at "
            "FROM vertex_sixir_company "
            "ORDER BY created_at DESC LIMIT ? OFFSET ?",
            (limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM vertex_sixir_company"
        ).fetchone()[0]
    return {
        "companies": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _get_company_sync(company_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, ticker, name, exchange, sector, created_at "
            "FROM vertex_sixir_company WHERE id = ?",
            (company_id,),
        ).fetchone()
    if not row:
        return {"error": "not found"}
    return dict(row)


def _search_companies_sync(
    query: str, limit: int, offset: int, actor: str
) -> dict[str, Any]:
    pattern = f"%{query}%"
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, ticker, name, exchange, sector, created_at "
            "FROM vertex_sixir_company "
            "WHERE name LIKE ? COLLATE NOCASE OR ticker LIKE ? COLLATE NOCASE "
            "ORDER BY name LIMIT ? OFFSET ?",
            (pattern, pattern, limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM vertex_sixir_company "
            "WHERE name LIKE ? COLLATE NOCASE OR ticker LIKE ? COLLATE NOCASE",
            (pattern, pattern),
        ).fetchone()[0]
    return {
        "companies": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _list_filings_sync(
    company_id: str, limit: int, offset: int, actor: str
) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, company_id, filing_type, period, filed_at, created_at "
            "FROM vertex_sixir_filing "
            "WHERE company_id = ? ORDER BY filed_at DESC LIMIT ? OFFSET ?",
            (company_id, limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM vertex_sixir_filing WHERE company_id = ?",
            (company_id,),
        ).fetchone()[0]
    return {
        "filings": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _get_filing_sync(filing_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, company_id, filing_type, period, filed_at, summary, created_at "
            "FROM vertex_sixir_filing WHERE id = ?",
            (filing_id,),
        ).fetchone()
    if not row:
        return {"error": "not found"}
    return dict(row)


def _list_earnings_sync(
    company_id: str, limit: int, offset: int, actor: str
) -> dict[str, Any]:
    with _open(actor) as conn:
        rows = conn.execute(
            "SELECT id, company_id, period, eps_actual, eps_estimate, "
            "revenue_actual, revenue_estimate, created_at "
            "FROM vertex_sixir_earnings "
            "WHERE company_id = ? ORDER BY period DESC LIMIT ? OFFSET ?",
            (company_id, limit, offset),
        ).fetchall()
        total = conn.execute(
            "SELECT COUNT(*) FROM vertex_sixir_earnings WHERE company_id = ?",
            (company_id,),
        ).fetchone()[0]
    return {
        "earnings": [dict(r) for r in rows],
        "total": total,
        "offset": offset,
        "limit": limit,
    }


def _get_earnings_sync(earnings_id: str, actor: str) -> dict[str, Any]:
    with _open(actor) as conn:
        row = conn.execute(
            "SELECT id, company_id, period, eps_actual, eps_estimate, "
            "revenue_actual, revenue_estimate, created_at "
            "FROM vertex_sixir_earnings WHERE id = ?",
            (earnings_id,),
        ).fetchone()
    if not row:
        return {"error": "not found"}
    return dict(row)


# ---------------------------------------------------------------------------
# Async task handlers (public API, thin wrappers around _*_sync)
# ---------------------------------------------------------------------------

async def task_list_companies(**kwargs: Any) -> dict[str, Any]:
    limit = int(kwargs.get("limit", 50))
    offset = int(kwargs.get("offset", 0))
    actor = kwargs.get("actor", _ACTOR)
    return await asyncio.to_thread(_list_companies_sync, limit, offset, actor)


async def task_get_company(**kwargs: Any) -> dict[str, Any]:
    company_id = kwargs.get("companyId", "")
    actor = kwargs.get("actor", _ACTOR)
    return await asyncio.to_thread(_get_company_sync, company_id, actor)


async def task_search_companies(**kwargs: Any) -> dict[str, Any]:
    query = kwargs.get("query", "")
    limit = int(kwargs.get("limit", 50))
    offset = int(kwargs.get("offset", 0))
    actor = kwargs.get("actor", _ACTOR)
    return await asyncio.to_thread(
        _search_companies_sync, query, limit, offset, actor
    )


async def task_list_filings(**kwargs: Any) -> dict[str, Any]:
    company_id = kwargs.get("companyId", "")
    limit = int(kwargs.get("limit", 50))
    offset = int(kwargs.get("offset", 0))
    actor = kwargs.get("actor", _ACTOR)
    return await asyncio.to_thread(
        _list_filings_sync, company_id, limit, offset, actor
    )


async def task_get_filing(**kwargs: Any) -> dict[str, Any]:
    filing_id = kwargs.get("filingId", "")
    actor = kwargs.get("actor", _ACTOR)
    return await asyncio.to_thread(_get_filing_sync, filing_id, actor)


async def task_list_earnings(**kwargs: Any) -> dict[str, Any]:
    company_id = kwargs.get("companyId", "")
    limit = int(kwargs.get("limit", 50))
    offset = int(kwargs.get("offset", 0))
    actor = kwargs.get("actor", _ACTOR)
    return await asyncio.to_thread(
        _list_earnings_sync, company_id, limit, offset, actor
    )


async def task_get_earnings(**kwargs: Any) -> dict[str, Any]:
    earnings_id = kwargs.get("earningsId", "")
    actor = kwargs.get("actor", _ACTOR)
    return await asyncio.to_thread(_get_earnings_sync, earnings_id, actor)
