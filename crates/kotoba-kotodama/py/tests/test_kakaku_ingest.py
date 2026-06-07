from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.ingest import kakaku as K


def test_kakaku_resolve_ids_prefers_jan_and_domain() -> None:
    ids = K.resolve_ids(
        {
            "jan": "4901777300443",
            "merchantName": "Yodobashi",
            "domain": "https://www.yodobashi.com/",
            "merchantSku": "4549995501234",
        }
    )

    assert ids["productId"] == "jan_4901777300443"
    assert ids["merchantId"] == "yodobashi_com"
    assert ids["offerId"] == "yodobashi_com:4549995501234"
    assert ids["productDid"] == "did:web:kakaku.etzhayyim.com:product:jan_4901777300443"


def test_normalize_product_url_drops_tracking_params() -> None:
    out = K.normalize_product_url("https://EXAMPLE.com/p/1?utm_source=x&sku=42&gclid=y")
    assert out == "https://example.com/p/1?sku=42"


def test_extract_offer_from_jsonld() -> None:
    html = """
    <html><head><title>Fallback title</title>
    <script type="application/ld+json">
      {"@type":"Product","name":"Acme Camera","offers":{"@type":"Offer","price":"12345","priceCurrency":"JPY","availability":"https://schema.org/InStock"}}
    </script>
    </head></html>
    """
    out = K.extract_offer_from_html(html)

    assert out["name"] == "Acme Camera"
    assert out["price"] == 12345.0
    assert out["currency"] == "JPY"
    assert out["availability"] == "instock"
    assert out["extractionMethod"] == "jsonld"


class _Cursor:
    def __init__(self) -> None:
        self.sqls: list[str] = []
        self.params: list[tuple] = []
        self.rowcount = 1

    def execute(self, sql: str, params: tuple = ()) -> None:
        self.sqls.append(sql)
        self.params.append(params)


class _SyncCursorFactory:
    def __init__(self) -> None:
        self.cursor = _Cursor()

    def __call__(self):
        factory = self

        class _Ctx:
            def __enter__(self):
                return factory.cursor

            def __exit__(self, exc_type, exc, tb):
                return False

        return _Ctx()


# ─── pure helper functions ───────────────────────────────────────────────────

def test_clean_strips_whitespace() -> None:
    assert K._clean("  hello  ") == "hello"


def test_clean_none_returns_empty() -> None:
    assert K._clean(None) == ""


def test_slug_lowercases_and_replaces_special_chars() -> None:
    assert K._slug("Hello World!") == "hello_world"


def test_slug_truncates_at_max_len() -> None:
    assert len(K._slug("a" * 200, max_len=50)) <= 50


def test_slug_unknown_on_empty() -> None:
    assert K._slug("") == "unknown"


def test_hash_slug_is_deterministic() -> None:
    h1 = K._hash_slug("a", "b", "c")
    h2 = K._hash_slug("a", "b", "c")
    assert h1 == h2


def test_hash_slug_varies_with_parts() -> None:
    assert K._hash_slug("a") != K._hash_slug("b")


def test_normalize_domain_strips_www() -> None:
    assert K.normalize_domain("https://www.amazon.co.jp/") == "amazon.co.jp"


def test_normalize_domain_bare_domain() -> None:
    assert K.normalize_domain("yodobashi.com") == "yodobashi.com"


def test_normalize_domain_empty_returns_empty() -> None:
    assert K.normalize_domain("") == ""


def test_merchant_key_uses_domain_slug() -> None:
    result = K.merchant_key(domain="https://shop.example.com/")
    assert result == "shop_example_com"


def test_merchant_key_falls_back_to_name() -> None:
    result = K.merchant_key(merchant_name="My Shop", domain="")
    assert result == "my_shop"


def test_canonical_gtin14_pads_jan_to_14() -> None:
    result = K.canonical_gtin14(jan="4901777300443")
    assert result == "04901777300443"
    assert len(result) == 14


def test_canonical_gtin14_empty_returns_empty() -> None:
    assert K.canonical_gtin14() == ""


def test_canonical_gtin14_strips_non_digits() -> None:
    result = K.canonical_gtin14(jan="490-1777-300443")
    assert result == "04901777300443"


def test_product_key_jan_priority() -> None:
    pid, source = K.product_key({"jan": "1234567890123", "gtin": "9999"})
    assert pid.startswith("jan_")
    assert source == "jan"


def test_product_key_gtin_fallback() -> None:
    pid, source = K.product_key({"gtin": "1234567890123"})
    assert pid.startswith("gtin_")
    assert source == "gtin"


def test_product_key_mpn_fallback() -> None:
    pid, source = K.product_key({"mpn": "M42X", "brand": "Sony"})
    assert source == "mpn"
    assert "m42x" in pid


def test_product_key_brand_model_fallback() -> None:
    pid, source = K.product_key({"brand": "Canon", "model": "EOS R5"})
    assert source == "brand_model"
    assert "canon" in pid


def test_product_key_title_hash_fallback() -> None:
    pid, source = K.product_key({"name": "Some Random Product"})
    assert source == "title_hash"
    assert pid.startswith("title_")


def test_offer_key_native_offer_id() -> None:
    oid, source = K.offer_key({"nativeOfferId": "OFFER-123"}, "merchant_x")
    assert source == "native_offer_id"


def test_offer_key_merchant_sku_fallback() -> None:
    oid, source = K.offer_key({"merchantSku": "SKU-456"}, "merchant_x")
    assert source == "merchant_sku"


def test_offer_key_product_url_fallback() -> None:
    oid, source = K.offer_key({"productUrl": "https://shop.com/p/42"}, "merchant_x")
    assert source == "product_url"
    assert oid.startswith("url_")


def test_normalize_product_url_keeps_stable_params() -> None:
    out = K.normalize_product_url("https://example.com/p/1?sku=42&fbclid=xyz")
    assert "fbclid" not in out
    assert "sku=42" in out


def test_normalize_product_url_lowercases_scheme_and_host() -> None:
    out = K.normalize_product_url("HTTPS://EXAMPLE.COM/path")
    assert out.startswith("https://example.com/")


# ─── upsert_offer_record ─────────────────────────────────────────────────────

def test_upsert_offer_record_writes_current_offer_and_history(monkeypatch) -> None:
    factory = _SyncCursorFactory()
    monkeypatch.setattr(K, "sync_cursor", factory)

    out = K.upsert_offer_record(
        {
            "jan": "4901777300443",
            "name": "Drink",
            "merchantName": "Shop",
            "domain": "shop.example",
            "merchantSku": "sku-1",
            "price": 100,
            "shippingFee": 20,
            "currency": "JPY",
            "productUrl": "https://shop.example/p/sku-1?utm_source=x",
            "observedAt": "2026-04-25T00:00:00Z",
        }
    )

    assert out["status"] == "ok"
    assert out["totalPrice"] == 120.0
    assert out["historyWritten"] is True
    sql_text = "\n".join(factory.cursor.sqls)
    assert "vertex_kakaku_product" in sql_text
    assert "vertex_kakaku_merchant" in sql_text
    assert "vertex_kakaku_offer" in sql_text
    assert "vertex_kakaku_price_history" in sql_text


# ─── task_upsert_offer early-return paths ────────────────────────────────────

def test_upsert_offer_missing_merchant_name_returns_error() -> None:
    result = asyncio.run(K.task_upsert_offer(price=100, currency="JPY"))
    assert result["status"] == "error"
    assert "merchantName" in result["error"]


def test_upsert_offer_missing_price_returns_error() -> None:
    result = asyncio.run(K.task_upsert_offer(merchantName="ShopA", currency="JPY"))
    assert result["status"] == "error"
    assert "price" in result["error"]


def test_upsert_offer_missing_currency_returns_error() -> None:
    result = asyncio.run(K.task_upsert_offer(merchantName="ShopA", price=100))
    assert result["status"] == "error"
    assert "currency" in result["error"]


def test_upsert_offer_error_returns_dict() -> None:
    result = asyncio.run(K.task_upsert_offer())
    assert isinstance(result, dict)
    assert "status" in result


# ─── task_ingest_offer_from_url early-return paths ───────────────────────────

def test_ingest_offer_from_url_missing_product_url_returns_error() -> None:
    result = asyncio.run(K.task_ingest_offer_from_url(merchantName="Shop"))
    assert result["status"] == "error"
    assert "productUrl" in result["error"]


def test_ingest_offer_from_url_missing_merchant_name_returns_error() -> None:
    result = asyncio.run(K.task_ingest_offer_from_url(productUrl="https://example.com/p/1"))
    assert result["status"] == "error"
    assert "merchantName" in result["error"]


def test_ingest_offer_from_url_no_price_in_empty_body_returns_needs_review() -> None:
    result = asyncio.run(K.task_ingest_offer_from_url(
        productUrl="https://example.com/p/1",
        merchantName="Shop",
        fetchedBody="",
    ))
    assert result["status"] == "needs_review"
    assert "price" in result["error"]


def test_ingest_offer_from_url_returns_dict() -> None:
    result = asyncio.run(K.task_ingest_offer_from_url())
    assert isinstance(result, dict)


# ─── task_compare_offers early-return paths ──────────────────────────────────

def test_compare_offers_missing_product_id_returns_error() -> None:
    result = asyncio.run(K.task_compare_offers())
    assert "error" in result
    assert "productId" in result["error"]


def test_compare_offers_empty_product_id_returns_error() -> None:
    result = asyncio.run(K.task_compare_offers(productId=""))
    assert "error" in result


def test_compare_offers_empty_product_id_has_empty_offers() -> None:
    result = asyncio.run(K.task_compare_offers(productId=""))
    assert result.get("offers") == []


def test_compare_offers_product_did_derives_product_id() -> None:
    # productDid is also empty → still triggers error
    result = asyncio.run(K.task_compare_offers(productId="", productDid=""))
    assert "error" in result


def test_compare_offers_whitespace_product_id_returns_error() -> None:
    result = asyncio.run(K.task_compare_offers(productId="   "))
    assert "error" in result


def test_compare_offers_error_result_is_dict() -> None:
    result = asyncio.run(K.task_compare_offers())
    assert isinstance(result, dict)
