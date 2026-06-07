from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama import rw_sql


def test_sqlalchemy_url_from_postgresql_url() -> None:
    assert (
        rw_sql.sqlalchemy_url_from_rw_url("postgresql://root@example:4566/dev")
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
        == "risingwave+psycopg2://root@example:4566/dev"
    )


def test_sqlalchemy_url_leaves_risingwave_url_unchanged() -> None:
    url = "risingwave+psycopg2://root@example:4566/dev"
    assert rw_sql.sqlalchemy_url_from_rw_url(url) == url


def test_get_sqlalchemy_url_prefers_explicit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_SQLALCHEMY_URL", "risingwave+psycopg2://explicit/dev")
    monkeypatch.setenv("RW_URL", "postgresql://root@example:4566/dev")
    assert rw_sql.get_sqlalchemy_url() == "risingwave+psycopg2://explicit/dev"


def test_get_sqlalchemy_url_uses_rw_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_SQLALCHEMY_URL", raising=False)
    monkeypatch.setenv("RW_URL", "postgres://root@example:4566/dev")
    assert rw_sql.get_sqlalchemy_url() == "risingwave+psycopg2://root@example:4566/dev"


class _Col:
    def __init__(self, name: str) -> None:
        self.name = name


class _Insert:
    def __init__(self) -> None:
        self.values_payload: dict[str, Any] = {}

    def values(self, **kwargs: Any) -> "_Insert":
        self.values_payload = kwargs
        return self


class _Table:
    def __init__(self) -> None:
        self.columns = [_Col("vertex_id"), _Col("repo")]
        self.last_insert = _Insert()

    def insert(self) -> _Insert:
        return self.last_insert


class _Result:
    rowcount = 1


class _Conn:
    def __init__(self) -> None:
        self.executed: Any = None

    def execute(self, stmt: Any) -> _Result:
        self.executed = stmt
        return _Result()

    def __enter__(self) -> "_Conn":
        return self

    def __exit__(self, *args: object) -> None:
        return None


class _Engine:
    def __init__(self) -> None:
        self.conn = _Conn()
        self.disposed = False

    def begin(self) -> _Conn:
        return self.conn

    def dispose(self) -> None:
        self.disposed = True


def test_table_column_names() -> None:
    assert rw_sql.table_column_names(_Table()) == ("vertex_id", "repo")


def test_project_row_for_table_drops_unknown_columns() -> None:
    assert rw_sql.project_row_for_table(
        _Table(),
        {"vertex_id": "v1", "repo": "did:web:x", "extra": "drop"},
    ) == {"vertex_id": "v1", "repo": "did:web:x"}


def test_insert_projected_row_uses_sqlalchemy_core(monkeypatch: pytest.MonkeyPatch) -> None:
    table = _Table()
    engine = _Engine()
    monkeypatch.setattr(rw_sql, "reflect_table", lambda *a, **kw: table)

    inserted = rw_sql.insert_projected_row(
        "vertex_test",
        {"vertex_id": "v1", "repo": "did:web:x", "extra": "drop"},
        engine=engine,
    )

    assert inserted == 1
    assert table.last_insert.values_payload == {"vertex_id": "v1", "repo": "did:web:x"}
    assert engine.conn.executed is table.last_insert
    assert engine.disposed is False


class _SchemaColumn:
    def __init__(self, name: str) -> None:
        self.column_name = name


class _SchemaTable:
    def __init__(self, name: str, column_count: int) -> None:
        self.table_name = name
        self.columns = tuple(_SchemaColumn(f"c{i}") for i in range(column_count))


class _Schema:
    def tables(self, schema_name: str) -> tuple[_SchemaTable, ...]:
        assert schema_name == "public"
        return (
            _SchemaTable("vertex_a", 2),
            _SchemaTable("edge_b", 3),
            _SchemaTable("dim_c", 1),
        )


def test_live_migration_coverage_summarizes_reflected_schema(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(rw_sql.rw_schema, "load_schema", lambda schema_name: _Schema())
    coverage = rw_sql.live_migration_coverage()
    assert coverage.table_count == 3
    assert coverage.column_count == 6
    assert coverage.vertex_table_count == 1
    assert coverage.edge_table_count == 1
    assert coverage.graph_table_count == 2
    assert coverage.graph_table_ratio == pytest.approx(2 / 3)
