"""Alembic env.py — RisingWave-compatible migration runner.

Key constraints (ADR-2605080400):
- NO transaction wrapping — RisingWave does not support DDL inside transactions.
  Each migration runs as autocommit DDL statements.
- Table name guard — any migration that references vertex_* / edge_* / mv_*
  table names raises an error at planning time (those tables belong to the
  Kysely TypeScript migration scope in 30-graph/graph-schema/).
- Schema: migrations target the ``public`` schema (not ``graphar``).

Running migrations:
    # Apply pending
    cd 20-actors/kotoba-kotodama/py
    alembic upgrade head

    # Generate a new migration
    alembic revision --autogenerate -m "add langgraph_state"

    # Dry-run check
    alembic upgrade head --sql
"""

from __future__ import annotations

import re
from logging.config import fileConfig
from pathlib import Path

import sqlalchemy as sa
from alembic import context
from sqlalchemy import event as sa_event
from sqlalchemy import text

# ---------------------------------------------------------------------------
# Guard: refuse to migrate graph-schema tables
# ---------------------------------------------------------------------------

_FORBIDDEN_TABLE_PREFIXES = (
    "edge_",
    "mv_",
    "graphar.",
)

# vertex_lora_* is allowed in Alembic (ADR-2605080400 Addendum 2026-05-08).
# All other vertex_* remain blocked (Kysely TypeScript ownership).
_FORBIDDEN_VERTEX_PREFIX = "vertex_"
_ALLOWED_VERTEX_EXCEPTIONS = ("vertex_lora_",)

_TABLE_REF_RE = re.compile(
    r"(?:CREATE|DROP|ALTER)\s+(?:TABLE|MATERIALIZED\s+VIEW|INDEX)\s+(?:IF\s+(?:NOT\s+)?EXISTS\s+)?([a-zA-Z_][a-zA-Z0-9_.]*)",
    re.IGNORECASE,
)


def _check_forbidden_tables(script_path: str) -> None:
    """Raise if the migration script references graph-schema tables.

    vertex_lora_* is allowed (ADR-2605080400 Addendum 2026-05-08).
    All other vertex_* / edge_* / mv_* / graphar.* remain forbidden.
    """
    source = Path(script_path).read_text(encoding="utf-8")
    for match in _TABLE_REF_RE.finditer(source):
        table_name = match.group(1).lower()
        # Check non-vertex forbidden prefixes first
        for prefix in _FORBIDDEN_TABLE_PREFIXES:
            if table_name.startswith(prefix):
                raise RuntimeError(
                    f"Alembic migration '{Path(script_path).name}' references "
                    f"table '{table_name}' which starts with '{prefix}'. "
                    f"Graph-schema tables (vertex_* / edge_* / mv_*) are owned "
                    f"by Kysely TypeScript migrations in "
                    f"30-graph/graph-schema/migrations/. "
                    f"Create the migration there instead."
                )
        # vertex_* check with allowed exceptions
        if table_name.startswith(_FORBIDDEN_VERTEX_PREFIX):
            if not any(table_name.startswith(exc) for exc in _ALLOWED_VERTEX_EXCEPTIONS):
                raise RuntimeError(
                    f"Alembic migration '{Path(script_path).name}' references "
                    f"table '{table_name}' (vertex_* prefix). "
                    f"Only vertex_lora_* tables are allowed in Alembic "
                    f"(ADR-2605080400 Addendum 2026-05-08). "
                    f"All other vertex_* belong in "
                    f"30-graph/graph-schema/migrations/."
                )


# ---------------------------------------------------------------------------
# Standard Alembic boilerplate
# ---------------------------------------------------------------------------

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = None


def _get_engine() -> object:
    """Return the SQLAlchemy engine from db_alchemy (reuses RW_URL env var)."""
    from kotodama.db_alchemy import get_sa_engine

    return get_sa_engine()


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (emit SQL to stdout / file).

    RisingWave does NOT support transactions for DDL, so we use
    ``literal_binds=True`` and emit bare DDL statements.
    """
    engine = _get_engine()
    context.configure(
        url=engine.url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        transaction_per_migration=False,  # RW: no DDL transactions
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations against the live RisingWave instance.

    Each migration script is checked for forbidden table names before execution.
    DDL is applied without wrapping transactions (RW constraint).
    """
    engine = _get_engine()

    def _on_version_apply(ctx: object, step: object, heads: object, run_args: object) -> None:
        """Guard: raise before any migration that references forbidden table names."""
        fn = getattr(step, "migration_fn", None)
        if fn is not None:
            src = getattr(getattr(fn, "__code__", None), "co_filename", None)
            if src:
                _check_forbidden_tables(src)

    def do_run_migrations(connection: object) -> None:
        # RisingWave rejects VARCHAR(32) — pre-create with plain VARCHAR + PK
        # so INSERT is immediately visible (non-PK tables are append-only with
        # checkpoint-based visibility in RW, which breaks Alembic's read-after-write).
        connection.execute(
            text(
                "CREATE TABLE IF NOT EXISTS alembic_version "
                "(version_num VARCHAR PRIMARY KEY)"
            )
        )

        # RisingWave forbids UPDATE on PK columns, so intercept Alembic's
        # "UPDATE alembic_version SET version_num=new WHERE version_num=old"
        # and replace it with DELETE + INSERT on the raw DBAPI cursor.
        @sa_event.listens_for(connection, "before_cursor_execute", retval=True)
        def _rw_version_pk_update(
            conn: object,
            cursor: object,
            statement: str,
            parameters: object,
            ctx: object,
            executemany: bool,
        ) -> tuple:
            if "UPDATE alembic_version SET version_num" in statement:
                new_ver = (
                    parameters.get("version_num_1")
                    if isinstance(parameters, dict)
                    else (parameters[0] if parameters else None)
                )
                if new_ver:
                    cursor.execute("DELETE FROM alembic_version")
                    cursor.execute("INSERT INTO alembic_version VALUES (%s)", (new_ver,))
                    return "SELECT 1", {}
            return statement, parameters

        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            transaction_per_migration=False,  # RW: no DDL transactions
            compare_type=True,
            on_version_apply=_on_version_apply,
        )
        with context.begin_transaction():
            context.run_migrations()

    with engine.connect() as connection:
        do_run_migrations(connection)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
