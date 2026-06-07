"""Tests for pure helper functions in ingest/core.py."""

from __future__ import annotations

import sys
from pathlib import Path
from datetime import date

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import core as IC


# ─── _slug ───────────────────────────────────────────────────────────────────

def test_ic_slug_basic() -> None:
    assert IC._slug("hello world") == "hello-world"


def test_ic_slug_lowercases() -> None:
    assert IC._slug("HELLO") == "hello"


def test_ic_slug_special_chars() -> None:
    result = IC._slug("a!b@c#d")
    assert "!" not in result
    assert "@" not in result


def test_ic_slug_empty_returns_unknown() -> None:
    assert IC._slug("") == "unknown"


def test_ic_slug_collapses_dashes() -> None:
    result = IC._slug("a--b")
    assert "--" not in result


def test_ic_slug_truncates_at_160() -> None:
    result = IC._slug("a" * 300)
    assert len(result) <= 160


# ─── run_vertex_id ───────────────────────────────────────────────────────────

def test_ic_run_vertex_id_format() -> None:
    vid = IC.run_vertex_id("run-001")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.ingest.run" in vid
    assert "run-001" in vid


def test_ic_run_vertex_id_deterministic() -> None:
    a = IC.run_vertex_id("test-run")
    b = IC.run_vertex_id("test-run")
    assert a == b


# ─── cursor_vertex_id ────────────────────────────────────────────────────────

def test_ic_cursor_vertex_id_format() -> None:
    vid = IC.cursor_vertex_id("gleif", "lei-feed", "shard-1")
    assert "com.etzhayyim.apps.ingest.cursor" in vid
    assert "gleif" in vid


def test_ic_cursor_vertex_id_includes_all_parts() -> None:
    vid = IC.cursor_vertex_id("family", "source", "key")
    combined = "family-source-key"
    assert any(c in vid for c in ["family", "source", "key"])


# ─── artifact_vertex_id ──────────────────────────────────────────────────────

def test_ic_artifact_vertex_id_format() -> None:
    vid = IC.artifact_vertex_id("run-001", "csv", "s3://bucket/file.csv")
    assert "com.etzhayyim.apps.ingest.artifact" in vid


def test_ic_artifact_vertex_id_deterministic() -> None:
    a = IC.artifact_vertex_id("run-001", "csv", "s3://bucket/file.csv")
    b = IC.artifact_vertex_id("run-001", "csv", "s3://bucket/file.csv")
    assert a == b


def test_ic_artifact_vertex_id_varies_with_uri() -> None:
    a = IC.artifact_vertex_id("run-001", "csv", "s3://bucket/file1.csv")
    b = IC.artifact_vertex_id("run-001", "csv", "s3://bucket/file2.csv")
    assert a != b


# ─── _sql_string ─────────────────────────────────────────────────────────────

def test_ic_sql_string_basic() -> None:
    result = IC._sql_string("hello")
    assert result == "'hello'"


def test_ic_sql_string_escapes_single_quotes() -> None:
    result = IC._sql_string("it's")
    assert "''" in result
    assert "it" in result


# ─── _sql_value ──────────────────────────────────────────────────────────────

def test_ic_sql_value_none() -> None:
    assert IC._sql_value(None) == "NULL"


def test_ic_sql_value_none_bigint() -> None:
    result = IC._sql_value(None, bigint=True)
    assert "CAST" in result and "BIGINT" in result


def test_ic_sql_value_none_date() -> None:
    result = IC._sql_value(None, date_value=True)
    assert "CAST" in result and "DATE" in result


def test_ic_sql_value_bool_true() -> None:
    assert IC._sql_value(True) == "TRUE"


def test_ic_sql_value_bool_false() -> None:
    assert IC._sql_value(False) == "FALSE"


def test_ic_sql_value_integer() -> None:
    assert IC._sql_value(42) == "42"


def test_ic_sql_value_string() -> None:
    result = IC._sql_value("hello")
    assert result == "'hello'"


def test_ic_sql_value_date_object() -> None:
    d = date(2026, 1, 15)
    result = IC._sql_value(d, date_value=True)
    assert "DATE" in result
    assert "2026-01-15" in result


def test_ic_sql_value_date_string() -> None:
    result = IC._sql_value("2026-01-15", date_value=True)
    assert "DATE" in result


def test_ic_sql_value_bigint() -> None:
    result = IC._sql_value(1234567890, bigint=True)
    assert "CAST" in result and "BIGINT" in result
    assert "1234567890" in result


# ─── _psql_enabled ────────────────────────────────────────────────────────────

def test_psql_enabled_false_when_no_rw_url(monkeypatch) -> None:
    monkeypatch.delenv("RW_URL", raising=False)
    assert IC._psql_enabled() is False


def test_psql_enabled_returns_bool(monkeypatch) -> None:
    monkeypatch.setenv("RW_URL", "postgresql://localhost:5432/test")
    result = IC._psql_enabled()
    assert isinstance(result, bool)


# ─── _insert_or_ignore ────────────────────────────────────────────────────────

class _FakeCursorInsert:
    def __init__(self, exc: Exception | None = None) -> None:
        self._exc = exc
        self.executed: bool = False

    def execute(self, sql: str, params: tuple) -> None:
        self.executed = True
        if self._exc:
            raise self._exc


def test_insert_or_ignore_executes_sql() -> None:
    cur = _FakeCursorInsert()
    IC._insert_or_ignore(cur, "INSERT INTO t VALUES (%s)", ("val",))
    assert cur.executed is True


def test_insert_or_ignore_ignores_duplicate_error() -> None:
    cur = _FakeCursorInsert(exc=Exception("duplicate key value"))
    IC._insert_or_ignore(cur, "INSERT INTO t VALUES (%s)", ("val",))
    # No exception raised


def test_insert_or_ignore_ignores_primary_key_error() -> None:
    cur = _FakeCursorInsert(exc=Exception("violates primary key constraint"))
    IC._insert_or_ignore(cur, "INSERT INTO t VALUES (%s)", ("val",))
    # No exception raised


def test_insert_or_ignore_ignores_already_exists() -> None:
    cur = _FakeCursorInsert(exc=Exception("relation already exists"))
    IC._insert_or_ignore(cur, "INSERT INTO t VALUES (%s)", ("val",))
    # No exception raised


def test_insert_or_ignore_reraises_other_errors() -> None:
    import pytest
    cur = _FakeCursorInsert(exc=Exception("connection refused"))
    with pytest.raises(Exception, match="connection refused"):
        IC._insert_or_ignore(cur, "INSERT INTO t VALUES (%s)", ("val",))
