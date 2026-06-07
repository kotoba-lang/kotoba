import pytest

from kotodama.db_sync import _validate_sql_guard


def test_heavy_ddl_is_blocked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)

    with pytest.raises(RuntimeError, match="heavy DDL is blocked"):
        _validate_sql_guard(
            "CREATE INDEX idx_re_listing_market "
            "ON vertex_real_estate_listing(country_iso2)"
        )


def test_create_table_is_blocked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)

    with pytest.raises(RuntimeError, match="heavy DDL is blocked"):
        _validate_sql_guard("CREATE TABLE IF NOT EXISTS vertex_guard_test (vertex_id TEXT)")


def test_dml_is_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_HEAVY_DDL", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)

    _validate_sql_guard("INSERT INTO vertex_guard_test(vertex_id) VALUES ('v1')")


def test_flush_is_blocked_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("RW_ALLOW_FLUSH", raising=False)
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)

    with pytest.raises(RuntimeError, match="FLUSH is blocked"):
        _validate_sql_guard("FLUSH")


def test_guard_can_be_disabled_for_queue_worker(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RW_ALLOW_HEAVY_DDL", "1")
    monkeypatch.delenv("RW_DDL_GUARD", raising=False)

    _validate_sql_guard("CREATE MATERIALIZED VIEW mv_guard AS SELECT 1")
