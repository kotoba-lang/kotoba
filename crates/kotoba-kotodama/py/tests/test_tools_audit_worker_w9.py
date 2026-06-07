"""Smoke tests for W9 — tools_audit_worker_main (audit log pattern).

Tests run entirely in a tempfile.TemporaryDirectory — no external services.
No Zeebe / SDK / psycopg dependency required.

Assertions per checklist:
  1. emit + row visible in SQLite           (2 emit)
  2. idempotent re-emit (INSERT OR REPLACE) (2 emit)
  3. error case: empty repo returns error   (1 error case)
"""
from __future__ import annotations

import asyncio
import os
import sqlite3
import tempfile
from pathlib import Path

import pytest

from kotodama.tools_audit_worker_main import task_audit_emit, _db_path


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture()
def tmp_sqlite_dir(monkeypatch, tmp_path):
    """Point ORGANISM_SQLITE_DIR at a fresh tempdir and patch the module."""
    monkeypatch.setenv("ORGANISM_SQLITE_DIR", str(tmp_path))
    # Patch the cached Path object inside the module
    import kotodama.tools_audit_worker_main as mod
    monkeypatch.setattr(mod, "_ORGANISM_SQLITE_DIR", tmp_path)
    return tmp_path


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _rows(db: Path, repo: str) -> list[dict]:
    with sqlite3.connect(str(db)) as conn:
        conn.row_factory = sqlite3.Row
        return [dict(r) for r in conn.execute(
            "SELECT * FROM audit_commit WHERE repo = ? ORDER BY ts_ms",
            (repo,),
        ).fetchall()]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

def test_emit_two_rows_visible_in_sqlite(tmp_sqlite_dir):
    """Emit 2 rows for the same repo; both must appear in the DB."""
    repo = "shosha"
    r1 = asyncio.run(task_audit_emit(
        repo=repo, collection="com.etzhayyim.apps.shosha.trade",
        rkey="rk001", action="create",
        recordJson={"amount": 100},
    ))
    r2 = asyncio.run(task_audit_emit(
        repo=repo, collection="com.etzhayyim.apps.shosha.trade",
        rkey="rk002", action="update",
        recordJson={"amount": 200},
    ))

    # Both calls returned vertexId without error
    assert "vertexId" in r1 and "error" not in r1
    assert "vertexId" in r2 and "error" not in r2

    db = _db_path(repo)
    rows = _rows(db, repo)
    assert len(rows) == 2, f"Expected 2 rows, got {len(rows)}"
    assert rows[0]["rkey"] == "rk001"
    assert rows[1]["rkey"] == "rk002"


def test_insert_or_replace_is_idempotent(tmp_sqlite_dir):
    """Re-emitting the same rkey+action must not create a duplicate row."""
    repo = "isbn"
    kwargs = dict(
        repo=repo, collection="com.etzhayyim.apps.isbn.book",
        rkey="fixed-rkey", action="create",
        recordJson={"title": "first"},
    )
    asyncio.run(task_audit_emit(**kwargs))
    # Re-emit with same vertex_id key but updated payload
    asyncio.run(task_audit_emit(**{**kwargs, "recordJson": {"title": "updated"}}))

    db = _db_path(repo)
    rows = _rows(db, repo)
    assert len(rows) == 1, "INSERT OR REPLACE must keep exactly 1 row"
    import json
    assert json.loads(rows[0]["record_json"])["title"] == "updated"


def test_error_case_empty_repo(tmp_sqlite_dir):
    """Missing repo must return an error dict without touching the filesystem."""
    result = asyncio.run(task_audit_emit(
        repo="", collection="some.collection", action="create"
    ))
    assert "error" in result
    assert result["error"] == "repo / collection / action required"
