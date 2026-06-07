"""
Shared AsyncConnectionPool factory for RisingWave (ADR-2605080600).

RisingWave 制約:
  - autocommit=True (multi-statement TX 非対応)
  - prepare_threshold=0 (prepared statement で LIMIT $N が rejected される)
  - ON CONFLICT なし → PK implicit overwrite

使用方法:
  from kotodama.rw_async_pool import ensure_rw_async_pool

  p = await ensure_rw_async_pool()
  async with p.connection() as conn:
      async with conn.cursor() as cur:
          await cur.execute(...)
"""

from __future__ import annotations

import os
from typing import Any

try:
    from psycopg_pool import AsyncConnectionPool
    _PSYCOPG_AVAILABLE = True
except ImportError:  # pragma: no cover
    _PSYCOPG_AVAILABLE = False

_POOL: Any = None


def _build_pool() -> Any:
    global _POOL
    if _POOL is not None:
        return _POOL
    if not _PSYCOPG_AVAILABLE:
        raise RuntimeError("psycopg[binary] and psycopg-pool required")
    dsn = os.environ.get("RW_URL") or os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError("RW_URL (or DATABASE_URL) not set")
    _POOL = AsyncConnectionPool(
        conninfo=dsn,
        min_size=1,
        max_size=4,
        timeout=10.0,
        max_lifetime=300.0,
        max_idle=60.0,
        kwargs={"autocommit": True, "prepare_threshold": 0},
        open=False,
    )
    return _POOL


async def ensure_rw_async_pool() -> Any:
    """Return an open AsyncConnectionPool, opening it lazily on first call."""
    p = _build_pool()
    if p.closed:
        await p.open()
    return p
