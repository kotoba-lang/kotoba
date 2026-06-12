"""Tests for pure helper functions in ingest/flight_offer.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import flight_offer as FO


# ─── _clean ──────────────────────────────────────────────────────────────────

def test_fo_clean_strips_whitespace() -> None:
    assert FO._clean("  HND  ") == "HND"


def test_fo_clean_none_returns_empty() -> None:
    assert FO._clean(None) == ""


def test_fo_clean_integer_converts() -> None:
    assert FO._clean(42) == "42"


# ─── _hash8 ──────────────────────────────────────────────────────────────────

def test_fo_hash8_length() -> None:
    result = FO._hash8("TYO", "LAX", "2026-05-01")
    assert len(result) == 12  # blake2b digest_size=6 → 12 hex chars


def test_fo_hash8_deterministic() -> None:
    a = FO._hash8("TYO", "LAX")
    b = FO._hash8("TYO", "LAX")
    assert a == b


def test_fo_hash8_varies_with_input() -> None:
    a = FO._hash8("TYO", "LAX")
    b = FO._hash8("TYO", "SFO")
    assert a != b


# ─── _vertex_id ──────────────────────────────────────────────────────────────

def test_fo_vertex_id_format() -> None:
    vid = FO._vertex_id("amadeus", "offer-001")
    assert vid.startswith("at://")
    assert "com.etzhayyim.apps.flightOffer.offer" in vid
    assert "amadeus" in vid
    assert "offer-001" in vid


def test_fo_vertex_id_deterministic() -> None:
    a = FO._vertex_id("amadeus", "offer-001")
    b = FO._vertex_id("amadeus", "offer-001")
    assert a == b


def test_fo_vertex_id_varies_with_provider() -> None:
    a = FO._vertex_id("amadeus", "offer-001")
    b = FO._vertex_id("duffel", "offer-001")
    assert a != b


# ─── _resolve_provider ───────────────────────────────────────────────────────

def test_fo_resolve_provider_stub_when_no_creds(monkeypatch) -> None:
    monkeypatch.delenv("AMADEUS_CLIENT_ID", raising=False)
    monkeypatch.delenv("DUFFEL_ACCESS_TOKEN", raising=False)
    result = FO._resolve_provider("")
    assert isinstance(result, str)
    assert len(result) > 0


def test_fo_resolve_provider_explicit_unknown_returns_stub(monkeypatch) -> None:
    monkeypatch.delenv("AMADEUS_CLIENT_ID", raising=False)
    result = FO._resolve_provider("amadeus")
    assert result in ("amadeus", "stub")


def test_fo_resolve_provider_kiwi_alias(monkeypatch) -> None:
    monkeypatch.delenv("KIWI_API_KEY", raising=False)
    monkeypatch.delenv("AMADEUS_CLIENT_ID", raising=False)
    result = FO._resolve_provider("kiwi")
    assert result in ("kiwi-tequila", "stub")


def test_fo_resolve_provider_invalid_returns_stub(monkeypatch) -> None:
    monkeypatch.delenv("AMADEUS_CLIENT_ID", raising=False)
    monkeypatch.delenv("DUFFEL_ACCESS_TOKEN", raising=False)
    result = FO._resolve_provider("nonexistent-provider-xyz")
    assert result == "stub"


# ─── _has_credentials ────────────────────────────────────────────────────────

def test_fo_has_credentials_stub_always_true(monkeypatch) -> None:
    # stub has no required env vars
    assert FO._has_credentials("stub") is True


def test_fo_has_credentials_amadeus_false_when_no_env(monkeypatch) -> None:
    monkeypatch.delenv("AMADEUS_CLIENT_ID", raising=False)
    monkeypatch.delenv("AMADEUS_CLIENT_SECRET", raising=False)
    assert FO._has_credentials("amadeus") is False


def test_fo_has_credentials_amadeus_true_when_env_set(monkeypatch) -> None:
    monkeypatch.setenv("AMADEUS_CLIENT_ID", "test-id")
    monkeypatch.setenv("AMADEUS_CLIENT_SECRET", "test-secret")
    assert FO._has_credentials("amadeus") is True


def test_fo_has_credentials_unknown_source_true() -> None:
    # unknown source has no requirements → True
    assert FO._has_credentials("nonexistent") is True


# ─── _stub_search ─────────────────────────────────────────────────────────────

def test_fo_stub_search_returns_list() -> None:
    result = FO._stub_search("TYO", "LAX", "2026-06-01", "USD")
    assert isinstance(result, list)
    assert len(result) == 3


def test_fo_stub_search_has_required_keys() -> None:
    result = FO._stub_search("HND", "CDG", "2026-07-01", "EUR")
    for offer in result:
        assert "offerId" in offer
        assert "airline" in offer
        assert "totalPrice" in offer
        assert "currency" in offer


def test_fo_stub_search_uses_provided_currency() -> None:
    result = FO._stub_search("NRT", "SYD", "2026-08-01", "JPY")
    for offer in result:
        assert offer["currency"] == "JPY"


def test_fo_stub_search_deterministic() -> None:
    a = FO._stub_search("TYO", "LAX", "2026-06-01", "USD")
    b = FO._stub_search("TYO", "LAX", "2026-06-01", "USD")
    assert [o["offerId"] for o in a] == [o["offerId"] for o in b]


def test_fo_stub_search_prices_positive() -> None:
    result = FO._stub_search("SIN", "LHR", "2026-09-01", "SGD")
    for offer in result:
        assert offer["totalPrice"] > 0
        assert offer["basePrice"] > 0


def test_fo_stub_search_varies_with_route() -> None:
    a = FO._stub_search("TYO", "LAX", "2026-06-01", "USD")
    b = FO._stub_search("TYO", "SFO", "2026-06-01", "USD")
    assert a[0]["offerId"] != b[0]["offerId"]


# ─── _adapter_stub ────────────────────────────────────────────────────────────

def test_fo_adapter_stub_delegates_to_stub_search() -> None:
    result = FO._adapter_stub("TYO", "LAX", "2026-06-01", "", "USD", 10)
    assert isinstance(result, list)
    assert len(result) == 3


def test_fo_adapter_stub_returns_list_of_dicts() -> None:
    result = FO._adapter_stub("HND", "CDG", "2026-07-01", "", "EUR", 5)
    assert all(isinstance(offer, dict) for offer in result)


# ─── _adapter_amadeus / _adapter_duffel / _adapter_kiwi / _adapter_travelpayouts ──

def test_fo_adapter_amadeus_delegates(monkeypatch) -> None:
    captured = {}

    def _mock_amadeus(o, d, od, rd, cur, mo):
        captured["called"] = True
        return [{"offerId": "mock"}]

    monkeypatch.setattr(FO, "_amadeus_search", _mock_amadeus)
    result = FO._adapter_amadeus("TYO", "LAX", "2026-06-01", "", "USD", 3)
    assert captured.get("called") is True
    assert result[0]["offerId"] == "mock"


def test_fo_adapter_duffel_delegates(monkeypatch) -> None:
    captured = {}

    def _mock_duffel(o, d, od, rd, cur, mo):
        captured["called"] = True
        return [{"offerId": "duffel-mock"}]

    monkeypatch.setattr(FO, "_duffel_search", _mock_duffel)
    result = FO._adapter_duffel("TYO", "LAX", "2026-06-01", "", "USD", 3)
    assert captured.get("called") is True


def test_fo_adapter_kiwi_delegates(monkeypatch) -> None:
    captured = {}

    def _mock_kiwi(o, d, od, rd, cur, mo):
        captured["called"] = True
        return []

    monkeypatch.setattr(FO, "_kiwi_search", _mock_kiwi)
    FO._adapter_kiwi("TYO", "LAX", "2026-06-01", "", "USD", 3)
    assert captured.get("called") is True


def test_fo_adapter_travelpayouts_delegates(monkeypatch) -> None:
    captured = {}

    def _mock_tp(o, d, od, rd, cur, mo):
        captured["called"] = True
        return []

    monkeypatch.setattr(FO, "_travelpayouts_search", _mock_tp)
    FO._adapter_travelpayouts("TYO", "LAX", "2026-06-01", "", "USD", 3)
    assert captured.get("called") is True


def test_fo_adapter_amadeus_returns_list(monkeypatch) -> None:
    monkeypatch.setattr(FO, "_amadeus_search", lambda *a: [])
    assert isinstance(FO._adapter_amadeus("T", "L", "2026-01-01", "", "USD", 3), list)


def test_fo_adapter_duffel_returns_list(monkeypatch) -> None:
    monkeypatch.setattr(FO, "_duffel_search", lambda *a: [])
    assert isinstance(FO._adapter_duffel("T", "L", "2026-01-01", "", "USD", 3), list)


# ─── _FakeCursor ──────────────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rowcount: int = 1, rows: list = None) -> None:
        self.rowcount = rowcount
        self._rows = rows or []
        self.last_sql: str = ""
        self.last_params: tuple = ()

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.last_sql = sql
        self.last_params = params

    def fetchall(self) -> list:
        return self._rows


# ─── _insert_offer ────────────────────────────────────────────────────────────

def _sample_offer_row() -> dict:
    return {
        "vertex_id": "at://did:web:test/com.etzhayyim.apps.flightOffer.offer/abc123",
        "offer_id": "abc123",
        "provider": "stub",
        "airline": "NH",
        "flight_number": "NH001",
        "origin_iata": "TYO",
        "destination_iata": "LAX",
        "outbound_date": "2026-06-01",
        "return_date": "",
        "base_price": 100.0,
        "taxes": 10.0,
        "total_price": 110.0,
        "currency": "USD",
        "booking_url": "https://example.com/book",
        "deeplink_url": "https://example.com/deep",
        "observed_at": "2026-06-01T00:00:00Z",
        "source_url": "https://example.com/src",
        "props": "{}",
    }


def test_fo_insert_offer_calls_execute() -> None:
    cur = _FakeCursor(rowcount=1)
    FO._insert_offer(cur, _sample_offer_row())
    assert "INSERT INTO" in cur.last_sql


def test_fo_insert_offer_returns_rowcount() -> None:
    cur = _FakeCursor(rowcount=1)
    result = FO._insert_offer(cur, _sample_offer_row())
    assert result == 1


def test_fo_insert_offer_rowcount_zero() -> None:
    cur = _FakeCursor(rowcount=0)
    result = FO._insert_offer(cur, _sample_offer_row())
    assert result == 0


def test_fo_insert_offer_rowcount_none_returns_zero() -> None:
    cur = _FakeCursor(rowcount=None)
    result = FO._insert_offer(cur, _sample_offer_row())
    assert result == 0


def test_fo_insert_offer_passes_vertex_id() -> None:
    cur = _FakeCursor(rowcount=1)
    row = _sample_offer_row()
    FO._insert_offer(cur, row)
    assert row["vertex_id"] in cur.last_params


def test_fo_insert_offer_returns_int() -> None:
    cur = _FakeCursor(rowcount=1)
    result = FO._insert_offer(cur, _sample_offer_row())
    assert isinstance(result, int)


# ─── _insert_alert ────────────────────────────────────────────────────────────

def _sample_alert() -> dict:
    return {
        "vertex_id": "at://did:web:test/com.etzhayyim.apps.flightOffer.alert/aa-bb-2026-01",
        "origin_iata": "TYO",
        "destination_iata": "LAX",
        "outbound_date": "2026-06-01",
        "currency": "USD",
        "previous_price": 500.0,
        "new_price": 350.0,
        "drop_pct": 30.0,
        "provider": "stub",
        "booking_url": "https://example.com/book",
        "observed_at": "2026-06-01T00:00:00Z",
    }


def test_fo_insert_alert_calls_execute() -> None:
    cur = _FakeCursor(rowcount=1)
    FO._insert_alert(cur, _sample_alert())
    assert "INSERT INTO" in cur.last_sql


def test_fo_insert_alert_returns_rowcount() -> None:
    cur = _FakeCursor(rowcount=1)
    result = FO._insert_alert(cur, _sample_alert())
    assert result == 1


def test_fo_insert_alert_rowcount_none_returns_zero() -> None:
    cur = _FakeCursor(rowcount=None)
    result = FO._insert_alert(cur, _sample_alert())
    assert result == 0


def test_fo_insert_alert_passes_vertex_id() -> None:
    cur = _FakeCursor(rowcount=1)
    alert = _sample_alert()
    FO._insert_alert(cur, alert)
    assert alert["vertex_id"] in cur.last_params


def test_fo_insert_alert_returns_int() -> None:
    cur = _FakeCursor(rowcount=1)
    result = FO._insert_alert(cur, _sample_alert())
    assert isinstance(result, int)


# ─── _select_due_watches ──────────────────────────────────────────────────────

def test_fo_select_due_watches_force_returns_all_active() -> None:
    rows = [("TYO", "LAX", "2026-06-01", "", "USD", 5.0, "stub", 3, None)]
    cur = _FakeCursor(rows=rows)
    result = FO._select_due_watches(cur, limit=10, force=True)
    assert result == rows


def test_fo_select_due_watches_force_true_no_date_filter() -> None:
    cur = _FakeCursor(rows=[])
    FO._select_due_watches(cur, limit=5, force=True)
    assert "next_due_at" not in cur.last_sql


def test_fo_select_due_watches_force_false_has_date_filter() -> None:
    cur = _FakeCursor(rows=[])
    FO._select_due_watches(cur, limit=5, force=False)
    assert "next_due_at" in cur.last_sql


def test_fo_select_due_watches_returns_list() -> None:
    cur = _FakeCursor(rows=[])
    result = FO._select_due_watches(cur, limit=10, force=True)
    assert isinstance(result, list)


def test_fo_select_due_watches_empty_cursor_returns_empty() -> None:
    cur = _FakeCursor(rows=[])
    result = FO._select_due_watches(cur, limit=10, force=True)
    assert result == []


def test_fo_select_due_watches_limit_embedded_in_sql() -> None:
    cur = _FakeCursor(rows=[])
    FO._select_due_watches(cur, limit=7, force=True)
    assert "7" in cur.last_sql


# ─── _do_search early-return (pure path) ─────────────────────────────────────

def test_fo_do_search_missing_origin_returns_error() -> None:
    result = FO._do_search(
        origin="", destination="LAX", outbound_date="2026-06-01",
        return_date="", currency="USD", provider="stub", max_offers=3,
    )
    assert result["status"] == "error"
    assert result["offersWritten"] == 0


def test_fo_do_search_missing_destination_returns_error() -> None:
    result = FO._do_search(
        origin="TYO", destination="", outbound_date="2026-06-01",
        return_date="", currency="USD", provider="stub", max_offers=3,
    )
    assert result["status"] == "error"


def test_fo_do_search_missing_date_returns_error() -> None:
    result = FO._do_search(
        origin="TYO", destination="LAX", outbound_date="",
        return_date="", currency="USD", provider="stub", max_offers=3,
    )
    assert result["status"] == "error"


def test_fo_do_search_error_has_offers_fetched_zero() -> None:
    result = FO._do_search(
        origin="", destination="", outbound_date="",
        return_date="", currency="USD", provider="stub", max_offers=3,
    )
    assert result.get("offersFetched") == 0


# ─── _FakeCursorWithFetchone ───────────────────────────────────────────────────

class _FakeCursorFetchone:
    """Cursor mock that also supports fetchone()."""

    def __init__(self, row=None, rowcount: int = 1) -> None:
        self._row = row
        self.rowcount = rowcount
        self.last_sql: str = ""
        self.last_params: tuple = ()

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.last_sql = sql
        self.last_params = params

    def fetchone(self):
        return self._row

    def fetchall(self) -> list:
        return [self._row] if self._row is not None else []


# ─── _query_cheapest ──────────────────────────────────────────────────────────

def test_fo_query_cheapest_returns_none_on_no_row() -> None:
    cur = _FakeCursorFetchone(row=None)
    result = FO._query_cheapest(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert result is None


def test_fo_query_cheapest_returns_dict_with_row() -> None:
    row = (110.0, "stub", "https://book.example.com", "2026-06-01T00:00:00Z")
    cur = _FakeCursorFetchone(row=row)
    result = FO._query_cheapest(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert result is not None
    assert result["cheapestTotalPrice"] == 110.0
    assert result["cheapestProvider"] == "stub"


def test_fo_query_cheapest_passes_params() -> None:
    cur = _FakeCursorFetchone(row=None)
    FO._query_cheapest(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert "TYO" in str(cur.last_params)
    assert "LAX" in str(cur.last_params)


def test_fo_query_cheapest_null_price_returns_none_price() -> None:
    row = (None, "stub", "https://example.com", "2026-06-01T00:00:00Z")
    cur = _FakeCursorFetchone(row=row)
    result = FO._query_cheapest(cur, "T", "L", "2026-06-01", "USD")
    assert result is not None
    assert result["cheapestTotalPrice"] is None


# ─── _last_alert_price ────────────────────────────────────────────────────────

def test_fo_last_alert_price_returns_none_on_no_row() -> None:
    cur = _FakeCursorFetchone(row=None)
    result = FO._last_alert_price(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert result is None


def test_fo_last_alert_price_returns_float() -> None:
    cur = _FakeCursorFetchone(row=(95.5,))
    result = FO._last_alert_price(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert result == 95.5


def test_fo_last_alert_price_none_value_returns_none() -> None:
    cur = _FakeCursorFetchone(row=(None,))
    result = FO._last_alert_price(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert result is None


def test_fo_last_alert_price_passes_params() -> None:
    cur = _FakeCursorFetchone(row=None)
    FO._last_alert_price(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert "TYO" in str(cur.last_params)


# ─── _mark_watch_polled ───────────────────────────────────────────────────────

def test_fo_mark_watch_polled_calls_update() -> None:
    cur = _FakeCursor(rowcount=1)
    FO._mark_watch_polled(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert "UPDATE" in cur.last_sql


def test_fo_mark_watch_polled_sets_next_due() -> None:
    cur = _FakeCursor(rowcount=1)
    FO._mark_watch_polled(cur, "TYO", "LAX", "2026-06-01", "USD", cadence_minutes=120)
    assert "next_due_at" in cur.last_sql


def test_fo_mark_watch_polled_returns_none() -> None:
    cur = _FakeCursor(rowcount=1)
    result = FO._mark_watch_polled(cur, "TYO", "LAX", "2026-06-01", "USD")
    assert result is None


# ─── _log_source_run ──────────────────────────────────────────────────────────

def test_fo_log_source_run_calls_insert() -> None:
    cur = _FakeCursor(rowcount=1)
    FO._log_source_run(
        cur,
        source_id="stub",
        resolved_source="stub",
        origin="TYO",
        destination="LAX",
        outbound_date="2026-06-01",
        return_date="",
        currency="USD",
        status="ok",
        error_class="",
        error_message="",
        offers_fetched=5,
        offers_written=5,
        latency_ms=100,
        observed_at="2026-06-01T00:00:00Z",
    )
    assert "INSERT INTO" in cur.last_sql


def test_fo_log_source_run_returns_none() -> None:
    cur = _FakeCursor(rowcount=1)
    result = FO._log_source_run(
        cur,
        source_id="stub",
        resolved_source="stub",
        origin="TYO",
        destination="LAX",
        outbound_date="2026-06-01",
        return_date="",
        currency="USD",
        status="ok",
        error_class="",
        error_message="",
        offers_fetched=0,
        offers_written=0,
        latency_ms=0,
        observed_at="2026-06-01T00:00:00Z",
    )
    assert result is None


# ─── _select_active_sources_for_route ─────────────────────────────────────────

def test_fo_select_active_sources_empty_on_no_rows() -> None:
    cur = _FakeCursor(rows=[])
    result = FO._select_active_sources_for_route(cur, "TYO", "LAX")
    assert isinstance(result, list)


def test_fo_select_active_sources_calls_select() -> None:
    cur = _FakeCursor(rows=[])
    FO._select_active_sources_for_route(cur, "TYO", "LAX")
    assert "SELECT" in cur.last_sql


# ─── _parse_source_filter ─────────────────────────────────────────────────────

def test_fo_parse_source_filter_empty_returns_empty() -> None:
    assert FO._parse_source_filter("") == []


def test_fo_parse_source_filter_auto_returns_empty() -> None:
    assert FO._parse_source_filter("auto") == []


def test_fo_parse_source_filter_star_returns_empty() -> None:
    assert FO._parse_source_filter("*") == []


def test_fo_parse_source_filter_all_returns_empty() -> None:
    assert FO._parse_source_filter("all") == []


def test_fo_parse_source_filter_single() -> None:
    assert FO._parse_source_filter("amadeus") == ["amadeus"]


def test_fo_parse_source_filter_multiple() -> None:
    result = FO._parse_source_filter("amadeus,duffel,kiwi")
    assert result == ["amadeus", "duffel", "kiwi"]


def test_fo_parse_source_filter_strips_spaces() -> None:
    result = FO._parse_source_filter("amadeus, duffel")
    assert "amadeus" in result
    assert "duffel" in result
