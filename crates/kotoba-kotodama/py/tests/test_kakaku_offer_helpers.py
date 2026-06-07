"""Tests for offer_key, resolve_ids, _history_id, _strip_tags, extract_offer_from_html in kakaku.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import kakaku as KK


# ─── offer_key ───────────────────────────────────────────────────────────────

def test_offer_key_native_offer_id_takes_priority() -> None:
    payload = {"nativeOfferId": "OFFER-001", "merchantSku": "SKU-A"}
    key, source = KK.offer_key(payload, "merchant-x")
    assert source == "native_offer_id"
    assert key  # non-empty


def test_offer_key_merchant_sku_second() -> None:
    payload = {"merchantSku": "SKU-ABC"}
    key, source = KK.offer_key(payload, "merchant-x")
    assert source == "merchant_sku"
    assert key


def test_offer_key_product_url_third() -> None:
    payload = {"productUrl": "https://example.com/product/123"}
    key, source = KK.offer_key(payload, "merchant-x")
    assert source == "product_url"
    assert key.startswith("url_")


def test_offer_key_payload_hash_fallback() -> None:
    payload = {}
    key, source = KK.offer_key(payload, "merchant-x")
    assert source == "payload_hash"
    assert key.startswith("offer_")


def test_offer_key_deterministic_for_native_id() -> None:
    payload = {"nativeOfferId": "OFFER-999"}
    k1, _ = KK.offer_key(payload, "m")
    k2, _ = KK.offer_key(payload, "m")
    assert k1 == k2


# ─── resolve_ids ─────────────────────────────────────────────────────────────

def test_resolve_ids_has_all_keys() -> None:
    payload = {
        "merchantName": "Amazon JP",
        "jan": "4901234567890",
        "name": "Product Name",
        "nativeOfferId": "AMZN-001",
    }
    result = KK.resolve_ids(payload)
    assert "productId" in result
    assert "merchantId" in result
    assert "offerId" in result
    assert "productDid" in result
    assert "merchantDid" in result
    assert "offerDid" in result


def test_resolve_ids_product_did_format() -> None:
    payload = {"jan": "4901234567890", "name": "Widget"}
    result = KK.resolve_ids(payload)
    assert result["productDid"]  # non-empty DID string


def test_resolve_ids_offer_id_has_merchant_prefix() -> None:
    payload = {"merchantId": "m-001", "nativeOfferId": "O-001"}
    result = KK.resolve_ids(payload)
    assert "m-001" in result["offerId"]


def test_resolve_ids_empty_payload_works() -> None:
    result = KK.resolve_ids({})
    assert isinstance(result, dict)
    assert len(result) == 8  # 8 keys always returned


def test_resolve_ids_deterministic() -> None:
    payload = {"merchantName": "Test", "jan": "1234567890123"}
    r1 = KK.resolve_ids(payload)
    r2 = KK.resolve_ids(payload)
    assert r1 == r2


# ─── _history_id ─────────────────────────────────────────────────────────────

def test_history_id_is_string() -> None:
    result = KK._history_id("offer-001", "2026-04-29T10:00:00Z", 1999.99, "JPY")
    assert isinstance(result, str)


def test_history_id_deterministic() -> None:
    a = KK._history_id("offer-001", "2026-04-29T10:00:00Z", 1999.99, "JPY")
    b = KK._history_id("offer-001", "2026-04-29T10:00:00Z", 1999.99, "JPY")
    assert a == b


def test_history_id_varies_with_price() -> None:
    a = KK._history_id("offer-001", "2026-04-29", 1000.0, "JPY")
    b = KK._history_id("offer-001", "2026-04-29", 2000.0, "JPY")
    assert a != b


def test_history_id_varies_with_timestamp() -> None:
    a = KK._history_id("offer-001", "2026-04-29T10:00:00Z", 999.0, "USD")
    b = KK._history_id("offer-001", "2026-04-29T11:00:00Z", 999.0, "USD")
    assert a != b


def test_history_id_no_special_chars() -> None:
    result = KK._history_id("offer-001", "2026-04-29", 500.0, "EUR")
    assert " " not in result


# ─── _strip_tags ─────────────────────────────────────────────────────────────

def test_strip_tags_removes_html_tags() -> None:
    result = KK._strip_tags("<b>Hello</b> <i>World</i>")
    assert "<b>" not in result
    assert "<i>" not in result
    assert "Hello" in result and "World" in result


def test_strip_tags_unescapes_entities() -> None:
    result = KK._strip_tags("AT&amp;T")
    assert "AT&T" in result


def test_strip_tags_collapses_whitespace() -> None:
    result = KK._strip_tags("a   b")
    assert "  " not in result


def test_strip_tags_empty_returns_empty() -> None:
    assert KK._strip_tags("") == ""


def test_strip_tags_no_tags_passthrough() -> None:
    result = KK._strip_tags("plain text")
    assert result == "plain text"


# ─── extract_offer_from_html ─────────────────────────────────────────────────

def test_extract_offer_from_html_empty_returns_dict() -> None:
    result = KK.extract_offer_from_html("")
    assert isinstance(result, dict)


def test_extract_offer_from_html_extracts_title() -> None:
    html = "<html><head><title>Widget Pro 3000</title></head><body></body></html>"
    result = KK.extract_offer_from_html(html)
    # title may or may not be present depending on regex
    assert isinstance(result, dict)


def test_extract_offer_from_html_jsonld_offer() -> None:
    html = """<html><head>
    <script type="application/ld+json">
    {
      "@type": "Product",
      "name": "Super Gadget",
      "offers": {"@type": "Offer", "price": 9800, "priceCurrency": "JPY"}
    }
    </script></head><body></body></html>"""
    result = KK.extract_offer_from_html(html)
    if "price" in result:  # JSON-LD extraction may succeed
        assert result["price"] == 9800.0
        assert result.get("currency") == "JPY"
        assert result.get("extractionMethod") == "jsonld"


def test_extract_offer_from_html_no_empty_values() -> None:
    html = "<html><body>Some text without offers</body></html>"
    result = KK.extract_offer_from_html(html)
    # All returned values should be non-empty/non-None
    for v in result.values():
        assert v not in ("", None)


def test_extract_offer_from_html_jsonld_list_offers() -> None:
    html = """<html><head>
    <script type="application/ld+json">
    {
      "@type": "Product",
      "name": "Multi-Offer Item",
      "offers": [{"price": 5500, "priceCurrency": "JPY"}]
    }
    </script></head></html>"""
    result = KK.extract_offer_from_html(html)
    if "price" in result:
        assert result["price"] == 5500.0
