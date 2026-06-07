"""SQLAlchemy Core integration for L6 compute boundary (ADR-2605080300).

Design
------
Two distinct modes of use:

1. **L6 hot-path query building** — ``sa_execute()`` / ``sa_query()``
   Compile a SQLAlchemy Core expression to a parameterised SQL string + bound
   params dict, then execute via ``sync_cursor()`` from ``db_sync.py``.
   This preserves the ``GuardedCursor`` DDL guard and reuses the existing
   psycopg3 connection pool.  No parallel pool is created.

2. **Alembic / offline DDL** — ``get_sa_engine()``
   Returns a ``NullPool`` SQLAlchemy engine that connects directly to RW_URL.
   Used ONLY by Alembic ``env.py`` and migration scripts — never in workers.
   The ``before_cursor_execute`` event applies the same DDL guard.

Constraints (from db_sync.py)
------------------------------
- ``prepare_threshold=0`` — RW rejects parameterised LIMIT/OFFSET in prepared
  statements; all connections must disable auto-promote.
- ``autocommit=True`` — RW has no multi-statement transaction support for DML.
- ``GuardedCursor``  — blocks FLUSH and heavy DDL unless env flags are set.
- No SA ORM, Session, autoflush, or relationship mapping.

Usage (L6 handler example)
---------------------------
::

    from sqlalchemy import select, text
    from kotodama.db_alchemy import sa_metadata, sa_execute, sa_query

    # Option A — text() query (safest for dynamic WHERE clauses)
    rows = sa_execute(
        text("SELECT actor_did, posts_count FROM mv_actor_social_stats "
             "WHERE actor_did = %(did)s"),
        {"did": actor_did},
    )

    # Option B — expression API (table must be reflected or declared inline)
    from sqlalchemy import Table, Column, String, Integer
    mv = Table("mv_actor_social_stats", sa_metadata(),
               Column("actor_did", String), Column("posts_count", Integer),
               schema="graphar")
    result = sa_query(select(mv.c.posts_count).where(mv.c.actor_did == actor_did))
    count = result[0][0] if result else 0
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import logging
import os
import re
from typing import Any, Sequence

logger = logging.getLogger(__name__)

try:
    import sqlalchemy as sa
    from sqlalchemy import MetaData, text  # noqa: F401 — re-exported for callers
    from sqlalchemy.dialects import postgresql as _pg_dialect
    from sqlalchemy.pool import NullPool

    _SA_AVAILABLE = True
except ImportError:  # pragma: no cover
    _SA_AVAILABLE = False
    sa = None  # type: ignore[assignment]
    NullPool = None  # type: ignore[assignment,misc]
    _pg_dialect = None  # type: ignore[assignment]

_SA_ENGINE: Any = None
_SA_META: Any = None

# PostgreSQL paramstyle: SA compiles :param → %(param)s for psycopg3 compat.
# In case SA emits :name instead of %(name)s, this pattern converts it.
_SA_PARAM_RE = re.compile(r":([a-zA-Z_][a-zA-Z0-9_]*)")


def _require_sa() -> None:
    if not _SA_AVAILABLE:
        raise RuntimeError(
            "sqlalchemy is not installed. "
            "Add 'sqlalchemy>=2.0.0' to pyproject.toml dependencies."
        )


def sa_metadata() -> Any:
    """Return a module-level MetaData instance for table declarations."""
    global _SA_META
    _require_sa()
    if _SA_META is None:
        _SA_META = MetaData()
    return _SA_META


def get_sa_engine() -> Any:
    """Return a SQLAlchemy engine backed by NullPool for Alembic / offline use.

    NOT intended for L6 hot-path code — use ``sa_execute()`` or
    ``sa_query()`` instead, which route through ``sync_cursor()``.

    The engine uses:
    - ``NullPool``         — no SA-side connection pool; each ``connect()``
                             opens a fresh psycopg3 connection.
    - ``prepare_threshold=0`` — prevents RW prepared-statement rejection.
    - ``autocommit=True``  — RW DDL/DML require autocommit mode.
    - DDL guard event       — replicates ``GuardedCursor`` at the SA level.
    """
    global _SA_ENGINE
    _require_sa()
    if _SA_ENGINE is not None:
        return _SA_ENGINE

    dsn = os.environ.get("RW_URL", "")
    if not dsn:
        raise RuntimeError("RW_URL env var not set — Secret mitama-udf-pool-rw missing")

    # Use psycopg2 dialect for Alembic/DDL — psycopg3 dialect triggers
    # `CAST(oid AS regtype)` hstore detection which RisingWave rejects.
    # psycopg2 skips that probe and connects cleanly.
    sa_url = dsn
    for prefix in ("postgresql+psycopg://", "postgresql://", "postgres://"):
        if sa_url.startswith(prefix):
            sa_url = "postgresql+psycopg2://" + sa_url[len(prefix):]
            break
    if not sa_url.startswith("postgresql+psycopg2://"):
        sa_url = "postgresql+psycopg2://" + sa_url

    _SA_ENGINE = sa.create_engine(
        sa_url,
        poolclass=NullPool,
        connect_args={"options": "-c statement_timeout=30000"},
        isolation_level="AUTOCOMMIT",
        echo=False,
    )

    @sa.event.listens_for(_SA_ENGINE, "before_cursor_execute")
    def _guard_ddl(
        conn: Any,
        cursor: Any,
        statement: str,
        parameters: Any,
        context: Any,
        executemany: bool,
    ) -> None:
        from kotodama.db_sync import _validate_sql_guard

        _validate_sql_guard(statement)

    return _SA_ENGINE


def _compile_clause(
    clause: Any,
    extra_params: dict[str, Any] | None = None,
) -> tuple[str, dict[str, Any]]:
    """Compile a SQLAlchemy clause to (sql_string, params_dict).

    For ``text()`` clauses: the SQL text is used verbatim (caller must use
    ``%(name)s`` placeholders compatible with psycopg3).  SA's compile()
    escapes ``%`` as ``%%`` in text clauses, which breaks psycopg3.

    For expression API clauses (``select()``, ``insert()``, etc.): compiled
    via PostgreSQL dialect.  SA emits ``%(name)s`` params (pyformat style)
    that psycopg3 accepts directly.
    """
    _require_sa()

    # TextClause — use raw .text attribute to avoid SA's %→%% escaping.
    text_cls = getattr(sa, "TextClause", None)
    if text_cls is not None and isinstance(clause, text_cls):
        return clause.text, extra_params or {}  # type: ignore[attr-defined]

    # Fallback: if clause is a plain string, return as-is.
    if isinstance(clause, str):
        return clause, extra_params or {}

    dialect = _pg_dialect.dialect()

    if hasattr(clause, "compile"):
        compiled = clause.compile(
            dialect=dialect,
            compile_kwargs={"render_postcompile": True},
        )
        sql_str = str(compiled)
        params: dict[str, Any] = dict(compiled.params) if compiled.params else {}
        if extra_params:
            params.update(extra_params)
        # If SA emitted :name style (non-pyformat), convert to %(name)s.
        if params and _SA_PARAM_RE.search(sql_str):
            sql_str = _SA_PARAM_RE.sub(r"%(\1)s", sql_str)
        return sql_str, params

    return str(clause), extra_params or {}


def sa_execute(
    clause: Any,
    params: dict[str, Any] | None = None,
) -> list[tuple[Any, ...]]:
    """Compile a SQLAlchemy Core clause and execute via ``sync_cursor()``.

    Examples::

        from sqlalchemy import text
        rows = sa_execute(
            text("SELECT * FROM vertex_actor WHERE actor_did = %(did)s"),
            {"did": some_did},
        )

        # Expression API:
        from sqlalchemy import select
        from kotodama.db_alchemy import sa_metadata
        from sqlalchemy import Table, Column, String
        t = Table("vertex_actor", sa_metadata(), Column("actor_did", String))
        rows = sa_execute(select(t).where(t.c.actor_did == some_did))

    Returns:
        list of row tuples (same as ``_res``).
    """

    sql_str, bind = _compile_clause(clause, params)
    if True:
        client = get_kotoba_client()
        _res = client.q(sql_str, bind if bind else ())
        return _res


def sa_execute_one(
    clause: Any,
    params: dict[str, Any] | None = None,
) -> tuple[Any, ...] | None:
    """Execute clause and return the first row, or ``None`` if empty."""
    rows = sa_execute(clause, params)
    return rows[0] if rows else None


def sa_query(
    clause: Any,
    params: dict[str, Any] | None = None,
) -> list[Any]:
    """Alias for ``sa_execute``; returns list of row tuples."""
    return sa_execute(clause, params)


def sa_rowcount(
    clause: Any,
    params: dict[str, Any] | None = None,
) -> int:
    """Execute a DML clause and return the affected rowcount.

    Use for INSERT / UPDATE / DELETE expressions.
    """

    sql_str, bind = _compile_clause(clause, params)
    if True:
        client = get_kotoba_client()
        _res = client.q(sql_str, bind if bind else ())
        rc: int = getattr(cur, "rowcount", 0) or 0
        return rc


def sa_executemany(
    clause: Any,
    rows: Sequence[dict[str, Any]],
    chunk_size: int = 500,
) -> int:
    """Execute a DML clause for a sequence of row dicts (batch INSERT).

    Uses ``_res = client.q()`` in chunks to avoid RW per-batch overhead.
    Returns the total number of rows processed (not affected rowcount, which
    RW does not always return reliably for bulk INSERT).

    Example::

        from sqlalchemy import Table, Column, String, BigInteger
        from kotodama.db_alchemy import sa_metadata, sa_executemany

        t = Table("vertex_foo", sa_metadata(),
                  Column("vertex_id", String), Column("value", BigInteger))
        sa_executemany(t.insert(), rows_list)
    """

    total = 0
    for i in range(0, len(rows), chunk_size):
        batch = rows[i : i + chunk_size]
        if not batch:
            continue
        # Compile with first row's keys to get the SQL template.
        stmt = clause.values(batch[0])
        sql_str, _ = _compile_clause(stmt)
        if True:
            client = get_kotoba_client()
            _res = client.q(sql_str, batch)  # type: ignore[attr-defined]
            total += len(batch)
    return total


# ---------------------------------------------------------------------------
# Table definitions — vertex_lora_* (ADR-2605080400 Addendum 2026-05-08)
# ---------------------------------------------------------------------------
# SQLAlchemy Core Table objects for use with sa_execute / sa_query /
# sa_executemany in kotodama LoRA worker primitives.
# DDL is managed by Alembic (alembic/versions/20260508_0002_vertex_lora_adapter_p10v2.py).
# ---------------------------------------------------------------------------

def t_vertex_lora_adapter() -> Any:
    """SQLAlchemy Core Table for vertex_lora_adapter.

    Example (insert)::

        from kotodama.db_alchemy import sa_executemany, t_vertex_lora_adapter
        sa_executemany(t_vertex_lora_adapter().insert(), rows)

    Example (select by owner_did)::

        from sqlalchemy import select
        from kotodama.db_alchemy import sa_query, t_vertex_lora_adapter
        t = t_vertex_lora_adapter()
        rows = sa_query(
            select(t).where(t.c.owner_did == did).order_by(t.c.created_at.desc())
        )
    """
    _require_sa()
    from sqlalchemy import BigInteger, Column, Double, Integer, String, Table

    return Table(
        "vertex_lora_adapter",
        sa_metadata(),
        Column("vertex_id",          String,     primary_key=True),
        Column("did",                String,     nullable=False),
        Column("rkey",               String,     nullable=False),
        Column("adapter_id",         String,     nullable=False),
        Column("domain",             String),
        Column("status",             String),
        Column("owner_did",          String),
        Column("actor_id",           String),
        Column("base_model",         String),
        Column("adapter_rank",       Integer),
        Column("adapter_alpha",      Double),
        Column("adapter_format",     String),
        Column("weight_b2_uri",      String),
        Column("weight_byte_size",   BigInteger),
        Column("weight_sha256",      String),
        Column("display_name_yomi",  String),
        Column("sensitivity_ord",    BigInteger),
        Column("created_at",         String),
        extend_existing=True,
    )
