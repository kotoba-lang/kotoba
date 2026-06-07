"""Tests for pure helpers in ingest/flight_offer.py:
_clean, _hash8, _vertex_id, _watch_vertex_id, _has_credentials, _resolve_provider."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest.mock import patch

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import flight_offer as FO


# ─── _clean ──────────────────────────────────────────────────────────────────

def test_clean_strips_whitespace() -> None:
    assert FO._clean("  hello  ") == "hello"


def test_clean_none_returns_empty() -> None:
    assert FO._clean(None) == ""


def test_clean_zero_returns_empty() -> None:
    assert FO._clean(0) == ""


def test_clean_int_converts_to_str() -> None:
    assert FO._clean(42) == "42"


def test_clean_already_clean() -> None:
    assert FO._clean("TYO") == "TYO"


def test_clean_empty_string() -> None:
    assert FO._clean("") == ""


# ─── _hash8 ──────────────────────────────────────────────────────────────────

def test_hash8_returns_string() -> None:
    result = FO._hash8("TYO", "NRT", "2026-05-01")
    assert isinstance(result, str)


def test_hash8_returns_12_hex_chars() -> None:
    result = FO._hash8("TYO", "NRT")
    assert len(result) == 12
    assert all(c in "0123456789abcdef" for c in result)


def test_hash8_deterministic() -> None:
    a = FO._hash8("TYO", "NRT", "2026-05-01")
    b = FO._hash8("TYO", "NRT", "2026-05-01")
    assert a == b


def test_hash8_different_inputs_differ() -> None:
    a = FO._hash8("TYO", "NRT")
    b = FO._hash8("NRT", "TYO")
    assert a != b


def test_hash8_single_part() -> None:
    result = FO._hash8("only")
    assert len(result) == 12


def test_hash8_none_parts_included() -> None:
    a = FO._hash8(None, "NRT")
    b = FO._hash8("", "NRT")
    assert a == b


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_vertex_id_starts_with_at() -> None:
    result = FO._vertex_id("amadeus", "abc123")
    assert result.startswith("at://")


def test_vertex_id_contains_flight_offer_did() -> None:
    result = FO._vertex_id("amadeus", "abc123")
    assert FO.FLIGHT_OFFER_DID in result


def test_vertex_id_contains_provider() -> None:
    result = FO._vertex_id("amadeus", "abc123")
    assert "amadeus" in result


def test_vertex_id_contains_offer_id() -> None:
    result = FO._vertex_id("stub", "xyz-99")
    assert "xyz-99" in result


def test_vertex_id_format() -> None:
    result = FO._vertex_id("stub", "offer-001")
    assert result == f"at://{FO.FLIGHT_OFFER_DID}/com.etzhayyim.apps.flightOffer.offer/stub-offer-001"


# ─── _watch_vertex_id ────────────────────────────────────────────────────────

def test_watch_vertex_id_starts_with_at() -> None:
    result = FO._watch_vertex_id("TYO", "NRT", "2026-05-01", "JPY")
    assert result.startswith("at://")


def test_watch_vertex_id_contains_origin_destination() -> None:
    result = FO._watch_vertex_id("TYO", "NRT", "2026-05-01", "JPY")
    assert "TYO" in result
    assert "NRT" in result


def test_watch_vertex_id_contains_date_prefix() -> None:
    result = FO._watch_vertex_id("TYO", "NRT", "2026-05-01T00:00:00Z", "JPY")
    assert "2026-05-01" in result


def test_watch_vertex_id_contains_currency() -> None:
    result = FO._watch_vertex_id("TYO", "NRT", "2026-05-01", "USD")
    assert "USD" in result


def test_watch_vertex_id_date_trimmed_to_10() -> None:
    long_date = "2026-05-01T12:34:56Z"
    result = FO._watch_vertex_id("TYO", "NRT", long_date, "JPY")
    assert "T12:34:56Z" not in result
    assert "2026-05-01" in result


def test_watch_vertex_id_deterministic() -> None:
    a = FO._watch_vertex_id("TYO", "NRT", "2026-05-01", "JPY")
    b = FO._watch_vertex_id("TYO", "NRT", "2026-05-01", "JPY")
    assert a == b


# ─── _has_credentials ────────────────────────────────────────────────────────

def test_has_credentials_stub_always_true() -> None:
    assert FO._has_credentials("stub") is True


def test_has_credentials_unknown_source_true() -> None:
    assert FO._has_credentials("nonexistent-source") is True


def test_has_credentials_amadeus_false_when_env_missing() -> None:
    with patch.dict(os.environ, {}, clear=False):
        env_copy = os.environ.copy()
        env_copy.pop("AMADEUS_CLIENT_ID", None)
        env_copy.pop("AMADEUS_CLIENT_SECRET", None)
        with patch.dict(os.environ, env_copy, clear=True):
            assert FO._has_credentials("amadeus") is False


def test_has_credentials_amadeus_true_when_env_set() -> None:
    with patch.dict(os.environ, {
        "AMADEUS_CLIENT_ID": "test_id",
        "AMADEUS_CLIENT_SECRET": "test_secret",
    }):
        assert FO._has_credentials("amadeus") is True


def test_has_credentials_duffel_false_when_env_missing() -> None:
    env_copy = {k: v for k, v in os.environ.items() if k != "DUFFEL_API_KEY"}
    with patch.dict(os.environ, env_copy, clear=True):
        assert FO._has_credentials("duffel") is False


def test_has_credentials_duffel_true_when_env_set() -> None:
    with patch.dict(os.environ, {"DUFFEL_API_KEY": "duffel_test_key"}):
        assert FO._has_credentials("duffel") is True


# ─── _resolve_provider ───────────────────────────────────────────────────────

def test_resolve_provider_stub_always_available() -> None:
    result = FO._resolve_provider("stub")
    assert result == "stub"


def test_resolve_provider_kiwi_alias() -> None:
    with patch.dict(os.environ, {"KIWI_TEQUILA_API_KEY": "test_key"}):
        result = FO._resolve_provider("kiwi")
        assert result == "kiwi-tequila"


def test_resolve_provider_travelpayouts_alias() -> None:
    with patch.dict(os.environ, {"TRAVELPAYOUTS_TOKEN": "test_token"}):
        result = FO._resolve_provider("travelpayouts")
        assert result == "travelpayouts-aviasales"


def test_resolve_provider_unknown_with_no_creds_returns_stub() -> None:
    env_no_creds = {
        k: v for k, v in os.environ.items()
        if k not in ("AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET",
                     "DUFFEL_API_KEY", "KIWI_TEQUILA_API_KEY", "TRAVELPAYOUTS_TOKEN")
    }
    with patch.dict(os.environ, env_no_creds, clear=True):
        result = FO._resolve_provider("unknown-provider")
        assert result == "stub"


def test_resolve_provider_empty_string_falls_back() -> None:
    env_no_creds = {
        k: v for k, v in os.environ.items()
        if k not in ("AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET",
                     "DUFFEL_API_KEY", "KIWI_TEQUILA_API_KEY", "TRAVELPAYOUTS_TOKEN")
    }
    with patch.dict(os.environ, env_no_creds, clear=True):
        result = FO._resolve_provider("")
        assert result == "stub"


def test_resolve_provider_amadeus_when_creds_present() -> None:
    with patch.dict(os.environ, {
        "AMADEUS_CLIENT_ID": "id",
        "AMADEUS_CLIENT_SECRET": "secret",
    }):
        result = FO._resolve_provider("amadeus")
        assert result == "amadeus"


def test_resolve_provider_strips_whitespace() -> None:
    result = FO._resolve_provider("  stub  ")
    assert result == "stub"


def test_resolve_provider_case_insensitive() -> None:
    result = FO._resolve_provider("STUB")
    assert result == "stub"


def test_resolve_provider_missing_creds_falls_to_stub() -> None:
    env_no_creds = {
        k: v for k, v in os.environ.items()
        if k not in ("AMADEUS_CLIENT_ID", "AMADEUS_CLIENT_SECRET",
                     "DUFFEL_API_KEY", "KIWI_TEQUILA_API_KEY", "TRAVELPAYOUTS_TOKEN")
    }
    with patch.dict(os.environ, env_no_creds, clear=True):
        result = FO._resolve_provider("amadeus")
        assert result == "stub"
