"""Tests for pure helper functions in blockchain, flight_offer ingest modules."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import blockchain as BC
from kotodama.ingest import flight_offer as FO


# ─── blockchain pure helpers ─────────────────────────────────────────────────

def test_json_dumps_sorts_keys() -> None:
    result = BC._json_dumps({"z": 1, "a": 2})
    assert result.index('"a"') < result.index('"z"')


def test_json_dumps_no_spaces() -> None:
    result = BC._json_dumps({"k": "v"})
    assert " " not in result


def test_json_dumps_non_ascii_preserved() -> None:
    result = BC._json_dumps({"msg": "日本語"})
    assert "日本語" in result


def test_sha256_text_length() -> None:
    h = BC._sha256_text("hello")
    assert len(h) == 64
    assert all(c in "0123456789abcdef" for c in h)


def test_sha256_text_deterministic() -> None:
    assert BC._sha256_text("abc") == BC._sha256_text("abc")


def test_sha256_text_different_inputs() -> None:
    assert BC._sha256_text("a") != BC._sha256_text("b")


def test_hex_int_hex_string() -> None:
    assert BC._hex_int("0x1a") == 26


def test_hex_int_plain_hex() -> None:
    assert BC._hex_int("ff") == 255


def test_hex_int_integer_passthrough() -> None:
    assert BC._hex_int(42) == 42


def test_hex_int_none_returns_zero() -> None:
    assert BC._hex_int(None) == 0


# ─── flight_offer pure helpers ───────────────────────────────────────────────

def test_flight_offer_clean_strips_whitespace() -> None:
    assert FO._clean("  test  ") == "test"


def test_flight_offer_clean_none() -> None:
    assert FO._clean(None) == ""


def test_flight_offer_hash8_deterministic() -> None:
    assert FO._hash8("a", "b") == FO._hash8("a", "b")


def test_flight_offer_hash8_varies() -> None:
    assert FO._hash8("x") != FO._hash8("y")


def test_flight_offer_hash8_length() -> None:
    h = FO._hash8("test")
    assert len(h) == 12  # digest_size=6 → 12 hex chars


def test_flight_offer_vertex_id_shape() -> None:
    vid = FO._vertex_id("amadeus", "OFFER-123")
    assert vid.startswith("at://did:web:flight-offer.etzhayyim.com/")
    assert "amadeus-OFFER-123" in vid


def test_flight_offer_watch_vertex_id_shape() -> None:
    vid = FO._watch_vertex_id("TYO", "LAX", "2026-05-01", "USD")
    assert "TYO-LAX-2026-05-01-USD" in vid
    assert vid.startswith("at://did:web:flight-offer.etzhayyim.com/")


def test_parse_source_filter_empty_returns_all() -> None:
    assert FO._parse_source_filter("") == []


def test_parse_source_filter_auto_returns_all() -> None:
    assert FO._parse_source_filter("auto") == []


def test_parse_source_filter_star_returns_all() -> None:
    assert FO._parse_source_filter("*") == []


def test_parse_source_filter_comma_separated() -> None:
    result = FO._parse_source_filter("amadeus,duffel")
    assert result == ["amadeus", "duffel"]


def test_parse_source_filter_single() -> None:
    result = FO._parse_source_filter("kiwi-tequila")
    assert result == ["kiwi-tequila"]


def test_parse_source_filter_trims_spaces() -> None:
    result = FO._parse_source_filter("  amadeus , duffel  ")
    assert result == ["amadeus", "duffel"]


def test_resolve_provider_alias_kiwi(monkeypatch) -> None:
    monkeypatch.setenv("KIWI_API_KEY", "test-key")
    result = FO._resolve_provider("kiwi")
    assert result in ("kiwi-tequila", "stub")


def test_has_credentials_stub_requires_no_keys(monkeypatch) -> None:
    assert FO._has_credentials("stub") is True
