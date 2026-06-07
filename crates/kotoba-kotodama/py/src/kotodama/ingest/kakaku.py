"""Kakaku price comparison ingest tasks.

This module is the source-specific Python layer behind
`com.etzhayyim.apps.kakaku.*` BPMN/XRPC bindings. It keeps deterministic entity
resolution in Python and writes the existing `vertex_kakaku_*` graph tables.
"""

from __future__ import annotations

import asyncio
import hashlib
import html
import json
import os
import re
import subprocess
import urllib.parse
from datetime import datetime, timezone
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client

KAKAKU_DID = "did:web:kakaku.etzhayyim.com"
PRODUCT_COLLECTION = "com.etzhayyim.apps.kakaku.product"
MERCHANT_COLLECTION = "com.etzhayyim.apps.kakaku.merchant"
OFFER_COLLECTION = "com.etzhayyim.apps.kakaku.offer"
PRICE_HISTORY_COLLECTION = "com.etzhayyim.apps.kakaku.priceHistory"
MATCH_COLLECTION = "com.etzhayyim.apps.kakaku.matchCandidate"


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _clean(value: Any) -> str:
    return str(value or "").strip()


def _slug(value: str, *, max_len: int = 180) -> str:
    value = html.unescape(value or "").lower()
    out: list[str] = []
    for ch in value:
        if "a" <= ch <= "z" or "0" <= ch <= "9":
            out.append(ch)
        elif ch.isalnum():
            out.append(ch)
        else:
            out.append("_")
    slug = "_".join(part for part in "".join(out).split("_") if part)
    return (slug[:max_len] or "unknown").strip("_") or "unknown"


def _hash_slug(*parts: Any, size: int = 8) -> str:
    payload = "|".join(_clean(p) for p in parts)
    return hashlib.blake2b(payload.encode("utf-8"), digest_size=size).hexdigest()


def normalize_domain(domain_or_url: str) -> str:
    value = _clean(domain_or_url).lower()
    if not value:
        return ""
    if "://" not in value:
        value = "https://" + value
    host = urllib.parse.urlparse(value).hostname or ""
    host = host.lower().strip(".")
    if host.startswith("www."):
        host = host[4:]
    return host


def merchant_key(merchant_name: str = "", domain: str = "", product_url: str = "") -> str:
    host = normalize_domain(domain or product_url)
    if host:
        return _slug(host.replace(".", "_"))
    return _slug(merchant_name)


def canonical_gtin14(jan: str = "", gtin: str = "") -> str:
    raw = re.sub(r"\D+", "", gtin or jan or "")
    if not raw:
        return ""
    if len(raw) <= 14:
        return raw.zfill(14)
    return raw[-14:]


def product_key(payload: dict[str, Any]) -> tuple[str, str]:
    jan = re.sub(r"\D+", "", _clean(payload.get("jan")))
    gtin = re.sub(r"\D+", "", _clean(payload.get("gtin")))
    mpn = _clean(payload.get("mpn"))
    brand = _clean(payload.get("brand"))
    model = _clean(payload.get("model"))
    name = _clean(payload.get("name"))
    if jan:
        return f"jan_{jan}", "jan"
    if gtin:
        return f"gtin_{gtin}", "gtin"
    if mpn:
        prefix = _slug(brand) if brand else "mpn"
        return f"{prefix}_{_slug(mpn)}", "mpn"
    if brand and model:
        return f"{_slug(brand)}_{_slug(model)}", "brand_model"
    source = name or _clean(payload.get("productUrl")) or json.dumps(payload, sort_keys=True)
    return f"title_{_hash_slug(source, size=8)}", "title_hash"


def offer_key(payload: dict[str, Any], merchant_id: str) -> tuple[str, str]:
    native_offer_id = _clean(payload.get("nativeOfferId"))
    merchant_sku = _clean(payload.get("merchantSku"))
    product_url = _clean(payload.get("productUrl"))
    if native_offer_id:
        return _slug(native_offer_id), "native_offer_id"
    if merchant_sku:
        return _slug(merchant_sku), "merchant_sku"
    if product_url:
        normalized = normalize_product_url(product_url)
        return f"url_{_hash_slug(merchant_id, normalized, size=8)}", "product_url"
    return f"offer_{_hash_slug(merchant_id, payload, size=8)}", "payload_hash"


def normalize_product_url(url: str) -> str:
    parsed = urllib.parse.urlparse(_clean(url))
    if not parsed.scheme or not parsed.netloc:
        return _clean(url)
    query = urllib.parse.parse_qsl(parsed.query, keep_blank_values=False)
    stable = [
        (k, v)
        for k, v in query
        if not k.lower().startswith(("utm_", "fbclid", "gclid", "yclid", "mc_"))
    ]
    return urllib.parse.urlunparse(
        (
            parsed.scheme.lower(),
            parsed.netloc.lower(),
            parsed.path,
            "",
            urllib.parse.urlencode(stable),
            "",
        )
    )


def resolve_ids(payload: dict[str, Any]) -> dict[str, str]:
    m_key = merchant_key(
        _clean(payload.get("merchantName") or payload.get("merchantId")),
        _clean(payload.get("domain")),
        _clean(payload.get("productUrl")),
    )
    p_key, p_source = product_key(payload)
    product_id = _clean(payload.get("productId")) or p_key
    merchant_id = _clean(payload.get("merchantId")) or m_key
    o_key, o_source = offer_key(payload, merchant_id)
    offer_id = f"{merchant_id}:{o_key}"
    return {
        "productId": product_id,
        "productKeySource": p_source,
        "productDid": f"{KAKAKU_DID}:product:{product_id}",
        "merchantId": merchant_id,
        "merchantDid": f"{KAKAKU_DID}:merchant:{merchant_id}",
        "offerId": offer_id,
        "offerKeySource": o_source,
        "offerDid": f"{KAKAKU_DID}:offer:{merchant_id}:{o_key}",
    }


def _price(value: Any, default: float = 0.0) -> float:
    if value is None or value == "":
        return default
    if isinstance(value, (int, float)):
        return float(value)
    cleaned = re.sub(r"[^0-9.\-]+", "", str(value))
    if cleaned in {"", ".", "-", "-."}:
        return default
    return float(cleaned)


def _history_id(offer_id: str, observed_at: str, total_price: float, currency: str) -> str:
    return f"{_slug(offer_id)}_{_hash_slug(observed_at, total_price, currency, size=6)}"











def upsert_offer_record(payload: dict[str, Any]) -> dict[str, Any]:
    ids = resolve_ids(payload)
    observed_at = _clean(payload.get("observedAt")) or now_iso()
    currency = (_clean(payload.get("currency")) or "JPY").upper()
    price = _price(payload.get("price"))
    shipping_fee = _price(payload.get("shippingFee"), 0.0)
    total_price = price + shipping_fee
    availability = _clean(payload.get("availability")) or "unknown"
    canonical = canonical_gtin14(_clean(payload.get("jan")), _clean(payload.get("gtin")))
    product_url = normalize_product_url(_clean(payload.get("productUrl")))
    now = now_iso()
    date = today()

    product_vid = f"at://{KAKAKU_DID}/{PRODUCT_COLLECTION}/{ids['productId']}"
    merchant_vid = f"at://{KAKAKU_DID}/{MERCHANT_COLLECTION}/{ids['merchantId']}"
    offer_vid = f"at://{KAKAKU_DID}/{OFFER_COLLECTION}/{_slug(ids['offerId'])}"
    history_id = _history_id(ids["offerId"], observed_at, total_price, currency)
    history_vid = f"at://{KAKAKU_DID}/{PRICE_HISTORY_COLLECTION}/{history_id}"

    product_values = {
        "vertex_id": product_vid,
        "_seq": None,
        "created_date": date,
        "sensitivity_ord": 1,
        "owner_did": KAKAKU_DID,
        "product_id": ids["productId"],
        "did": ids["productDid"],
        "name": _clean(payload.get("name")) or None,
        "brand": _clean(payload.get("brand")) or None,
        "model": _clean(payload.get("model")) or None,
        "jan": _clean(payload.get("jan")) or None,
        "gtin": _clean(payload.get("gtin")) or None,
        "mpn": _clean(payload.get("mpn")) or None,
        "pack_size": _clean(payload.get("packSize")) or None,
        "category": _clean(payload.get("category")) or None,
        "global_product_id": _clean(payload.get("globalProductId")) or canonical or None,
        "global_product_did": _clean(payload.get("globalProductDid")) or None,
        "canonical_gtin14": canonical or None,
        "status": "active",
        "repo": KAKAKU_DID,
        "collection": PRODUCT_COLLECTION,
        "created_at": now,
        "updated_at": now,
    }
    merchant_values = {
        "vertex_id": merchant_vid,
        "_seq": None,
        "created_date": date,
        "sensitivity_ord": 1,
        "owner_did": KAKAKU_DID,
        "merchant_id": ids["merchantId"],
        "did": ids["merchantDid"],
        "name": _clean(payload.get("merchantName")) or ids["merchantId"],
        "domain": normalize_domain(_clean(payload.get("domain")) or product_url) or None,
        "base_currency": currency,
        "shipping_policy": None,
        "reputation_score": None,
        "selector_profile": _clean(payload.get("selectorProfile")) or None,
        "selector_version": int(payload["selectorVersion"]) if payload.get("selectorVersion") else None,
        "selector_config": None,
        "selector_rollout": float(payload["selectorRollout"]) if payload.get("selectorRollout") else None,
        "active_revision_id": _clean(payload.get("selectedRevisionId")) or None,
        "status": "active",
        "repo": KAKAKU_DID,
        "collection": MERCHANT_COLLECTION,
        "created_at": now,
        "updated_at": now,
    }
    offer_values = {
        "vertex_id": offer_vid,
        "_seq": None,
        "created_date": date,
        "sensitivity_ord": 1,
        "owner_did": KAKAKU_DID,
        "offer_id": ids["offerId"],
        "did": ids["offerDid"],
        "product_id": ids["productId"],
        "product_did": ids["productDid"],
        "merchant_id": ids["merchantId"],
        "merchant_did": ids["merchantDid"],
        "merchant_sku": _clean(payload.get("merchantSku")) or None,
        "native_offer_id": _clean(payload.get("nativeOfferId")) or None,
        "price": price,
        "shipping_fee": shipping_fee,
        "total_price": total_price,
        "currency": currency,
        "availability": availability,
        "delivery_eta": _clean(payload.get("deliveryEta")) or None,
        "product_url": product_url or None,
        "observed_at": observed_at,
        "extraction_method": _clean(payload.get("extractionMethod")) or "direct",
        "status": "active",
        "repo": KAKAKU_DID,
        "collection": OFFER_COLLECTION,
        "updated_at": now,
    }
    history_values = {
        "vertex_id": history_vid,
        "_seq": None,
        "created_date": date,
        "sensitivity_ord": 1,
        "owner_did": KAKAKU_DID,
        "history_id": history_id,
        "did": f"{KAKAKU_DID}:priceHistory:{history_id}",
        "product_id": ids["productId"],
        "merchant_id": ids["merchantId"],
        "offer_id": ids["offerId"],
        "price": price,
        "shipping_fee": shipping_fee,
        "total_price": total_price,
        "currency": currency,
        "availability": availability,
        "source_url": product_url or None,
        "observed_at": observed_at,
        "status": "active",
        "repo": KAKAKU_DID,
        "collection": PRICE_HISTORY_COLLECTION,
        "created_at": now,
    }

    client = get_kotoba_client()
    writes = 0

    client.insert_row("vertex_kakaku_product", product_values)
    # The 'insert_row' method performs an upsert, so explicit updates are not needed.
    writes += 1

    client.insert_row("vertex_kakaku_merchant", merchant_values)
    # The 'insert_row' method performs an upsert, so explicit updates are not needed.
    writes += 1

    client.insert_row("vertex_kakaku_offer", offer_values)
    # The 'insert_row' method performs an upsert, so explicit updates are not needed.
    writes += 1

    client.insert_row("vertex_kakaku_price_history", history_values)
    history_written = 1
    writes += history_written

    match_created = 0
    if not canonical and ids["productKeySource"] == "title_hash":
        candidate_id = f"{ids['merchantId']}:{_clean(payload.get('merchantSku')) or _hash_slug(product_url or ids['offerId'], size=6)}"
        candidate_vid = f"at://{KAKAKU_DID}/{MATCH_COLLECTION}/{_slug(candidate_id)}"
        client.insert_row(
            "vertex_kakaku_match_candidate",
            {
                "vertex_id": candidate_vid,
                "_seq": None,
                "created_date": date,
                "sensitivity_ord": 1,
                "owner_did": KAKAKU_DID,
                "candidate_id": candidate_id,
                "did": f"{KAKAKU_DID}:match:{_slug(candidate_id)}",
                "source_merchant_id": ids["merchantId"],
                "source_sku": _clean(payload.get("merchantSku")) or None,
                "source_url": product_url or None,
                "product_id": ids["productId"],
                "product_did": ids["productDid"],
                "confidence": 0.35,
                "reason": "title-hash product identity requires human or GTIN confirmation",
                "status": "pending",
                "repo": KAKAKU_DID,
                "collection": MATCH_COLLECTION,
                "created_at": now,
            },
        )
        match_created = 1
        writes += match_created

    return {
        "status": "ok",
        "productId": ids["productId"],
        "productDid": ids["productDid"],
        "globalProductId": product_values["global_product_id"],
        "globalProductDid": product_values["global_product_did"],
        "merchantId": ids["merchantId"],
        "merchantDid": ids["merchantDid"],
        "offerId": ids["offerId"],
        "offerDid": ids["offerDid"],
        "historyWritten": history_written > 0,
        "matchCandidateCreated": match_created > 0,
        "recordsWritten": writes,
        "totalPrice": total_price,
        "currency": currency,
    }


_TITLE_RE = re.compile(r"<title[^>]*>(.*?)</title>", re.IGNORECASE | re.DOTALL)
_JSONLD_RE = re.compile(
    r"<script[^>]+type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script>",
    re.IGNORECASE | re.DOTALL,
)
_PRICE_RE = re.compile(
    r"(?:price|価格|税込)[^0-9]{0,20}([0-9][0-9,]*(?:\.[0-9]+)?)",
    re.IGNORECASE,
)


def _strip_tags(value: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(value))).strip()


def extract_offer_from_html(body_text: str) -> dict[str, Any]:
    text = body_text or ""
    title_match = _TITLE_RE.search(text)
    title = _strip_tags(title_match.group(1)) if title_match else ""
    extracted: dict[str, Any] = {"fetchedTitle": title}

    for match in _JSONLD_RE.finditer(text):
        raw = html.unescape(match.group(1)).strip()
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            continue
        nodes = data if isinstance(data, list) else [data]
        for node in nodes:
            if not isinstance(node, dict):
                continue
            offers = node.get("offers")
            offer = offers[0] if isinstance(offers, list) and offers else offers
            if isinstance(offer, dict):
                extracted["name"] = _clean(node.get("name")) or title
                if offer.get("price") is not None:
                    extracted["price"] = _price(offer.get("price"))
                extracted["currency"] = _clean(offer.get("priceCurrency"))
                extracted["availability"] = _clean(offer.get("availability")).rsplit("/", 1)[-1].lower()
                extracted["extractionMethod"] = "jsonld"
                return {k: v for k, v in extracted.items() if v not in ("", None)}

    price_match = _PRICE_RE.search(_strip_tags(text[:200_000]))
    if price_match:
        extracted["price"] = _price(price_match.group(1))
        extracted["name"] = title
        extracted["extractionMethod"] = "regex"
    return {k: v for k, v in extracted.items() if v not in ("", None)}


async def task_upsert_offer(
    productId: str = "",
    name: str = "",
    brand: str = "",
    model: str = "",
    jan: str = "",
    gtin: str = "",
    mpn: str = "",
    packSize: str = "",
    category: str = "",
    merchantId: str = "",
    merchantName: str = "",
    domain: str = "",
    merchantSku: str = "",
    nativeOfferId: str = "",
    price: Any = None,
    shippingFee: Any = None,
    currency: str = "",
    availability: str = "",
    deliveryEta: str = "",
    productUrl: str = "",
    observedAt: str = "",
    **extra: Any,
) -> dict[str, Any]:
    payload = {
        **extra,
        "productId": productId,
        "name": name,
        "brand": brand,
        "model": model,
        "jan": jan,
        "gtin": gtin,
        "mpn": mpn,
        "packSize": packSize,
        "category": category,
        "merchantId": merchantId,
        "merchantName": merchantName,
        "domain": domain,
        "merchantSku": merchantSku,
        "nativeOfferId": nativeOfferId,
        "price": price,
        "shippingFee": shippingFee,
        "currency": currency,
        "availability": availability,
        "deliveryEta": deliveryEta,
        "productUrl": productUrl,
        "observedAt": observedAt,
    }
    if not _clean(payload.get("merchantName")):
        return {"status": "error", "error": "merchantName is required"}
    if payload.get("price") is None:
        return {"status": "error", "error": "price is required"}
    if not _clean(payload.get("currency")):
        return {"status": "error", "error": "currency is required"}
    try:
        return await asyncio.to_thread(upsert_offer_record, payload)
    except Exception as e:  # noqa: BLE001
        return {"status": "error", "error": f"kakaku.upsertOffer failed: {e}"}


async def task_ingest_offer_from_url(
    productUrl: str = "",
    merchantName: str = "",
    fetchedBody: str = "",
    fetchedTitle: str = "",
    **kwargs: Any,
) -> dict[str, Any]:
    if not _clean(productUrl):
        return {"status": "error", "error": "productUrl is required"}
    if not _clean(merchantName):
        return {"status": "error", "error": "merchantName is required"}
    extracted = extract_offer_from_html(fetchedBody or "")
    payload = {
        **kwargs,
        **{k: v for k, v in extracted.items() if k in {"name", "price", "currency", "availability", "extractionMethod"}},
        "productUrl": productUrl,
        "merchantName": merchantName,
    }
    if fetchedTitle and not payload.get("name"):
        payload["name"] = fetchedTitle
    for key in ("productId", "name", "brand", "model", "jan", "gtin", "mpn", "merchantSku", "nativeOfferId", "shippingFee", "currency", "availability", "deliveryEta"):
        if kwargs.get(key) not in (None, ""):
            payload[key] = kwargs[key]
    if payload.get("price") is None:
        return {
            "status": "needs_review",
            "error": "price could not be extracted",
            "fetchedTitle": extracted.get("fetchedTitle") or fetchedTitle,
            "extractionMethod": extracted.get("extractionMethod") or "none",
        }
    if not payload.get("currency"):
        payload["currency"] = "JPY"
    result = await asyncio.to_thread(upsert_offer_record, payload)
    return {
        **result,
        "fetchedTitle": extracted.get("fetchedTitle") or fetchedTitle,
        "extractedName": payload.get("name"),
        "extractedPrice": payload.get("price"),
        "availability": payload.get("availability") or "unknown",
        "extractionMethod": payload.get("extractionMethod") or "input",
        "barcodeSource": "input" if payload.get("jan") or payload.get("gtin") else "",
        "canonicalGtin14": canonical_gtin14(_clean(payload.get("jan")), _clean(payload.get("gtin"))),
    }


def task_compare_offers(productId: str = "", productDid: str = "", limit: int = 50) -> dict[str, Any]:
    product_id = _clean(productId)
    if not product_id and productDid:
        product_id = _clean(productDid).rsplit(":", 1)[-1]
    if not product_id:
        return {"productId": "", "offers": [], "error": "productId is required"}
    safe_limit = max(1, min(int(limit or 50), 100))
    client = get_kotoba_client()

    # R0: Fetch all offers for the product_id and then apply join/order/limit in Python.
    offers_raw = client.select_where("vertex_kakaku_offer", "product_id", product_id)

    rows: list[dict[str, Any]] = []
    for offer in offers_raw:
        # Apply WHERE COALESCE(o.status, 'active') = 'active'
        offer_status = offer.get("status")
        if offer_status is None:
            offer_status = "active"
        if offer_status != "active":
            continue

        merchant_id = offer.get("merchant_id")
        merchant_data = None
        if merchant_id:
            merchant_data = client.select_first_where("vertex_kakaku_merchant", "merchant_id", merchant_id)

        reputation_score = merchant_data.get("reputation_score") if merchant_data else None
        merchant_status = merchant_data.get("status") if merchant_data else None

        # Apply COALESCE(m.reputation_score, 0.5)
        reputation_score = float(reputation_score) if reputation_score is not None else 0.5
        # Apply COALESCE(m.status, 'unknown')
        merchant_status = str(merchant_status) if merchant_status is not None else "unknown"

        rows.append({
            "offer_id": offer.get("offer_id"),
            "merchant_id": offer.get("merchant_id"),
            "price": offer.get("price"),
            "shipping_fee": offer.get("shipping_fee"),
            "total_price": offer.get("total_price"),
            "currency": offer.get("currency"),
            "availability": offer.get("availability"),
            "delivery_eta": offer.get("delivery_eta"),
            "product_url": offer.get("product_url"),
            "observed_at": offer.get("observed_at"),
            "reputation_score": reputation_score,
            "merchant_status": merchant_status,
        })

    # Apply ORDER BY o.total_price ASC
    rows.sort(key=lambda x: float(x.get("total_price") or 0.0))

    # Apply LIMIT
    rows = rows[:safe_limit]

    def score(row: dict[str, Any]) -> float:
        total = float(row.get("total_price") or 0.0)
        rep = float(row.get("reputation_score") or 0.5)
        available = 0.0 if str(row.get("availability") or "").lower() in {"instock", "in_stock", "available"} else 1000.0
        inactive = 5000.0 if row.get("merchant_status") != "active" else 0.0
        return total - (rep * 100.0) + available + inactive

    cheapest = rows[0] if rows else None
    fastest = next((r for r in rows if _clean(r.get("delivery_eta"))), cheapest)
    best = min(rows, key=score) if rows else None
    suspicious = [
        r
        for r in rows
        if r.get("merchant_status") != "active"
        or not _clean(r.get("availability"))
        or float(r.get("total_price") or 0.0) <= 0
        or not _clean(r.get("product_url"))
    ]
    return {
        "productId": product_id,
        "bestOverall": best,
        "cheapest": cheapest,
        "fastest": fastest,
        "offers": rows,
        "suspiciousOffers": suspicious,
    }
