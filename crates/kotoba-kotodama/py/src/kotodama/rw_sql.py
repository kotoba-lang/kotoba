"""Optional SQLAlchemy Core helpers for RisingWave.

Use these when a Python worker needs SQLAlchemy's expression builder or table
reflection. Hot-path inserts/selects can keep using ``kotodama.db_sync``.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

from kotodama import rw_schema


def sqlalchemy_url_from_rw_url(rw_url: str) -> str:
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
    if rw_url.startswith("risingwave+"):
        return rw_url
    if rw_url.startswith("postgresql://"):
        return "risingwave+psycopg2://" + rw_url[len("postgresql://") :]
    if rw_url.startswith("postgres://"):
        return "risingwave+psycopg2://" + rw_url[len("postgres://") :]
    return rw_url


def get_sqlalchemy_url() -> str:
    explicit = os.environ.get("RW_SQLALCHEMY_URL")
    if explicit:
        return explicit
    rw_url = os.environ.get("RW_URL") or os.environ.get("RISINGWAVE_URL")
    if not rw_url:
        raise RuntimeError("RW_URL or RW_SQLALCHEMY_URL env var not set")
    return sqlalchemy_url_from_rw_url(rw_url)


def create_rw_engine(**kwargs: Any) -> Any:
    try:
        from sqlalchemy import create_engine
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("SQLAlchemy is not installed") from exc

    options = {"isolation_level": "AUTOCOMMIT"}
    options.update(kwargs)
    return create_engine(get_sqlalchemy_url(), **options)


def reflect_table(table_name: str, *, schema: str | None = None, engine: Any | None = None) -> Any:
    try:
        from sqlalchemy import MetaData, Table
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("SQLAlchemy is not installed") from exc

    owns_engine = engine is None
    actual_engine = engine or create_rw_engine()
    metadata = MetaData()
    try:
        return Table(table_name, metadata, schema=schema, autoload_with=actual_engine)
    finally:
        if owns_engine:
            dispose = getattr(actual_engine, "dispose", None)
            if callable(dispose):
                dispose()


def table_column_names(table: Any) -> tuple[str, ...]:
    return tuple(str(column.name) for column in table.columns)


def project_row_for_table(table: Any, row: Mapping[str, Any]) -> dict[str, Any]:
    cols = set(table_column_names(table))
    return {key: value for key, value in row.items() if key in cols}


def insert_projected_row(
    table_name: str,
    row: Mapping[str, Any],
    *,
    schema: str | None = None,
    engine: Any | None = None,
) -> int:
    """Insert a row through SQLAlchemy Core after table reflection projection."""
    owns_engine = engine is None
    actual_engine = engine or create_rw_engine()
    try:
        table = reflect_table(table_name, schema=schema, engine=actual_engine)
        projected = project_row_for_table(table, row)
        if not projected:
            return 0
        with actual_engine.begin() as conn:
            result = conn.execute(table.insert().values(**projected))
            return int(result.rowcount or 0)
    finally:
        if owns_engine:
            dispose = getattr(actual_engine, "dispose", None)
            if callable(dispose):
                dispose()


def select_projected(
    table_name: str,
    columns: tuple[str, ...] = (),
    *,
    schema: str | None = None,
    engine: Any | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    """Run a small SQLAlchemy Core SELECT against a reflected table."""
    owns_engine = engine is None
    actual_engine = engine or create_rw_engine()
    try:
        table = reflect_table(table_name, schema=schema, engine=actual_engine)
        known = set(table_column_names(table))
        selected = [table.c[name] for name in columns if name in known] if columns else [table]
        stmt = table.select() if selected == [table] else __import__("sqlalchemy").select(*selected)
        stmt = stmt.limit(max(1, min(int(limit or 100), 1000)))
        with actual_engine.connect() as conn:
            return [dict(row) for row in conn.execute(stmt).mappings().all()]
    finally:
        if owns_engine:
            dispose = getattr(actual_engine, "dispose", None)
            if callable(dispose):
                dispose()


@dataclass(frozen=True)
class MigrationCoverage:
    table_count: int
    column_count: int
    vertex_table_count: int
    edge_table_count: int

    @property
    def graph_table_count(self) -> int:
        return self.vertex_table_count + self.edge_table_count

    @property
    def graph_table_ratio(self) -> float:
        if self.table_count == 0:
            return 0.0
        return self.graph_table_count / self.table_count


def live_migration_coverage(schema_name: str = rw_schema.DEFAULT_SCHEMA) -> MigrationCoverage:
    """Summarize Python visibility over the Kysely-managed live schema.

    This is intentionally not Alembic coverage. Kysely owns migrations; Python
    coverage means the live schema reflected from RisingWave is visible enough
    for SQLAlchemy/Core and LangServer projection helpers.
    """
    schema = rw_schema.load_schema(schema_name)
    tables = schema.tables(schema_name)
    return MigrationCoverage(
        table_count=len(tables),
        column_count=sum(len(table.columns) for table in tables),
        vertex_table_count=sum(1 for table in tables if table.table_name.startswith("vertex_")),
        edge_table_count=sum(1 for table in tables if table.table_name.startswith("edge_")),
    )
