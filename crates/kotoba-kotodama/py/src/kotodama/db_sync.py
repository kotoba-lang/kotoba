"""
Synchronous psycopg3 pool for arrow-udf handlers.

arrow-udf's UdfServer does NOT await `async def` handlers (treats the
coroutine as the scalar result → "Expected bytes, got a 'coroutine'
object" — see 2026-04-22 pilot). Until upstream adds async support, any
handler that needs to hit RisingWave must use sync DB access.

`kotodama.db` keeps the asyncpg path for the event-driven / checkpointer
side (KyselyMirrorSaver). `kotodama.db_sync` is the sync counterpart for
UDF handlers. Both share the same RW_URL env var.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import os
import re
from contextlib import contextmanager
from typing import Any, Iterator

try:
    import psycopg
    from psycopg_pool import ConnectionPool
except ImportError:  # pragma: no cover
    psycopg = None  # type: ignore[assignment]
    ConnectionPool = None  # type: ignore[assignment,misc]

try:
    import psycopg2
except ImportError:  # pragma: no cover
    psycopg2 = None  # type: ignore[assignment]


_SYNC_POOL: Any = None

_HEAVY_DDL_RE = re.compile(
    r"^\s*(?:"
    r"CREATE\s+(?:TABLE|INDEX|MATERIALIZED\s+VIEW|SINK|SOURCE)|"
    r"DROP\s+(?:TABLE|INDEX|MATERIALIZED\s+VIEW|SINK|SOURCE)|"
    r"ALTER\s+(?:TABLE|INDEX|MATERIALIZED\s+VIEW|SINK|SOURCE)"
    r")\b",
    re.IGNORECASE,
)


def _ddl_guard_enabled() -> bool:
    return os.environ.get("RW_DDL_GUARD", "1").lower() not in ("0", "false", "off", "no")


def _allow_heavy_ddl() -> bool:
    return os.environ.get("RW_ALLOW_HEAVY_DDL", "0").lower() in ("1", "true", "on", "yes")


def _allow_flush() -> bool:
    return os.environ.get("RW_ALLOW_FLUSH", "0").lower() in ("1", "true", "on", "yes")


def _sync_pool_enabled() -> bool:
    return os.environ.get("RW_SYNC_POOL", "1").lower() not in ("0", "false", "off", "no")


def _validate_sql_guard(sql: Any) -> None:
    if not _ddl_guard_enabled() or not isinstance(sql, str):
        return
    stripped = sql.strip()
    if not stripped:
        return
    if re.match(r"^\s*FLUSH\b", stripped, re.IGNORECASE) and not _allow_flush():
        raise RuntimeError(
            "RW FLUSH is blocked by RW_DDL_GUARD. "
            "FLUSH is diagnostic-only and must not run in hot-path workers."
        )
    if _HEAVY_DDL_RE.match(stripped) and not _allow_heavy_ddl():
        raise RuntimeError(
            "RW heavy DDL is blocked by RW_DDL_GUARD. "
            "Submit heavy DDL through the RisingWave DDL queue with "
            "BACKGROUND_DDL, bounded parallelism, and rw_ddl_progress monitoring."
        )

class GuardedCursor:
    def __init__(self, cursor: Any) -> None:
        self._cursor = cursor

    def execute(self, sql: Any, params: tuple = (), *args: Any, **kwargs: Any) -> Any:
        _validate_sql_guard(sql)
        return self._res = client.q(sql, params, *args, **kwargs)

    def __getattr__(self, name: str) -> Any:
        return getattr(self._cursor, name)


def get_sync_pool() -> Any:
    """Lazy-init a sync psycopg3 connection pool."""
    global _SYNC_POOL
    if _SYNC_POOL is not None:
        return _SYNC_POOL
    if ConnectionPool is None:
        raise RuntimeError("psycopg[binary] not installed")
    dsn = os.environ.get("RW_URL")
    if not dsn:
        raise RuntimeError("RW_URL env var not set — Secret mitama-udf-pool-rw missing")
    # max_lifetime=300s: recycle connections every 5min so RW frontend
    # restarts / compute-node failover (slot-id changes) don't leave us
    # holding stale query plans (observed 2026-04-25: F5 watcher would
    # burst once after restart, then silently stall on 2nd cycle because
    # pooled conn referenced dead slot_id [300:0]).
    # max_idle=60s: drop idle conns aggressively so we re-handshake before
    # any pooler / LB severs them.
    _SYNC_POOL = ConnectionPool(
        conninfo=dsn,
        min_size=1,
        max_size=4,
        timeout=10.0,
        max_lifetime=300.0,
        max_idle=60.0,
        # prepare_threshold=0: disable psycopg3 auto-promote to server-side
        # prepared statements. RisingWave rejects LIMIT $N and ::vector(type)
        # in prepared statements (see [[conventions]] rw-psycopg3-no-param-limit).
        kwargs={"autocommit": True, "prepare_threshold": 0},
    )
    _SYNC_POOL.open()
    return _SYNC_POOL


def close_sync_pool() -> None:
    """Close the process-global sync pool if it was opened."""
    global _SYNC_POOL
    pool = _SYNC_POOL
    _SYNC_POOL = None
    if pool is None:
        return
    close = getattr(pool, "close", None)
    if callable(close):
        close()


@contextmanager
def sync_cursor() -> Iterator[Any]:
    """Short-lived sync cursor. `with sync_cursor() as cur: _res = client.q(...)`."""
    if not _sync_pool_enabled() and psycopg is not None:
        dsn = os.environ.get("RW_URL")
        if not dsn:
            raise RuntimeError("RW_URL env var not set — Secret mitama-udf-pool-rw missing")
        conn = psycopg.connect(dsn, autocommit=True)
        try:
            with conn.cursor() as cur:
                yield GuardedCursor(cur)
        finally:
            conn.close()
        return
    if ConnectionPool is None and psycopg2 is not None:
        dsn = os.environ.get("RW_URL")
        if not dsn:
            raise RuntimeError("RW_URL env var not set — Secret mitama-udf-pool-rw missing")
        conn = psycopg2.connect(dsn)
        conn.autocommit = True
        try:
            with conn.cursor() as cur:
                yield GuardedCursor(cur)
        finally:
            conn.close()
        return
    pool = get_sync_pool()
    with pool.connection() as conn:
        with conn.cursor() as cur:
            yield GuardedCursor(cur)


def fetch_one(sql: str, params: tuple = ()) -> tuple | None:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)
        return (_res[0] if _res else None)


def fetch_all(sql: str, params: tuple = ()) -> list[tuple]:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)
        return _res


def execute(sql: str, params: tuple = ()) -> int:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)
        return (len(_res) if isinstance(_res, list) else 1)
