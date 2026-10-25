"""Async PG pool for the kyber data layer.

Single asyncpg pool per pod process, bounded at 10 connections. Connects
directly to RisingWave PG :4566 using RW_URL (k8s Secret
`kyber-rw-root-creds`). The pool is sized for steady-state cron + on-demand.

graph-schema AGENTS.md §"Hyperdrive + pg.Pool Configuration" enforces
serial writes inside one request; callers MUST NOT `asyncio.gather` two
writes against the same pool.
"""

from __future__ import annotations

import logging
import os
from typing import Any

import asyncpg

_log = logging.getLogger(__name__)

_POOL: asyncpg.Pool | None = None


class _RwConnection(asyncpg.Connection):
    """RisingWave PG :4566 wire-compatible Connection.

    asyncpg's default reset emits `UNLISTEN *;` on pool release.
    RisingWave does not implement LISTEN/UNLISTEN — override to no-op.
    """

    async def reset(self, *, timeout: float | None = None) -> None:  # type: ignore[override]
        return None


def _resolve_dsn() -> str:
    dsn = os.environ.get("RW_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "RW_URL not set. Mount k8s Secret kyber-rw-root-creds and inject as RW_URL env."
        )
    return dsn


async def get_pool() -> asyncpg.Pool:
    global _POOL
    if _POOL is not None and not _POOL._closed:  # type: ignore[attr-defined]
        return _POOL
    dsn = _resolve_dsn()
    _POOL = await asyncpg.create_pool(
        dsn=dsn,
        min_size=1,
        max_size=10,
        command_timeout=30.0,
        connection_class=_RwConnection,
        server_settings={"application_name": "lg-kyber"},
    )
    _log.info("[kyber.db] pool ready dsn=%s", _redact_dsn(dsn))
    return _POOL


async def close_pool() -> None:
    global _POOL
    if _POOL is not None:
        await _POOL.close()
        _POOL = None


def _redact_dsn(dsn: str) -> str:
    try:
        scheme, rest = dsn.split("://", 1)
        cred, host = rest.split("@", 1)
        if ":" in cred:
            user, _ = cred.split(":", 1)
            return f"{scheme}://{user}:***@{host}"
        return dsn
    except ValueError:
        return "***"


async def fetch(query: str, *args: Any) -> list[dict[str, Any]]:
    pool = await get_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(query, *args)
        return [dict(r) for r in rows]


async def fetchrow(query: str, *args: Any) -> dict[str, Any] | None:
    pool = await get_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(query, *args)
        return dict(row) if row else None


async def fetchval(query: str, *args: Any) -> Any:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.fetchval(query, *args)


async def execute(query: str, *args: Any) -> str:
    pool = await get_pool()
    async with pool.acquire() as conn:
        return await conn.execute(query, *args)
