"""Pure-path tests for mangaka and kakaku task functions.

All tested via early-return error paths requiring no DB/HTTP/LLM.

Covers:
- primitives/mangaka.py: all 5 tasks — empty/None script → error dict
- ingest/kakaku.py: task_upsert_offer (no merchantName), task_ingest_offer_from_url
  (no productUrl), task_compare_offers (no productId)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_py_src = Path(__file__).resolve().parents[1] / "src"
if str(_py_src) not in sys.path:
    sys.path.insert(0, str(_py_src))

from kotodama.primitives import mangaka as MG  # noqa: E402
from kotodama.ingest import kakaku as KK  # noqa: E402


# ══════════════════════════════════════════════════════════════════════════════
# mangaka — all tasks have early-return on empty/None inputs
# ══════════════════════════════════════════════════════════════════════════════

def test_mangaka_batch_render_no_script_returns_dict() -> None:
    result = asyncio.run(MG.task_batch_render(script=None))
    assert isinstance(result, dict)


def test_mangaka_batch_render_no_script_status_error() -> None:
    result = asyncio.run(MG.task_batch_render(script=None))
    assert result["status"] == "error"


def test_mangaka_batch_render_no_script_has_error() -> None:
    result = asyncio.run(MG.task_batch_render(script=None))
    assert "error" in result


def test_mangaka_batch_overlay_no_script_returns_dict() -> None:
    result = asyncio.run(MG.task_batch_overlay(script=None, panelBlobKeys=None))
    assert isinstance(result, dict)


def test_mangaka_batch_overlay_no_script_status_error() -> None:
    result = asyncio.run(MG.task_batch_overlay(script=None, panelBlobKeys=None))
    assert result["status"] == "error"


def test_mangaka_batch_overlay_no_script_has_error() -> None:
    result = asyncio.run(MG.task_batch_overlay(script=None))
    assert "error" in result


def test_mangaka_batch_compose_no_script_returns_dict() -> None:
    result = asyncio.run(MG.task_batch_compose(script=None, overlayBlobKeys=None))
    assert isinstance(result, dict)


def test_mangaka_batch_compose_no_script_status_error() -> None:
    result = asyncio.run(MG.task_batch_compose(script=None))
    assert result["status"] == "error"


def test_mangaka_batch_insert_pages_no_script_returns_dict() -> None:
    result = asyncio.run(MG.task_batch_insert_pages(script=None, pageBlobKeys=None))
    assert isinstance(result, dict)


def test_mangaka_batch_insert_pages_no_script_status_error() -> None:
    result = asyncio.run(MG.task_batch_insert_pages(script=None))
    assert result["status"] == "error"


def test_mangaka_post_publish_no_work_uri_returns_dict() -> None:
    result = asyncio.run(MG.task_post_publish(workUri="", pageBlobKeys=None))
    assert isinstance(result, dict)


def test_mangaka_post_publish_no_work_uri_status_error() -> None:
    result = asyncio.run(MG.task_post_publish())
    assert result["status"] == "error"


def test_mangaka_post_publish_no_work_uri_has_error() -> None:
    result = asyncio.run(MG.task_post_publish(workUri=""))
    assert "error" in result


# ══════════════════════════════════════════════════════════════════════════════
# kakaku — pure early-return error paths (no DB call)
# ══════════════════════════════════════════════════════════════════════════════

def test_kakaku_upsert_offer_no_merchant_name_returns_dict() -> None:
    result = asyncio.run(KK.task_upsert_offer(merchantName="", price=100.0, currency="JPY"))
    assert isinstance(result, dict)


def test_kakaku_upsert_offer_no_merchant_name_status_error() -> None:
    result = asyncio.run(KK.task_upsert_offer(merchantName=""))
    assert result["status"] == "error"


def test_kakaku_upsert_offer_no_merchant_name_has_error() -> None:
    result = asyncio.run(KK.task_upsert_offer())
    assert "error" in result


def test_kakaku_upsert_offer_no_price_returns_error() -> None:
    result = asyncio.run(KK.task_upsert_offer(merchantName="TestMerchant", price=None, currency="JPY"))
    assert result["status"] == "error"
    assert "price" in result["error"]


def test_kakaku_upsert_offer_no_currency_returns_error() -> None:
    result = asyncio.run(KK.task_upsert_offer(merchantName="TestMerchant", price=100.0, currency=""))
    assert result["status"] == "error"
    assert "currency" in result["error"]


def test_kakaku_ingest_offer_no_url_returns_dict() -> None:
    result = asyncio.run(KK.task_ingest_offer_from_url(productUrl=""))
    assert isinstance(result, dict)


def test_kakaku_ingest_offer_no_url_status_error() -> None:
    result = asyncio.run(KK.task_ingest_offer_from_url(productUrl=""))
    assert result["status"] == "error"


def test_kakaku_ingest_offer_no_url_has_error() -> None:
    result = asyncio.run(KK.task_ingest_offer_from_url())
    assert "error" in result


def test_kakaku_ingest_offer_no_merchant_returns_error() -> None:
    result = asyncio.run(KK.task_ingest_offer_from_url(productUrl="https://example.com/product", merchantName=""))
    assert result["status"] == "error"
    assert "merchantName" in result["error"]


def test_kakaku_compare_offers_no_product_id_returns_dict() -> None:
    result = asyncio.run(KK.task_compare_offers(productId=""))
    assert isinstance(result, dict)


def test_kakaku_compare_offers_no_product_id_has_error() -> None:
    result = asyncio.run(KK.task_compare_offers(productId=""))
    assert "error" in result


def test_kakaku_compare_offers_no_product_id_empty_offers() -> None:
    result = asyncio.run(KK.task_compare_offers())
    assert result.get("offers") == []


def test_kakaku_compare_offers_no_product_id_returns_empty_id() -> None:
    result = asyncio.run(KK.task_compare_offers(productId=""))
    assert result.get("productId") == ""
