"""Tests for pure helper functions in ingest/fund/ids.py and types.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest.fund import ids as I
from kotodama.ingest.fund.types import drop_none


# ─── clean ───────────────────────────────────────────────────────────────────

def test_clean_strips_whitespace() -> None:
    assert I.clean("  hello  ") == "hello"


def test_clean_none_returns_empty() -> None:
    assert I.clean(None) == ""


def test_clean_integer() -> None:
    assert I.clean(42) == "42"


def test_clean_empty_string() -> None:
    assert I.clean("") == ""


# ─── slug ────────────────────────────────────────────────────────────────────

def test_slug_passthrough_alphanumeric() -> None:
    assert I.slug("hello123") == "hello123"


def test_slug_lowercases() -> None:
    assert I.slug("HelloWorld") == "helloworld"


def test_slug_replaces_spaces_with_dash() -> None:
    result = I.slug("hello world")
    assert " " not in result
    assert "hello" in result and "world" in result


def test_slug_collapses_consecutive_dashes() -> None:
    result = I.slug("a--b")
    assert "--" not in result
    assert "a" in result and "b" in result


def test_slug_empty_returns_unknown() -> None:
    assert I.slug("") == "unknown"
    assert I.slug("   ") == "unknown"
    assert I.slug("!!!") == "unknown"


def test_slug_truncates_at_max_len() -> None:
    assert len(I.slug("a" * 300)) <= 180


def test_slug_custom_max_len() -> None:
    result = I.slug("a" * 300, max_len=50)
    assert len(result) <= 50


# ─── digest_slug ─────────────────────────────────────────────────────────────

def test_digest_slug_deterministic() -> None:
    assert I.digest_slug("a", "b", "c") == I.digest_slug("a", "b", "c")


def test_digest_slug_varies_with_parts() -> None:
    assert I.digest_slug("x") != I.digest_slug("y")


def test_digest_slug_default_size() -> None:
    h = I.digest_slug("test")
    assert len(h) == 16  # digest_size=8 → 16 hex chars


def test_digest_slug_custom_size() -> None:
    h = I.digest_slug("test", size=4)
    assert len(h) == 8  # digest_size=4 → 8 hex chars


def test_digest_slug_multiple_parts() -> None:
    h = I.digest_slug("a", "b", "c", size=6)
    assert len(h) == 12


# ─── cik_key ─────────────────────────────────────────────────────────────────

def test_cik_key_strips_non_digits() -> None:
    assert I.cik_key("CIK0001234567") == "1234567"


def test_cik_key_plain_digits() -> None:
    assert I.cik_key("0001234567") == "1234567"


def test_cik_key_strips_leading_zeros() -> None:
    assert I.cik_key("0000042") == "42"


def test_cik_key_none_returns_empty() -> None:
    assert I.cik_key(None) == ""


def test_cik_key_all_zeros_returns_empty() -> None:
    assert I.cik_key("000") == ""


# ─── manager_id ──────────────────────────────────────────────────────────────

def test_manager_id_lei_takes_priority() -> None:
    result = I.manager_id(source_id="sec", cik="123", crd="456", lei="LEI123", name="Foo")
    assert result.startswith("lei-")
    assert "lei123" in result


def test_manager_id_crd_second_priority() -> None:
    result = I.manager_id(source_id="sec", cik="123", crd="456", name="Foo")
    assert result.startswith("crd-")


def test_manager_id_cik_third_priority() -> None:
    result = I.manager_id(source_id="sec", cik="0001234567", name="Foo")
    assert result.startswith("sec-cik-")
    assert "1234567" in result


def test_manager_id_fallback_to_source_digest() -> None:
    result = I.manager_id(source_id="pf", name="Acme Capital")
    assert result.startswith("pf-")
    parts = result.split("-")
    assert len(parts) >= 2


def test_manager_id_deterministic() -> None:
    a = I.manager_id(source_id="pf", name="Acme Capital")
    b = I.manager_id(source_id="pf", name="Acme Capital")
    assert a == b


# ─── fund_id ─────────────────────────────────────────────────────────────────

def test_fund_id_uses_native_when_present() -> None:
    result = I.fund_id(source_id="pf", adviser_id="adv-abc", native_fund_id="FUND001")
    assert "pf" in result
    assert "fund001" in result


def test_fund_id_fallback_to_source_adviser_digest() -> None:
    result = I.fund_id(source_id="pf", adviser_id="adv-abc", name="My Fund")
    assert "pf" in result
    assert "adv-abc" in result


def test_fund_id_deterministic() -> None:
    a = I.fund_id(source_id="pf", adviser_id="adv-abc", name="My Fund")
    b = I.fund_id(source_id="pf", adviser_id="adv-abc", name="My Fund")
    assert a == b


# ─── vertex id helpers ───────────────────────────────────────────────────────

def test_manager_vertex_id_shape() -> None:
    vid = I.manager_vertex_id("adv-123")
    assert vid.startswith("at://did:web:fund.etzhayyim.com/")
    assert "com.etzhayyim.apps.fund.manager" in vid


def test_fund_vertex_id_shape() -> None:
    vid = I.fund_vertex_id("fund-abc")
    assert vid.startswith("at://did:web:fund.etzhayyim.com/")
    assert "com.etzhayyim.apps.fund.fund" in vid


def test_investor_vertex_id_shape() -> None:
    vid = I.investor_vertex_id("inv-001")
    assert vid.startswith("at://did:web:fund.etzhayyim.com/")
    assert "investor" in vid


def test_investee_vertex_id_shape() -> None:
    vid = I.investee_vertex_id("comp-xyz")
    assert vid.startswith("at://did:web:fund.etzhayyim.com/")
    assert "investee" in vid


def test_vertex_id_deterministic() -> None:
    a = I.manager_vertex_id("adv-123")
    b = I.manager_vertex_id("adv-123")
    assert a == b


# ─── edge_id ─────────────────────────────────────────────────────────────────

def test_edge_id_shape() -> None:
    eid = I.edge_id("invests_in", "at://src", "at://dst")
    assert "invests-in" in eid or "invests_in" in eid.replace("-", "_")


def test_edge_id_deterministic() -> None:
    a = I.edge_id("holds", "src-a", "dst-b")
    b = I.edge_id("holds", "src-a", "dst-b")
    assert a == b


def test_edge_id_varies_by_endpoints() -> None:
    a = I.edge_id("holds", "src-a", "dst-b")
    b = I.edge_id("holds", "src-c", "dst-d")
    assert a != b


def test_edge_id_extra_parts_change_hash() -> None:
    a = I.edge_id("holds", "src", "dst")
    b = I.edge_id("holds", "src", "dst", "extra")
    assert a != b


# ─── drop_none ───────────────────────────────────────────────────────────────

def test_drop_none_removes_none_values() -> None:
    result = drop_none({"a": 1, "b": None, "c": "x"})
    assert "b" not in result
    assert result == {"a": 1, "c": "x"}


def test_drop_none_empty_dict() -> None:
    assert drop_none({}) == {}


def test_drop_none_all_none() -> None:
    assert drop_none({"a": None, "b": None}) == {}


def test_drop_none_no_none() -> None:
    d = {"a": 1, "b": 2}
    assert drop_none(d) == d


def test_drop_none_preserves_falsy_non_none() -> None:
    # drop_none removes None and empty strings, but keeps 0 and False
    result = drop_none({"a": 0, "b": "", "c": False, "d": None})
    assert "d" not in result
    assert "b" not in result  # empty string is also dropped
    assert result["a"] == 0
    assert result["c"] is False
