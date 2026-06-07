"""Pure helper tests for ingest/site_common_crawl and ingest/flight_offer primitives.

Covers pure functions with no DB/HTTP/subprocess dependencies:
- site_common_crawl: now_iso / _truthy / _data_dir / _etzhayyim_binary
- flight_offer: _now_iso / _clean / _hash8 / _vertex_id / _stub_search /
                _adapter_stub constants
"""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import site_common_crawl as SCC
from kotodama.ingest import flight_offer as FO


# ─── site_common_crawl — now_iso ─────────────────────────────────────────────

def test_scc_now_iso_returns_string():
    assert isinstance(SCC.now_iso(), str)


def test_scc_now_iso_ends_with_z():
    assert SCC.now_iso().endswith("Z")


def test_scc_now_iso_contains_t():
    assert "T" in SCC.now_iso()


# ─── site_common_crawl — _truthy ─────────────────────────────────────────────

def test_scc_truthy_true_values():
    for val in ["1", "true", "True", "TRUE", "yes", "YES", "on", "ON"]:
        assert SCC._truthy(val) is True


def test_scc_truthy_false_values():
    for val in ["0", "false", "no", "off", "", None, "nope"]:
        assert SCC._truthy(val) is False


def test_scc_truthy_returns_bool():
    assert isinstance(SCC._truthy("1"), bool)


# ─── site_common_crawl — _data_dir ───────────────────────────────────────────

def test_scc_data_dir_with_explicit_path():
    result = SCC._data_dir("/tmp/cc_data")
    assert str(result) == "/tmp/cc_data"


def test_scc_data_dir_returns_path():
    result = SCC._data_dir("/tmp/test")
    assert isinstance(result, Path)


# ─── site_common_crawl — _etzhayyim_binary ────────────────────────────────────────

def test_scc_etzhayyim_binary_returns_string():
    result = SCC._etzhayyim_binary()
    assert isinstance(result, str)


def test_scc_etzhayyim_binary_not_empty():
    result = SCC._etzhayyim_binary()
    assert len(result) > 0


# ─── flight_offer — _now_iso ─────────────────────────────────────────────────

def test_fo_now_iso_returns_string():
    assert isinstance(FO._now_iso(), str)


def test_fo_now_iso_ends_with_z():
    assert FO._now_iso().endswith("Z")


def test_fo_now_iso_contains_t():
    assert "T" in FO._now_iso()


# ─── flight_offer — _clean ───────────────────────────────────────────────────

def test_fo_clean_strips_whitespace():
    assert FO._clean("  hello  ") == "hello"


def test_fo_clean_none_returns_empty():
    assert FO._clean(None) == ""


def test_fo_clean_converts_to_string():
    assert FO._clean(42) == "42"


def test_fo_clean_strips_empty():
    assert FO._clean("") == ""


# ─── flight_offer — _hash8 ────────────────────────────────────────────────────

def test_fo_hash8_returns_string():
    result = FO._hash8("provider", "NRT", "LAX", "2026-06-01")
    assert isinstance(result, str)


def test_fo_hash8_is_deterministic():
    a = FO._hash8("amadeus", "NRT", "LAX")
    b = FO._hash8("amadeus", "NRT", "LAX")
    assert a == b


def test_fo_hash8_differs_by_parts():
    a = FO._hash8("amadeus", "NRT", "LAX")
    b = FO._hash8("amadeus", "NRT", "SFO")
    assert a != b


def test_fo_hash8_is_hex():
    result = FO._hash8("x", "y")
    int(result, 16)  # raises ValueError if not hex


# ─── flight_offer — _vertex_id ────────────────────────────────────────────────

def test_fo_vertex_id_starts_with_at():
    result = FO._vertex_id("amadeus", "offer-001")
    assert result.startswith("at://")


def test_fo_vertex_id_contains_provider():
    result = FO._vertex_id("duffel", "offer-001")
    assert "duffel" in result


def test_fo_vertex_id_contains_offer_id():
    result = FO._vertex_id("amadeus", "offer-001")
    assert "offer-001" in result


# ─── flight_offer — _stub_search ──────────────────────────────────────────────

def test_fo_stub_search_returns_list():
    result = FO._stub_search("NRT", "LAX", "2026-06-01", "JPY")
    assert isinstance(result, list)


def test_fo_stub_search_returns_3_items():
    result = FO._stub_search("NRT", "LAX", "2026-06-01", "JPY")
    assert len(result) == 3


def test_fo_stub_search_has_required_keys():
    result = FO._stub_search("NRT", "LAX", "2026-06-01", "JPY")
    offer = result[0]
    for key in ("offerId", "airline", "totalPrice", "currency", "bookingUrl"):
        assert key in offer


def test_fo_stub_search_correct_currency():
    result = FO._stub_search("TYO", "SFO", "2026-06-01", "USD")
    for offer in result:
        assert offer["currency"] == "USD"
