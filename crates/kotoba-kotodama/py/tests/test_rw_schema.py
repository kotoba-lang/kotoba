from __future__ import annotations

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama import rw_schema


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "table_schema": "public",
            "table_name": "vertex_test",
            "column_name": "vertex_id",
            "data_type": "character varying",
            "ordinal_position": 1,
            "is_nullable": "NO",
            "column_default": None,
        },
        {
            "table_schema": "public",
            "table_name": "vertex_test",
            "column_name": "owner_did",
            "data_type": "character varying",
            "ordinal_position": 2,
            "is_nullable": "YES",
            "column_default": None,
        },
    ]


def test_schema_from_information_schema_rows_projects_known_columns() -> None:
    schema = rw_schema.RisingWaveSchema.from_information_schema_rows(_rows())
    assert schema.has_table("vertex_test")
    assert schema.column_names("vertex_test") == ("vertex_id", "owner_did")
    assert schema.project_known_columns(
        "vertex_test",
        {"vertex_id": "v1", "owner_did": "did:web:x", "extra": "drop"},
    ) == {"vertex_id": "v1", "owner_did": "did:web:x"}


def test_validate_insert_rejects_unknown_column() -> None:
    schema = rw_schema.RisingWaveSchema.from_information_schema_rows(_rows())
    with pytest.raises(ValueError, match="Unknown columns"):
        schema.validate_insert("vertex_test", {"vertex_id": "v1", "extra": "bad"})


def test_validate_insert_can_require_non_nullable_columns() -> None:
    schema = rw_schema.RisingWaveSchema.from_information_schema_rows(_rows())
    with pytest.raises(ValueError, match="Missing required columns"):
        schema.validate_insert("vertex_test", {"owner_did": "did:web:x"}, require_non_nullable=True)


class _FakeCursor:
    description = [
        ("table_schema",),
        ("table_name",),
        ("column_name",),
        ("data_type",),
        ("ordinal_position",),
        ("is_nullable",),
        ("column_default",),
    ]

    def __init__(self, calls: list[tuple[str, tuple[Any, ...]]]) -> None:
        self.calls = calls

    def execute(self, sql: str, params: tuple[Any, ...] = ()) -> None:
        self.calls.append((sql, params))

    def fetchall(self) -> list[tuple[Any, ...]]:
        return [
            (
                row["table_schema"],
                row["table_name"],
                row["column_name"],
                row["data_type"],
                row["ordinal_position"],
                row["is_nullable"],
                row["column_default"],
            )
            for row in _rows()
        ]


def test_load_schema_uses_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[tuple[str, tuple[Any, ...]]] = []

    @contextmanager
    def fake_sync_cursor():
        yield _FakeCursor(calls)

    monkeypatch.setattr(rw_schema.db_sync, "sync_cursor", fake_sync_cursor)
    rw_schema.clear_schema_cache()
    try:
        first = rw_schema.load_schema(force=True)
        second = rw_schema.load_schema()
        assert first is second
        assert len(calls) == 1
        assert calls[0][1] == ("public", "public")
    finally:
        rw_schema.clear_schema_cache()
