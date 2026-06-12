"""Tests for pure helper functions in ingest/kakaku.py."""

from __future__ import annotations

import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import kakaku as KK


# ─── _clean ──────────────────────────────────────────────────────────────────

def test_kk_clean_strips_whitespace() -> None:
    assert KK._clean("  hello  ") == "hello"


def test_kk_clean_none_returns_empty() -> None:
    assert KK._clean(None) == ""


def test_kk_clean_integer() -> None:
    assert KK._clean(42) == "42"


# ─── _slug ───────────────────────────────────────────────────────────────────

def test_kk_slug_lowercases() -> None:
    assert KK._slug("HELLO") == "hello"


def test_kk_slug_empty_returns_unknown() -> None:
    assert KK._slug("") == "unknown"


def test_kk_slug_special_chars_become_underscore() -> None:
    result = KK._slug("hello world!")
    assert " " not in result
    assert "!" not in result


def test_kk_slug_max_len() -> None:
    result = KK._slug("a" * 300, max_len=50)
    assert len(result) <= 50


def test_kk_slug_collapses_underscores() -> None:
    result = KK._slug("a__b")
    assert "__" not in result


# ─── _hash_slug ──────────────────────────────────────────────────────────────

def test_kk_hash_slug_default_size() -> None:
    result = KK._hash_slug("a", "b")
    assert len(result) == 16  # size=8 → 16 hex


def test_kk_hash_slug_deterministic() -> None:
    a = KK._hash_slug("x", "y")
    b = KK._hash_slug("x", "y")
    assert a == b


def test_kk_hash_slug_varies() -> None:
    a = KK._hash_slug("a", "b")
    b = KK._hash_slug("a", "c")
    assert a != b


# ─── normalize_domain ────────────────────────────────────────────────────────

def test_kk_normalize_domain_basic() -> None:
    assert KK.normalize_domain("example.com") == "example.com"


def test_kk_normalize_domain_strips_www() -> None:
    assert KK.normalize_domain("https://www.example.com") == "example.com"


def test_kk_normalize_domain_strips_scheme() -> None:
    assert KK.normalize_domain("https://shop.example.com/path") == "shop.example.com"


def test_kk_normalize_domain_empty() -> None:
    assert KK.normalize_domain("") == ""


def test_kk_normalize_domain_lowercases() -> None:
    result = KK.normalize_domain("https://EXAMPLE.COM")
    assert result == "example.com"


# ─── merchant_key ────────────────────────────────────────────────────────────

def test_kk_merchant_key_from_domain() -> None:
    result = KK.merchant_key(domain="amazon.co.jp")
    assert "amazon" in result


def test_kk_merchant_key_from_url() -> None:
    result = KK.merchant_key(product_url="https://www.rakuten.co.jp/item")
    assert "rakuten" in result


def test_kk_merchant_key_from_name_fallback() -> None:
    result = KK.merchant_key(merchant_name="My Shop")
    assert "my" in result


# ─── canonical_gtin14 ────────────────────────────────────────────────────────

def test_kk_canonical_gtin14_pads_short() -> None:
    result = KK.canonical_gtin14(jan="4901234")
    assert len(result) == 14
    assert result.startswith("0")


def test_kk_canonical_gtin14_truncates_long() -> None:
    result = KK.canonical_gtin14(gtin="12345678901234567")
    assert len(result) == 14


def test_kk_canonical_gtin14_empty() -> None:
    assert KK.canonical_gtin14() == ""


def test_kk_canonical_gtin14_strips_non_digits() -> None:
    result = KK.canonical_gtin14(jan="49-01234-56789")
    assert result.isdigit()


# ─── product_key ─────────────────────────────────────────────────────────────

def test_kk_product_key_prefers_jan() -> None:
    key, source = KK.product_key({"jan": "4901234567890", "mpn": "ABC"})
    assert source == "jan"
    assert "jan_" in key


def test_kk_product_key_falls_back_to_gtin() -> None:
    key, source = KK.product_key({"gtin": "14901234567890"})
    assert source == "gtin"


def test_kk_product_key_uses_mpn() -> None:
    key, source = KK.product_key({"mpn": "MODEL-X", "brand": "Sony"})
    assert source == "mpn"


def test_kk_product_key_uses_brand_model() -> None:
    key, source = KK.product_key({"brand": "Sony", "model": "A7"})
    assert source == "brand_model"
    assert "sony" in key
    assert "a7" in key


def test_kk_product_key_falls_back_to_title_hash() -> None:
    key, source = KK.product_key({"name": "Some Product"})
    assert source == "title_hash"
    assert key.startswith("title_")


# ─── _price ──────────────────────────────────────────────────────────────────

def test_kk_price_numeric() -> None:
    assert KK._price(1234.56) == 1234.56


def test_kk_price_integer() -> None:
    assert KK._price(100) == 100.0


def test_kk_price_string_with_commas() -> None:
    assert KK._price("1,234.56") == 1234.56


def test_kk_price_none_returns_default() -> None:
    assert KK._price(None) == 0.0


def test_kk_price_empty_returns_default() -> None:
    assert KK._price("") == 0.0


def test_kk_price_custom_default() -> None:
    assert KK._price(None, default=-1.0) == -1.0


# ─── normalize_product_url ───────────────────────────────────────────────────

def test_kk_normalize_product_url_strips_tracking_params() -> None:
    url = "https://example.com/item/123?ref=abc&utm_source=test"
    result = KK.normalize_product_url(url)
    assert "utm_source" not in result


def test_kk_normalize_product_url_preserves_path() -> None:
    url = "https://example.com/item/123"
    result = KK.normalize_product_url(url)
    assert "item/123" in result


# ─── _update_by_vertex ───────────────────────────────────────────────────────

class _FakeCursor:
    def __init__(self, rowcount: int = 1) -> None:
        self.rowcount = rowcount
        self.last_sql: str = ""
        self.last_params: tuple = ()

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.last_sql = sql
        self.last_params = params


def test_kk_update_by_vertex_calls_execute() -> None:
    cur = _FakeCursor(rowcount=1)
    KK._update_by_vertex(cur, "vertex_kakaku_product", "at://did/col/rkey", {"name": "Widget"})
    assert "UPDATE" in cur.last_sql


def test_kk_update_by_vertex_returns_rowcount() -> None:
    cur = _FakeCursor(rowcount=1)
    result = KK._update_by_vertex(cur, "vertex_kakaku_product", "at://did/col/rkey", {"name": "Widget"})
    assert result == 1


def test_kk_update_by_vertex_rowcount_none_returns_zero() -> None:
    cur = _FakeCursor(rowcount=None)
    result = KK._update_by_vertex(cur, "vertex_kakaku_product", "at://did/col/rkey", {"name": "X"})
    assert result == 0


def test_kk_update_by_vertex_empty_values_returns_zero_no_execute() -> None:
    cur = _FakeCursor(rowcount=1)
    result = KK._update_by_vertex(cur, "vertex_kakaku_product", "at://did/col/rkey", {})
    assert result == 0
    assert cur.last_sql == ""


def test_kk_update_by_vertex_all_none_values_returns_zero() -> None:
    cur = _FakeCursor(rowcount=1)
    result = KK._update_by_vertex(cur, "t", "vid", {"name": None, "price": None})
    assert result == 0


def test_kk_update_by_vertex_skips_vertex_id_key() -> None:
    cur = _FakeCursor(rowcount=1)
    KK._update_by_vertex(cur, "t", "my-vid", {"vertex_id": "should-be-skipped", "name": "X"})
    assert "should-be-skipped" not in str(cur.last_params)


def test_kk_update_by_vertex_includes_vertex_id_in_where() -> None:
    cur = _FakeCursor(rowcount=1)
    KK._update_by_vertex(cur, "t", "my-vid", {"name": "X"})
    assert "my-vid" in cur.last_params


def test_kk_update_by_vertex_table_name_in_sql() -> None:
    cur = _FakeCursor(rowcount=1)
    KK._update_by_vertex(cur, "vertex_kakaku_offer", "vid", {"price": 100.0})
    assert "vertex_kakaku_offer" in cur.last_sql


def test_kk_update_by_vertex_returns_int() -> None:
    cur = _FakeCursor(rowcount=2)
    result = KK._update_by_vertex(cur, "t", "v", {"a": 1})
    assert isinstance(result, int)
