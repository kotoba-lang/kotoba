"""Tests for pure helpers in ingest/kakaku.py:
now_iso, today, _clean, _slug, _hash_slug, normalize_domain,
merchant_key, canonical_gtin14, product_key, offer_key, normalize_product_url."""

from __future__ import annotations

import re
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import kakaku as KK


# ─── now_iso / today ─────────────────────────────────────────────────────────

def test_now_iso_format() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z", KK.now_iso())


def test_today_format() -> None:
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", KK.today())


# ─── _clean ──────────────────────────────────────────────────────────────────

def test_clean_strips() -> None:
    assert KK._clean("  hello  ") == "hello"


def test_clean_none_empty() -> None:
    assert KK._clean(None) == ""


def test_clean_int() -> None:
    assert KK._clean(42) == "42"


def test_clean_zero_empty() -> None:
    assert KK._clean(0) == ""


# ─── _slug ───────────────────────────────────────────────────────────────────

def test_slug_lowercases() -> None:
    assert KK._slug("Hello World") == "hello_world"


def test_slug_replaces_specials_with_underscore() -> None:
    result = KK._slug("a@b#c")
    assert "@" not in result
    assert "#" not in result
    assert "_" in result


def test_slug_no_consecutive_underscores() -> None:
    result = KK._slug("a  b")
    assert "__" not in result


def test_slug_max_len() -> None:
    long = "a" * 200
    assert len(KK._slug(long, max_len=10)) <= 10


def test_slug_empty_returns_unknown() -> None:
    assert KK._slug("") == "unknown"


def test_slug_html_entities_unescaped() -> None:
    result = KK._slug("a&amp;b")
    assert "amp" not in result
    assert "a" in result and "b" in result


def test_slug_no_leading_trailing_underscores() -> None:
    result = KK._slug("  hello  ")
    assert not result.startswith("_")
    assert not result.endswith("_")


# ─── _hash_slug ──────────────────────────────────────────────────────────────

def test_hash_slug_deterministic() -> None:
    assert KK._hash_slug("a", "b") == KK._hash_slug("a", "b")


def test_hash_slug_default_size_16_hex() -> None:
    result = KK._hash_slug("hello")
    assert len(result) == 16
    assert re.fullmatch(r"[0-9a-f]+", result)


def test_hash_slug_custom_size() -> None:
    result = KK._hash_slug("x", size=4)
    assert len(result) == 8  # digest_size=4 → 8 hex chars


def test_hash_slug_different_inputs_differ() -> None:
    assert KK._hash_slug("abc") != KK._hash_slug("xyz")


# ─── normalize_domain ────────────────────────────────────────────────────────

def test_normalize_domain_removes_www() -> None:
    assert KK.normalize_domain("www.example.com") == "example.com"


def test_normalize_domain_from_url() -> None:
    assert KK.normalize_domain("https://www.kakaku.com/path?q=1") == "kakaku.com"


def test_normalize_domain_empty() -> None:
    assert KK.normalize_domain("") == ""


def test_normalize_domain_lowercase() -> None:
    assert KK.normalize_domain("AMAZON.CO.JP") == "amazon.co.jp"


def test_normalize_domain_no_scheme() -> None:
    assert KK.normalize_domain("kakaku.com") == "kakaku.com"


def test_normalize_domain_strips_path() -> None:
    result = KK.normalize_domain("https://shop.example.com/products")
    assert result == "shop.example.com"


# ─── merchant_key ────────────────────────────────────────────────────────────

def test_merchant_key_from_domain() -> None:
    result = KK.merchant_key(domain="amazon.co.jp")
    assert result == "amazon_co_jp"


def test_merchant_key_from_product_url() -> None:
    result = KK.merchant_key(product_url="https://kakaku.com/item/123")
    assert "kakaku" in result


def test_merchant_key_from_name_fallback() -> None:
    result = KK.merchant_key(merchant_name="LOHACO Yahoo")
    assert isinstance(result, str)
    assert len(result) > 0


def test_merchant_key_domain_preferred_over_name() -> None:
    result = KK.merchant_key(merchant_name="Anything", domain="example.com")
    assert "example" in result


# ─── canonical_gtin14 ────────────────────────────────────────────────────────

def test_canonical_gtin14_pads_short() -> None:
    result = KK.canonical_gtin14(jan="4901234567890")
    assert len(result) == 14
    assert result.startswith("0")


def test_canonical_gtin14_already_14() -> None:
    result = KK.canonical_gtin14(gtin="04901234567890")
    assert len(result) == 14


def test_canonical_gtin14_strips_non_digits() -> None:
    result = KK.canonical_gtin14(jan="490-1234-5678")
    assert re.fullmatch(r"\d+", result)


def test_canonical_gtin14_empty() -> None:
    assert KK.canonical_gtin14() == ""


def test_canonical_gtin14_too_long_truncates() -> None:
    result = KK.canonical_gtin14(jan="1" * 20)
    assert len(result) == 14


# ─── product_key ─────────────────────────────────────────────────────────────

def test_product_key_jan_priority() -> None:
    key, method = KK.product_key({"jan": "4901234567890", "gtin": "other"})
    assert method == "jan"
    assert "jan_" in key


def test_product_key_gtin_when_no_jan() -> None:
    key, method = KK.product_key({"gtin": "04901234567890"})
    assert method == "gtin"
    assert "gtin_" in key


def test_product_key_mpn() -> None:
    key, method = KK.product_key({"mpn": "MODEL-X1", "brand": "Sony"})
    assert method == "mpn"
    assert "sony" in key or "model" in key.lower()


def test_product_key_brand_model() -> None:
    key, method = KK.product_key({"brand": "Canon", "model": "EOS R5"})
    assert method == "brand_model"
    assert "canon" in key


def test_product_key_title_hash_fallback() -> None:
    key, method = KK.product_key({"name": "Some Product"})
    assert method == "title_hash"
    assert key.startswith("title_")


def test_product_key_returns_two_tuple() -> None:
    result = KK.product_key({"name": "x"})
    assert len(result) == 2


# ─── offer_key ───────────────────────────────────────────────────────────────

def test_offer_key_native_offer_id_priority() -> None:
    key, method = KK.offer_key({"nativeOfferId": "ABC-123"}, "m1")
    assert method == "native_offer_id"


def test_offer_key_merchant_sku() -> None:
    key, method = KK.offer_key({"merchantSku": "SKU-001"}, "m1")
    assert method == "merchant_sku"


def test_offer_key_product_url() -> None:
    key, method = KK.offer_key({"productUrl": "https://shop.example.com/item/1"}, "m1")
    assert method == "product_url"
    assert key.startswith("url_")


def test_offer_key_payload_hash_fallback() -> None:
    key, method = KK.offer_key({}, "m1")
    assert method == "payload_hash"
    assert key.startswith("offer_")


def test_offer_key_deterministic_for_same_input() -> None:
    a, _ = KK.offer_key({"nativeOfferId": "X1"}, "merch1")
    b, _ = KK.offer_key({"nativeOfferId": "X1"}, "merch1")
    assert a == b


# ─── normalize_product_url ───────────────────────────────────────────────────

def test_normalize_product_url_strips_utm() -> None:
    url = "https://example.com/p?id=1&utm_source=google&utm_campaign=sale"
    result = KK.normalize_product_url(url)
    assert "utm_" not in result
    assert "id=1" in result


def test_normalize_product_url_strips_fbclid() -> None:
    url = "https://example.com/p?fbclid=abc123"
    result = KK.normalize_product_url(url)
    assert "fbclid" not in result


def test_normalize_product_url_lowercase_scheme_host() -> None:
    url = "HTTPS://EXAMPLE.COM/product"
    result = KK.normalize_product_url(url)
    assert result.startswith("https://example.com")


def test_normalize_product_url_no_fragment() -> None:
    url = "https://example.com/p#section"
    result = KK.normalize_product_url(url)
    assert "#" not in result


def test_normalize_product_url_no_scheme_returns_cleaned() -> None:
    result = KK.normalize_product_url("  some-path  ")
    assert result == "some-path"
