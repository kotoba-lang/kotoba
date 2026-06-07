"""Live RisingWave schema reflection for Python workers.

Kysely migrations remain the schema source of truth. This module gives
LangServer/UDF code a small runtime view of the live RisingWave catalog via
``information_schema`` so Python handlers can project dynamic rows onto known
columns without owning migrations or generated models.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import time
from dataclasses import dataclass
from typing import Any, Mapping

from kotodama import db_sync


DEFAULT_SCHEMA = "public"
DEFAULT_TTL_SECONDS = 300.0


@dataclass(frozen=True)
class ColumnInfo:
    table_schema: str
    table_name: str
    column_name: str
    data_type: str
    ordinal_position: int
    is_nullable: bool
    column_default: str | None = None


@dataclass(frozen=True)
class TableInfo:
    table_schema: str
    table_name: str
    columns: tuple[ColumnInfo, ...]

    @property
    def column_names(self) -> tuple[str, ...]:
        return tuple(col.column_name for col in self.columns)

    @property
    def column_set(self) -> frozenset[str]:
        return frozenset(self.column_names)


class RisingWaveSchema:
    def __init__(self, tables: Mapping[tuple[str, str], TableInfo]) -> None:
        self._tables = dict(tables)

    @classmethod
    def from_information_schema_rows(cls, rows: list[Mapping[str, Any]]) -> "RisingWaveSchema":
        grouped: dict[tuple[str, str], list[ColumnInfo]] = {}
        for row in rows:
            table_schema = str(row["table_schema"])
            table_name = str(row["table_name"])
            column = ColumnInfo(
                table_schema=table_schema,
                table_name=table_name,
                column_name=str(row["column_name"]),
                data_type=str(row.get("data_type") or ""),
                ordinal_position=int(row["ordinal_position"]),
                is_nullable=str(row.get("is_nullable", "")).upper() == "YES",
                column_default=row.get("column_default"),
            )
            grouped.setdefault((table_schema, table_name), []).append(column)

        tables = {
            key: TableInfo(
                table_schema=key[0],
                table_name=key[1],
                columns=tuple(sorted(cols, key=lambda col: col.ordinal_position)),
            )
            for key, cols in grouped.items()
        }
        return cls(tables)

    def tables(self, table_schema: str | None = None) -> tuple[TableInfo, ...]:
        values = self._tables.values()
        if table_schema is not None:
            values = (table for table in values if table.table_schema == table_schema)
        return tuple(sorted(values, key=lambda table: (table.table_schema, table.table_name)))

    def has_table(self, table_name: str, table_schema: str = DEFAULT_SCHEMA) -> bool:
        return (table_schema, table_name) in self._tables

    def table(self, table_name: str, table_schema: str = DEFAULT_SCHEMA) -> TableInfo:
        try:
            return self._tables[(table_schema, table_name)]
        except KeyError as exc:
            raise KeyError(f"RisingWave table not found: {table_schema}.{table_name}") from exc

    def column_names(self, table_name: str, table_schema: str = DEFAULT_SCHEMA) -> tuple[str, ...]:
        return self.table(table_name, table_schema).column_names

    def project_known_columns(
        self,
        table_name: str,
        row: Mapping[str, Any],
        table_schema: str = DEFAULT_SCHEMA,
    ) -> dict[str, Any]:
        known = self.table(table_name, table_schema).column_set
        return {key: value for key, value in row.items() if key in known}

    def validate_insert(
        self,
        table_name: str,
        row: Mapping[str, Any],
        table_schema: str = DEFAULT_SCHEMA,
        *,
        require_non_nullable: bool = False,
    ) -> None:
        table = self.table(table_name, table_schema)
        unknown = sorted(set(row) - table.column_set)
        if unknown:
            raise ValueError(
                f"Unknown columns for {table_schema}.{table_name}: {', '.join(unknown)}"
            )
        if not require_non_nullable:
            return
        missing = [
            col.column_name
            for col in table.columns
            if not col.is_nullable and col.column_default is None and col.column_name not in row
        ]
        if missing:
            raise ValueError(
                f"Missing required columns for {table_schema}.{table_name}: {', '.join(missing)}"
            )


def _fetch_information_schema_rows(table_schema: str | None = DEFAULT_SCHEMA) -> list[dict[str, Any]]:
    sql = """
        SELECT
          table_schema,
          table_name,
          column_name,
          data_type,
          ordinal_position,
          is_nullable,
          column_default
        FROM information_schema.columns
        WHERE (%s IS NULL OR table_schema = %s)
        ORDER BY table_schema, table_name, ordinal_position
    """
    rows: list[dict[str, Any]] = []
    with db_sync.sync_cursor() as cur:
        _res = client.q(sql, (table_schema, table_schema))
        description = getattr(cur, "description", None)
        raw_rows = _res
    if description:
        names = [str(getattr(col, "name", col[0])) for col in description]
        return [dict(zip(names, row)) for row in raw_rows]
    for row in raw_rows:
        if isinstance(row, Mapping):
            rows.append(dict(row))
        else:
            raise RuntimeError("information_schema cursor returned tuples without description")
    return rows


_SCHEMA_CACHE: tuple[float, str | None, RisingWaveSchema] | None = None


def load_schema(
    table_schema: str | None = DEFAULT_SCHEMA,
    *,
    ttl_seconds: float = DEFAULT_TTL_SECONDS,
    force: bool = False,
) -> RisingWaveSchema:
    global _SCHEMA_CACHE
    now = time.monotonic()
    if not force and _SCHEMA_CACHE is not None:
        loaded_at, cached_schema_name, schema = _SCHEMA_CACHE
        if cached_schema_name == table_schema and now - loaded_at < ttl_seconds:
            return schema

    schema = RisingWaveSchema.from_information_schema_rows(
        _fetch_information_schema_rows(table_schema)
    )
    _SCHEMA_CACHE = (now, table_schema, schema)
    return schema


def clear_schema_cache() -> None:
    global _SCHEMA_CACHE
    _SCHEMA_CACHE = None
