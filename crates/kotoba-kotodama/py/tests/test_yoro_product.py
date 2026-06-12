"""Smoke tests for yoro_product primitives — pure logic, no network."""

from __future__ import annotations

import json

import pytest

from kotodama.primitives.yoro_product import (
    ALL_RETAILERS,
    ADAPTERS,
    OfferCard,
    _extract_jsonld_products,
    _jsonld_to_offer,
    summarize,
)


def test_all_retailers_have_adapters():
    assert set(ALL_RETAILERS) == set(ADAPTERS.keys())
    assert len(ALL_RETAILERS) == 6


def test_offer_card_pydantic_validation():
    o = OfferCard(retailer="amazon-jp", title="テスト机", url="https://example.com/p/1")
    assert o.currency == "JPY"
    assert o.captured_at  # auto-filled
    assert json.loads(o.model_dump_json())["retailer"] == "amazon-jp"


def test_offer_card_rejects_invalid_url():
    with pytest.raises(Exception):
        OfferCard(retailer="amazon-jp", title="x", url="not-a-url")


def test_jsonld_extraction_finds_products():
    html = """
    <html><head>
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"Product","name":"FlexiSpot E7",
     "brand":{"@type":"Brand","name":"FlexiSpot"},"gtin13":"4571234567890",
     "offers":{"@type":"Offer","price":"55000","priceCurrency":"JPY","availability":"https://schema.org/InStock","url":"https://flexispot.jp/products/e7"},
     "image":["https://cdn.example/e7.jpg"]}
    </script>
    </head><body></body></html>
    """
    products = list(_extract_jsonld_products(html))
    assert len(products) == 1
    offer = _jsonld_to_offer("flexispot-jp", products[0], "https://flexispot.jp/search?q=desk")
    assert offer is not None
    assert offer.title == "FlexiSpot E7"
    assert offer.brand == "FlexiSpot"
    assert offer.gtin == "4571234567890"
    assert offer.price_jpy == 55000
    assert offer.in_stock is True
    assert str(offer.url).startswith("https://flexispot.jp/products/e7")


def test_jsonld_extraction_handles_outofstock():
    html = """
    <script type="application/ld+json">
    {"@type":"Product","name":"Sold out desk",
     "offers":{"@type":"Offer","price":"30000","availability":"https://schema.org/SoldOut"}}
    </script>
    """
    products = list(_extract_jsonld_products(html))
    offer = _jsonld_to_offer("ikea-jp", products[0], "https://www.ikea.com/jp/x")
    assert offer is not None
    assert offer.in_stock is False


def test_summarize_computes_min_max_median():
    offers = [
        OfferCard(retailer="amazon-jp", title="a", url="https://a.example/1", price_jpy=10000),
        OfferCard(retailer="amazon-jp", title="b", url="https://a.example/2", price_jpy=30000),
        OfferCard(retailer="rakuten", title="c", url="https://r.example/3", price_jpy=20000),
    ]
    s = summarize("desk", "office.standing-desk", offers)
    assert s.total_offers == 3
    assert s.offers_by_retailer == {"amazon-jp": 2, "rakuten": 1}
    assert s.min_price_jpy == 10000
    assert s.max_price_jpy == 30000
    assert s.median_price_jpy == 20000
    assert s.retailers == ["amazon-jp", "rakuten"]


def test_summarize_handles_empty():
    s = summarize("desk", None, [])
    assert s.total_offers == 0
    assert s.min_price_jpy is None
    assert s.median_price_jpy is None


def test_summarize_skips_priceless_offers():
    offers = [
        OfferCard(retailer="ikea-jp", title="a", url="https://i.example/1"),
        OfferCard(retailer="ikea-jp", title="b", url="https://i.example/2", price_jpy=15000),
    ]
    s = summarize("desk", None, offers)
    assert s.total_offers == 2
    assert s.min_price_jpy == 15000
    assert s.max_price_jpy == 15000
