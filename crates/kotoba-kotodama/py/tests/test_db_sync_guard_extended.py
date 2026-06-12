"""Extended tests for db_sync guard helpers and gov primitive pure functions."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.db_sync import (
    _ddl_guard_enabled,
    _allow_heavy_ddl,
    _allow_flush,
    _sync_pool_enabled,
    _validate_sql_guard,
    GuardedCursor,
)


# ─── env var flag helpers ─────────────────────────────────────────────────────

def test_ddl_guard_enabled_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    assert _ddl_guard_enabled() is True


def test_ddl_guard_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_DDL_GUARD", "0")
    assert _ddl_guard_enabled() is False


def test_ddl_guard_disabled_by_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_DDL_GUARD", "false")
    assert _ddl_guard_enabled() is False


def test_allow_heavy_ddl_default_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    assert _allow_heavy_ddl() is False


def test_allow_heavy_ddl_enabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_ALLOW_HEAVY_DDL", "1")
    assert _allow_heavy_ddl() is True


def test_allow_flush_default_false(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_FLUSH", raising=False)
    assert _allow_flush() is False


def test_allow_flush_enabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_ALLOW_FLUSH", "true")
    assert _allow_flush() is True


def test_sync_pool_enabled_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_SYNC_POOL", raising=False)
    assert _sync_pool_enabled() is True


def test_sync_pool_disabled_by_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_SYNC_POOL", "0")
    assert _sync_pool_enabled() is False


# ─── _validate_sql_guard additional cases ────────────────────────────────────

def test_validate_drop_table_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    with pytest.raises(RuntimeError, match="heavy DDL"):
        _validate_sql_guard("DROP TABLE vertex_foo")


def test_validate_alter_table_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    with pytest.raises(RuntimeError, match="heavy DDL"):
        _validate_sql_guard("ALTER TABLE vertex_foo ADD COLUMN bar TEXT")


def test_validate_materialized_view_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    with pytest.raises(RuntimeError, match="heavy DDL"):
        _validate_sql_guard("CREATE MATERIALIZED VIEW mv_test AS SELECT 1")


def test_validate_select_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    _validate_sql_guard("SELECT * FROM vertex_foo WHERE id = 1")


def test_validate_update_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    _validate_sql_guard("UPDATE vertex_foo SET status = 'ok' WHERE id = 1")


def test_validate_non_string_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    _validate_sql_guard(None)  # should not raise
    _validate_sql_guard(42)    # should not raise


def test_validate_empty_string_passthrough(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    _validate_sql_guard("")  # should not raise
    _validate_sql_guard("   ")  # should not raise


def test_validate_guard_disabled_allows_ddl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_DDL_GUARD", "0")
    _validate_sql_guard("DROP TABLE vertex_test")  # should not raise


def test_validate_flush_allowed_when_env_set(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_ALLOW_FLUSH", "1")
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    _validate_sql_guard("FLUSH")  # should not raise


# ─── GuardedCursor ───────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self) -> None:
        self.last_sql: str = ""
        self.rowcount = 1

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.last_sql = sql

    def fetchone(self) -> tuple | None:
        return None


def test_guarded_cursor_executes_allowed_sql(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    fake = _FakeCursor()
    cur = GuardedCursor(fake)
    cur.execute("SELECT 1", ())
    assert fake.last_sql == "SELECT 1"


def test_guarded_cursor_blocks_ddl(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)
    fake = _FakeCursor()
    cur = GuardedCursor(fake)
    with pytest.raises(RuntimeError, match="heavy DDL"):
        cur.execute("DROP TABLE vertex_test")


def test_guarded_cursor_delegates_attributes() -> None:
    fake = _FakeCursor()
    cur = GuardedCursor(fake)
    assert cur.rowcount == 1


def test_guarded_cursor_fetchone_delegates() -> None:
    fake = _FakeCursor()
    cur = GuardedCursor(fake)
    assert cur.fetchone() is None


# ─── gov module shared pure helpers ──────────────────────────────────────────

from kotodama.primitives import gov_afg as GA


def test_gov_url_to_domain_slug_standard() -> None:
    assert GA._url_to_domain_slug("https://president.gov.af") == "president-gov-af"


def test_gov_url_to_domain_slug_strips_www() -> None:
    result = GA._url_to_domain_slug("https://www.example.com/path")
    assert "www" not in result
    assert "example-com" in result


def test_gov_url_to_domain_slug_empty_returns_empty() -> None:
    assert GA._url_to_domain_slug("") == ""


def test_gov_vertex_id_starts_with_at() -> None:
    vid = GA._vertex_id("mod")
    assert vid.startswith("at://did:web:afg-state.etzhayyim.com/")
    assert "mod" in vid


def test_gov_vertex_id_collection_in_path() -> None:
    vid = GA._vertex_id("mof")
    assert "com.etzhayyim.apps.states.govOrg" in vid


def test_gov_load_seed_orgs_returns_list() -> None:
    orgs = GA._load_seed_orgs()
    assert isinstance(orgs, list)
    assert len(orgs) > 0


def test_gov_load_seed_orgs_have_required_fields() -> None:
    orgs = GA._load_seed_orgs()
    for org in orgs[:3]:
        assert "path" in org
        assert "name" in org


def test_gov_load_seed_orgs_contains_ministries_and_provinces() -> None:
    orgs = GA._load_seed_orgs()
    paths = [o["path"] for o in orgs]
    assert "mod" in paths  # Ministry of Defence
    assert "kabul" in paths  # Kabul Province
