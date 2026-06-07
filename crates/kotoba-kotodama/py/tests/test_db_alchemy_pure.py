"""Pure-path tests for db_alchemy.py (ADR-2605080300).

All tests are pure: sync_cursor is replaced with a MagicMock context manager
so no real RisingWave connection is needed.

Coverage:
- sa_execute / sa_query / sa_execute_one — compile + route through sync_cursor
- sa_rowcount — returns cursor.rowcount
- sa_executemany — chunks rows, calls cursor.executemany per chunk
- _compile_clause — text() passthrough + SA expression compilation
- get_sa_engine — NullPool engine creation (env guard, singleton)
- sa_metadata — singleton MetaData
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch, call

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

import kotodama.db_alchemy as DA  # noqa: E402


# ── helpers ────────────────────────────────────────────────────────────────────

def _mock_cursor_cm(rows: list | None = None, rowcount: int = 0) -> MagicMock:
    cur = MagicMock()
    cur.fetchall.return_value = rows if rows is not None else []
    cur.fetchone.return_value = rows[0] if rows else None
    cur.rowcount = rowcount
    cm = MagicMock()
    cm.__enter__ = MagicMock(return_value=cur)
    cm.__exit__ = MagicMock(return_value=False)
    return MagicMock(return_value=cm)


# ── _compile_clause ────────────────────────────────────────────────────────────

class TestCompileClause:
    def test_text_passthrough(self) -> None:
        from sqlalchemy import text
        sql, params = DA._compile_clause(text("SELECT 1"), {"x": 1})
        assert "SELECT 1" in sql
        assert params == {"x": 1}

    def test_raw_string_passthrough(self) -> None:
        sql, params = DA._compile_clause("SELECT 2")
        assert sql == "SELECT 2"
        assert params == {}

    def test_sa_expression_compiles(self) -> None:
        from sqlalchemy import select, Table, Column, String
        t = Table("vertex_actor", DA.sa_metadata(), Column("actor_did", String))
        sql, params = DA._compile_clause(select(t.c.actor_did))
        assert "vertex_actor" in sql
        assert "actor_did" in sql


# ── sa_execute / sa_query ──────────────────────────────────────────────────────

class TestSaExecute:
    def test_returns_rows(self) -> None:
        rows = [("did:plc:abc",), ("did:plc:def",)]
        mock_sc = _mock_cursor_cm(rows)
        with patch.object(DA, "sync_cursor" if hasattr(DA, "sync_cursor") else "_noop", mock_sc, create=True):
            # Patch sync_cursor inside db_alchemy's import namespace
            import kotodama.db_sync as ds
            orig = ds.sync_cursor
            ds.sync_cursor = mock_sc
            try:
                from sqlalchemy import text
                result = DA.sa_execute(text("SELECT actor_did FROM vertex_actor LIMIT 2"))
                assert result == rows
            finally:
                ds.sync_cursor = orig

    def test_empty_returns_empty_list(self) -> None:
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        ds.sync_cursor = _mock_cursor_cm([])
        try:
            from sqlalchemy import text
            result = DA.sa_execute(text("SELECT 1 WHERE false"))
            assert result == []
        finally:
            ds.sync_cursor = orig

    def test_sa_query_alias(self) -> None:
        rows = [("x",)]
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        ds.sync_cursor = _mock_cursor_cm(rows)
        try:
            from sqlalchemy import text
            result = DA.sa_query(text("SELECT 'x'"))
            assert result == rows
        finally:
            ds.sync_cursor = orig

    def test_params_forwarded(self) -> None:
        captured: list[tuple] = []

        def capturing_cursor():
            cur = MagicMock()
            cur.fetchall.return_value = []

            def exec_capture(sql, params=None):
                captured.append((sql, params))

            cur.execute.side_effect = exec_capture
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cur)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        ds.sync_cursor = capturing_cursor
        try:
            from sqlalchemy import text
            DA.sa_execute(text("SELECT 1 WHERE x = %(n)s"), {"n": 42})
            assert captured, "execute was not called"
            assert captured[0][1] == {"n": 42}
        finally:
            ds.sync_cursor = orig


# ── sa_execute_one ─────────────────────────────────────────────────────────────

class TestSaExecuteOne:
    def test_returns_first_row(self) -> None:
        rows = [("first",), ("second",)]
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        ds.sync_cursor = _mock_cursor_cm(rows)
        try:
            from sqlalchemy import text
            result = DA.sa_execute_one(text("SELECT 1"))
            assert result == ("first",)
        finally:
            ds.sync_cursor = orig

    def test_returns_none_when_empty(self) -> None:
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        ds.sync_cursor = _mock_cursor_cm([])
        try:
            from sqlalchemy import text
            result = DA.sa_execute_one(text("SELECT 1 WHERE false"))
            assert result is None
        finally:
            ds.sync_cursor = orig


# ── sa_rowcount ────────────────────────────────────────────────────────────────

class TestSaRowcount:
    def test_returns_rowcount(self) -> None:
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        ds.sync_cursor = _mock_cursor_cm([], rowcount=3)
        try:
            from sqlalchemy import text
            rc = DA.sa_rowcount(text("UPDATE vertex_foo SET x=1"))
            assert rc == 3
        finally:
            ds.sync_cursor = orig

    def test_zero_when_no_rows_affected(self) -> None:
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        ds.sync_cursor = _mock_cursor_cm([], rowcount=0)
        try:
            from sqlalchemy import text
            rc = DA.sa_rowcount(text("UPDATE vertex_foo SET x=1 WHERE false"))
            assert rc == 0
        finally:
            ds.sync_cursor = orig


# ── sa_executemany ─────────────────────────────────────────────────────────────

class TestSaExecutemany:
    def test_returns_total_rows_processed(self) -> None:
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        calls: list = []

        def capturing_cursor():
            cur = MagicMock()
            cur.executemany.side_effect = lambda sql, batch: calls.extend(batch)
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cur)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        ds.sync_cursor = capturing_cursor
        try:
            from sqlalchemy import Table, Column, String, insert
            t = Table("vertex_test_batch", DA.sa_metadata(), Column("vertex_id", String))
            rows = [{"vertex_id": f"v{i}"} for i in range(10)]
            total = DA.sa_executemany(insert(t), rows, chunk_size=4)
            assert total == 10
        finally:
            ds.sync_cursor = orig

    def test_chunks_correctly(self) -> None:
        import kotodama.db_sync as ds
        orig = ds.sync_cursor
        executemany_calls: list[list] = []

        def capturing_cursor():
            cur = MagicMock()

            def capture(sql, batch):
                executemany_calls.append(list(batch))

            cur.executemany.side_effect = capture
            cm = MagicMock()
            cm.__enter__ = MagicMock(return_value=cur)
            cm.__exit__ = MagicMock(return_value=False)
            return cm

        ds.sync_cursor = capturing_cursor
        try:
            from sqlalchemy import Table, Column, String, insert
            t = Table("vertex_test_chunk", DA.sa_metadata(), Column("vertex_id", String))
            rows = [{"vertex_id": f"v{i}"} for i in range(7)]
            DA.sa_executemany(insert(t), rows, chunk_size=3)
            # 7 rows in chunks of 3 → 3 executemany calls (3+3+1)
            assert len(executemany_calls) == 3
            assert len(executemany_calls[0]) == 3
            assert len(executemany_calls[1]) == 3
            assert len(executemany_calls[2]) == 1
        finally:
            ds.sync_cursor = orig

    def test_empty_rows_returns_zero(self) -> None:
        from sqlalchemy import Table, Column, String, insert
        t = Table("vertex_test_empty", DA.sa_metadata(), Column("vertex_id", String))
        total = DA.sa_executemany(insert(t), [])
        assert total == 0


# ── sa_metadata singleton ──────────────────────────────────────────────────────

class TestSaMetadata:
    def test_returns_same_instance(self) -> None:
        m1 = DA.sa_metadata()
        m2 = DA.sa_metadata()
        assert m1 is m2

    def test_is_metadata_type(self) -> None:
        from sqlalchemy import MetaData
        assert isinstance(DA.sa_metadata(), MetaData)


# ── get_sa_engine (env guard) ──────────────────────────────────────────────────

class TestGetSaEngine:
    def setup_method(self) -> None:
        DA._SA_ENGINE = None  # reset singleton between tests

    def teardown_method(self) -> None:
        DA._SA_ENGINE = None

    def test_raises_without_rw_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RW_URL", raising=False)
        with pytest.raises(RuntimeError, match="RW_URL"):
            DA.get_sa_engine()

    def test_creates_engine_with_rw_url(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RW_URL", "postgresql://root:pass@localhost:4566/dev")
        engine = DA.get_sa_engine()
        assert engine is not None
        # Singleton: second call returns same object
        assert DA.get_sa_engine() is engine
