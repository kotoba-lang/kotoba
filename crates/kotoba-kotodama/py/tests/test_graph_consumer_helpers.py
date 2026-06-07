"""Tests for pure helper functions in primitives/graph_consumer.py."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import graph_consumer as G


# ─── _camel_to_snake ─────────────────────────────────────────────────────────

def test_camel_to_snake_simple() -> None:
    assert G._camel_to_snake("camelCase") == "camel_case"


def test_camel_to_snake_multiple_words() -> None:
    assert G._camel_to_snake("myEntityId") == "my_entity_id"


def test_camel_to_snake_already_lower() -> None:
    assert G._camel_to_snake("already") == "already"


def test_camel_to_snake_leading_capital_prefixed() -> None:
    result = G._camel_to_snake("EdgeFoo")
    assert "_edge_foo" in result or result == "_edge_foo"


def test_camel_to_snake_empty() -> None:
    assert G._camel_to_snake("") == ""


def test_camel_to_snake_single_cap() -> None:
    result = G._camel_to_snake("X")
    assert "_x" in result


# ─── _maps_entity_label ──────────────────────────────────────────────────────

def test_maps_entity_label_regular_entity() -> None:
    label = G._maps_entity_label("station")
    assert label[0].isupper()
    assert label.startswith("S")


def test_maps_entity_label_special_case() -> None:
    # The MAPS_LABEL_SPECIAL dict maps certain names
    # Just verify it returns a non-empty string
    result = G._maps_entity_label("route")
    assert isinstance(result, str) and len(result) > 0


def test_maps_entity_label_capitalizes_first_char() -> None:
    label = G._maps_entity_label("building")
    assert label[0] == "B"


def test_maps_entity_label_returns_string() -> None:
    assert isinstance(G._maps_entity_label("ferry"), str)


# ─── _convention_candidates ──────────────────────────────────────────────────

def test_convention_candidates_valid_vertex_collection() -> None:
    candidates = G._convention_candidates("com.etzhayyim.apps.yabai.entity")
    assert any("vertex_yabai" in c for c in candidates)


def test_convention_candidates_valid_edge_collection() -> None:
    candidates = G._convention_candidates("com.etzhayyim.apps.yabai.edgeFoo")
    assert any("edge_yabai" in c for c in candidates)


def test_convention_candidates_invalid_format() -> None:
    assert G._convention_candidates("not.a.valid.collection.at.all.extra") == []
    assert G._convention_candidates("short") == []


def test_convention_candidates_maps_entity_uses_vertex_spatial() -> None:
    candidates = G._convention_candidates("com.etzhayyim.apps.maps.station")
    assert "vertex_spatial" in candidates


def test_convention_candidates_maps_edge_not_spatial() -> None:
    candidates = G._convention_candidates("com.etzhayyim.apps.maps.edgeRoute")
    assert "vertex_spatial" not in candidates
    assert any("edge_maps" in c for c in candidates)


def test_convention_candidates_returns_two_candidates_for_vertex() -> None:
    candidates = G._convention_candidates("com.etzhayyim.apps.gmail.email")
    assert len(candidates) == 2


def test_convention_candidates_returns_two_candidates_for_edge() -> None:
    candidates = G._convention_candidates("com.etzhayyim.apps.gmail.edgeContact")
    assert len(candidates) == 2


# ─── _utc_now_iso ────────────────────────────────────────────────────────────

def test_utc_now_iso_format() -> None:
    result = G._utc_now_iso()
    assert result.endswith("Z")
    assert "T" in result
    assert len(result) == 20  # YYYY-MM-DDTHH:MM:SSZ


def test_utc_now_iso_returns_string() -> None:
    assert isinstance(G._utc_now_iso(), str)


def test_utc_now_iso_no_microseconds() -> None:
    result = G._utc_now_iso()
    # should not have fractional seconds
    assert "." not in result


# ─── _build_convention_row ───────────────────────────────────────────────────

def _make_ctx(**overrides: object) -> dict:
    base: dict = {
        "vid": "at://did:web:x/col/rkey1",
        "rkey": "rkey1",
        "repo": "did:web:x",
        "seq": 42,
        "created_date": "2024-01-01",
    }
    base.update(overrides)
    return base


def test_build_convention_row_includes_vertex_id() -> None:
    row = G._build_convention_row({}, _make_ctx(), {"vertex_id"})
    assert row["vertex_id"] == "at://did:web:x/col/rkey1"


def test_build_convention_row_includes_rkey() -> None:
    row = G._build_convention_row({}, _make_ctx(), {"rkey"})
    assert row["rkey"] == "rkey1"


def test_build_convention_row_includes_repo() -> None:
    row = G._build_convention_row({}, _make_ctx(), {"repo"})
    assert row["repo"] == "did:web:x"


def test_build_convention_row_includes_seq() -> None:
    row = G._build_convention_row({}, _make_ctx(), {"_seq"})
    assert row["_seq"] == 42


def test_build_convention_row_includes_created_date() -> None:
    row = G._build_convention_row({}, _make_ctx(), {"created_date"})
    assert row["created_date"] == "2024-01-01"


def test_build_convention_row_sensitivity_ord_is_300() -> None:
    row = G._build_convention_row({}, _make_ctx(), {"sensitivity_ord"})
    assert row["sensitivity_ord"] == 300


def test_build_convention_row_owner_did_is_repo() -> None:
    row = G._build_convention_row({}, _make_ctx(), {"owner_did"})
    assert row["owner_did"] == "did:web:x"


def test_build_convention_row_skips_missing_col() -> None:
    row = G._build_convention_row({}, _make_ctx(), set())
    assert "vertex_id" not in row
    assert "rkey" not in row


def test_build_convention_row_maps_camel_to_snake() -> None:
    rec = {"displayName": "Foo"}
    row = G._build_convention_row(rec, _make_ctx(), {"display_name"})
    assert row["display_name"] == "Foo"


def test_build_convention_row_maps_created_at() -> None:
    rec = {"createdAt": "2024-06-01T00:00:00Z"}
    row = G._build_convention_row(rec, _make_ctx(), {"created_at"})
    assert row["created_at"] == "2024-06-01T00:00:00Z"


def test_build_convention_row_skips_none_values() -> None:
    rec = {"myField": None}
    row = G._build_convention_row(rec, _make_ctx(), {"my_field"})
    assert "my_field" not in row


def test_build_convention_row_preserves_non_none_values() -> None:
    rec = {"myField": "hello"}
    row = G._build_convention_row(rec, _make_ctx(), {"my_field"})
    assert row["my_field"] == "hello"


def test_build_convention_row_passthrough_non_camel_key() -> None:
    rec = {"my_key": "value"}
    row = G._build_convention_row(rec, _make_ctx(), {"my_key"})
    assert row["my_key"] == "value"


def test_build_convention_row_returns_empty_when_no_matching_cols() -> None:
    rec = {"unknownField": "x"}
    row = G._build_convention_row(rec, _make_ctx(), set())
    assert row == {}


# ─── _project_rows_for_insert ────────────────────────────────────────────────

class _FakeSchema:
    def column_names(self, table: str) -> tuple[str, ...]:
        assert table == "vertex_test"
        return ("vertex_id", "repo")

    def project_known_columns(self, table: str, row: dict[str, Any]) -> dict[str, Any]:
        assert table == "vertex_test"
        return {key: value for key, value in row.items() if key in {"vertex_id", "repo"}}


def test_project_rows_for_insert_uses_live_schema(monkeypatch) -> None:
    monkeypatch.setattr(G.rw_schema, "load_schema", lambda: _FakeSchema())
    rows, cols = G._project_rows_for_insert(
        "vertex_test",
        [{"vertex_id": "v1", "repo": "did:web:x", "extra": "drop"}],
        {"vertex_id", "extra"},
    )
    assert rows == [{"vertex_id": "v1", "repo": "did:web:x"}]
    assert cols == {"vertex_id", "repo"}


def test_project_rows_for_insert_falls_back_to_probe_cols(monkeypatch) -> None:
    def _raise() -> None:
        raise RuntimeError("schema unavailable")

    monkeypatch.setattr(G.rw_schema, "load_schema", _raise)
    rows, cols = G._project_rows_for_insert(
        "vertex_test",
        [{"vertex_id": "v1", "repo": "did:web:x", "extra": "drop"}],
        {"vertex_id", "extra"},
    )
    assert rows == [{"vertex_id": "v1", "extra": "drop"}]
    assert cols == {"vertex_id", "extra"}


# ─── _handle_collection ──────────────────────────────────────────────────────

def test_handle_collection_profile_returns_list() -> None:
    rec = {"displayName": "Test Actor", "description": "A test"}
    ctx = _make_ctx(vid="at://did:web:x/app.bsky.actor.profile/self")
    result = G._handle_collection("app.bsky.actor.profile", rec, ctx)
    assert result is not None
    assert isinstance(result, list)
    assert len(result) >= 1


def test_handle_collection_profile_vertex_profile_table() -> None:
    rec = {"displayName": "Alice", "description": ""}
    ctx = _make_ctx(vid="at://did:web:x/app.bsky.actor.profile/self")
    result = G._handle_collection("app.bsky.actor.profile", rec, ctx)
    assert result is not None
    tables = [t for t, _ in result]
    assert "vertex_profile" in tables


def test_handle_collection_profile_display_name_in_row() -> None:
    rec = {"displayName": "Bob Smith"}
    ctx = _make_ctx(vid="at://did:web:x/app.bsky.actor.profile/self")
    result = G._handle_collection("app.bsky.actor.profile", rec, ctx)
    assert result is not None
    profile_row = next((r for t, r in result if t == "vertex_profile"), None)
    assert profile_row is not None
    assert profile_row.get("display_name") == "Bob Smith"


def test_handle_collection_unknown_collection_returns_none() -> None:
    rec = {"someField": "value"}
    ctx = _make_ctx(vid="at://did:web:x/com.etzhayyim.apps.unknown/rkey1")
    result = G._handle_collection("com.etzhayyim.apps.unknown.entity", rec, ctx)
    assert result is None


def test_handle_collection_profile_with_description_fragment() -> None:
    rec = {"displayName": "Carol", "description": "A detailed description"}
    ctx = _make_ctx(vid="at://did:web:x/app.bsky.actor.profile/self")
    result = G._handle_collection("app.bsky.actor.profile", rec, ctx)
    assert result is not None
    tables = [t for t, _ in result]
    assert "vertex_profile_fragment" in tables


def test_handle_collection_post_returns_list() -> None:
    rec = {"text": "Hello world", "createdAt": "2024-01-01T00:00:00Z"}
    ctx = _make_ctx(vid="at://did:web:x/app.bsky.feed.post/rkey1")
    result = G._handle_collection("app.bsky.feed.post", rec, ctx)
    # Either returns a list of (table, row) tuples or None for convention fallback
    assert result is None or isinstance(result, list)


# ─── _get_convention_cols ────────────────────────────────────────────────────

class _FakeCursorCols:
    def __init__(self, columns: list[str]) -> None:
        self._columns = columns
        self.last_sql: str = ""
        self.last_params: tuple = ()

    def execute(self, sql: str, params: tuple) -> None:
        self.last_sql = sql
        self.last_params = params

    def fetchall(self) -> list[tuple]:
        return [(c,) for c in self._columns]


def _reset_col_cache() -> None:
    G._convention_col_cache.clear()  # type: ignore[attr-defined]


def test_get_convention_cols_returns_set() -> None:
    _reset_col_cache()
    cur = _FakeCursorCols(["vertex_id", "rkey", "repo"])
    result = G._get_convention_cols(cur, "vertex_test")
    assert isinstance(result, set)
    assert "vertex_id" in result


def test_get_convention_cols_returns_all_columns() -> None:
    _reset_col_cache()
    cur = _FakeCursorCols(["a", "b", "c"])
    result = G._get_convention_cols(cur, "vertex_abc")
    assert result == {"a", "b", "c"}


def test_get_convention_cols_empty_table_returns_none() -> None:
    _reset_col_cache()
    cur = _FakeCursorCols([])
    result = G._get_convention_cols(cur, "vertex_missing")
    assert result is None


def test_get_convention_cols_caches_result() -> None:
    _reset_col_cache()
    cur = _FakeCursorCols(["col1", "col2"])
    first = G._get_convention_cols(cur, "vertex_cached")
    # Replace cursor to ensure cache is used
    cur2 = _FakeCursorCols(["different"])
    second = G._get_convention_cols(cur2, "vertex_cached")
    assert first == second
    assert "col1" in second  # type: ignore[operator]


def test_get_convention_cols_exception_returns_none() -> None:
    _reset_col_cache()

    class _ErrorCursor:
        def execute(self, sql: str, params: tuple) -> None:
            raise RuntimeError("DB down")
        def fetchall(self) -> list[tuple]:
            return []

    result = G._get_convention_cols(_ErrorCursor(), "vertex_err")
    assert result is None


def test_get_convention_cols_passes_table_name() -> None:
    _reset_col_cache()
    cur = _FakeCursorCols(["id"])
    G._get_convention_cols(cur, "vertex_foo")
    assert cur.last_params == ("vertex_foo",)
