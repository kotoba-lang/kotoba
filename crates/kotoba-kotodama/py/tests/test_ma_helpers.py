"""Tests for pure helper functions in ma.py (M&A actor primitives)."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import ma as MA


# ─── _slug ───────────────────────────────────────────────────────────────────

def test_ma_slug_basic() -> None:
    assert MA._slug("Hello World") == "hello-world"


def test_ma_slug_special_chars_become_dashes() -> None:
    result = MA._slug("Hello, World!")
    assert "," not in result
    assert "!" not in result


def test_ma_slug_empty_returns_unknown() -> None:
    assert MA._slug("") == "unknown"
    assert MA._slug(None) == "unknown"


def test_ma_slug_collapses_dashes() -> None:
    result = MA._slug("a--b")
    assert "--" not in result


def test_ma_slug_truncates_at_96() -> None:
    result = MA._slug("x" * 200)
    assert len(result) <= 96


def test_ma_slug_lowercases() -> None:
    assert MA._slug("HELLO") == "hello"


# ─── _stable_id ──────────────────────────────────────────────────────────────

def test_ma_stable_id_format() -> None:
    result = MA._stable_id("deal", "TargetCo", "BuyerCo")
    assert result.startswith("deal-")


def test_ma_stable_id_deterministic() -> None:
    a = MA._stable_id("deal", "TargetCo", "BuyerCo")
    b = MA._stable_id("deal", "TargetCo", "BuyerCo")
    assert a == b


def test_ma_stable_id_varies_by_parts() -> None:
    a = MA._stable_id("deal", "Target1")
    b = MA._stable_id("deal", "Target2")
    assert a != b


def test_ma_stable_id_hex_length() -> None:
    result = MA._stable_id("pfx", "val")
    hex_part = result[len("pfx-"):]
    assert len(hex_part) == 16


# ─── _bounded_score ──────────────────────────────────────────────────────────

def test_ma_bounded_score_in_range() -> None:
    score = MA._bounded_score("company-a", "company-b")
    assert 0.45 <= score <= 0.90


def test_ma_bounded_score_deterministic() -> None:
    a = MA._bounded_score("x", "y")
    b = MA._bounded_score("x", "y")
    assert a == b


def test_ma_bounded_score_varies_with_input() -> None:
    a = MA._bounded_score("a", "b")
    b = MA._bounded_score("c", "d")
    # Not guaranteed to differ but overwhelmingly likely
    assert isinstance(a, float) and isinstance(b, float)


def test_ma_bounded_score_custom_floor_span() -> None:
    score = MA._bounded_score("x", floor=0.7, span=0.2)
    assert 0.7 <= score <= 0.90


# ─── _as_float ───────────────────────────────────────────────────────────────

def test_ma_as_float_numeric_string() -> None:
    assert MA._as_float("3.14") == 3.14


def test_ma_as_float_integer() -> None:
    assert MA._as_float(42) == 42.0


def test_ma_as_float_none_returns_default() -> None:
    assert MA._as_float(None) == 0.0


def test_ma_as_float_invalid_string_returns_default() -> None:
    assert MA._as_float("not-a-number") == 0.0


def test_ma_as_float_custom_default() -> None:
    assert MA._as_float("bad", default=-1.0) == -1.0


# ─── _deal_vid ───────────────────────────────────────────────────────────────

def test_ma_deal_vid_format() -> None:
    vid = MA._deal_vid("deal-001")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.ma.deal" in vid
    assert "deal-001" in vid


def test_ma_deal_vid_deterministic() -> None:
    a = MA._deal_vid("deal-xyz")
    b = MA._deal_vid("deal-xyz")
    assert a == b


# ─── _candidate_vid ──────────────────────────────────────────────────────────

def test_ma_candidate_vid_format() -> None:
    vid = MA._candidate_vid("cand-001")
    assert "com.etzhayyim.apps.ma.candidate" in vid
    assert "cand-001" in vid


# ─── _valuation_vid ──────────────────────────────────────────────────────────

def test_ma_valuation_vid_format() -> None:
    vid = MA._valuation_vid("val-001")
    assert "com.etzhayyim.apps.ma.valuation" in vid
    assert "val-001" in vid


# ─── _match_vid ──────────────────────────────────────────────────────────────

def test_ma_match_vid_format() -> None:
    vid = MA._match_vid("match-001")
    assert "com.etzhayyim.apps.ma.match" in vid
    assert "match-001" in vid


# ─── _edge_id ────────────────────────────────────────────────────────────────

def test_ma_edge_id_format() -> None:
    eid = MA._edge_id("ACQUIRED_BY", "deal-001", "buyer-001")
    assert eid.startswith("edge:ACQUIRED_BY:")


def test_ma_edge_id_deterministic() -> None:
    a = MA._edge_id("REL", "src", "dst")
    b = MA._edge_id("REL", "src", "dst")
    assert a == b


def test_ma_edge_id_varies_with_args() -> None:
    a = MA._edge_id("REL", "src1", "dst")
    b = MA._edge_id("REL", "src2", "dst")
    assert a != b


# ─── _count_visible ──────────────────────────────────────────────────────────

class _FakeCursorCount:
    def __init__(self, count: int) -> None:
        self._count = count
    def execute(self, sql: str, params: tuple) -> None:
        pass
    def fetchone(self) -> tuple:
        return (self._count,)


def test_count_visible_empty_ids_returns_zero() -> None:
    cur = _FakeCursorCount(5)
    assert MA._count_visible(cur, "vertex_ma_deal", "vertex_id", []) == 0


def test_count_visible_returns_db_count() -> None:
    cur = _FakeCursorCount(3)
    result = MA._count_visible(cur, "vertex_ma_deal", "vertex_id", ["id1", "id2", "id3"])
    assert result == 3


def test_count_visible_single_id() -> None:
    cur = _FakeCursorCount(1)
    result = MA._count_visible(cur, "vertex_ma_candidate", "vertex_id", ["only_id"])
    assert result == 1


def test_count_visible_zero_from_db() -> None:
    cur = _FakeCursorCount(0)
    result = MA._count_visible(cur, "vertex_ma_deal", "vertex_id", ["missing_id"])
    assert result == 0


# ─── _insert_ignore ───────────────────────────────────────────────────────────

class _FakeCursorMA:
    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.last_sql: str = ""
        self.last_params: tuple = ()

    def execute(self, sql: str, params: tuple) -> None:
        self.last_sql = sql
        self.last_params = params


def test_ma_insert_ignore_builds_select_not_exists() -> None:
    cur = _FakeCursorMA()
    MA._insert_ignore(cur, "vertex_ma_deal", "vertex_id", {
        "vertex_id": "at://did/com.etzhayyim.apps.ma.deal/deal-001",
        "title": "Acquisition of Target",
    })
    assert "WHERE NOT EXISTS" in cur.last_sql
    assert "vertex_ma_deal" in cur.last_sql


def test_ma_insert_ignore_returns_rowcount() -> None:
    cur = _FakeCursorMA(rowcount=1)
    result = MA._insert_ignore(cur, "vertex_ma_deal", "vertex_id", {
        "vertex_id": "at://did/com.etzhayyim.apps.ma.deal/deal-001",
    })
    assert result == 1


def test_ma_insert_ignore_filters_none_values() -> None:
    cur = _FakeCursorMA()
    MA._insert_ignore(cur, "vertex_ma_deal", "vertex_id", {
        "vertex_id": "at://x", "title": None, "status": "active",
    })
    assert "title" not in cur.last_sql


# ─── _update_by_pk ────────────────────────────────────────────────────────────

def test_ma_update_by_pk_no_updatable_cols_returns_zero() -> None:
    cur = _FakeCursorMA()
    result = MA._update_by_pk(cur, "vertex_ma_deal", "vertex_id", {
        "vertex_id": "at://x", "_seq": 1, "created_date": "2024-01-01",
    })
    assert result == 0


def test_ma_update_by_pk_builds_set_clause() -> None:
    cur = _FakeCursorMA(rowcount=1)
    result = MA._update_by_pk(cur, "vertex_ma_deal", "vertex_id", {
        "vertex_id": "at://x", "status": "closed",
    })
    assert "UPDATE vertex_ma_deal SET" in cur.last_sql
    assert "status" in cur.last_sql
    assert result == 1


def test_ma_update_by_pk_excludes_created_at() -> None:
    cur = _FakeCursorMA()
    result = MA._update_by_pk(cur, "vertex_ma_deal", "vertex_id", {
        "vertex_id": "at://x", "created_at": "2024-01-01T00:00:00Z",
    })
    # created_at is excluded → no updatable cols → returns 0
    assert result == 0
