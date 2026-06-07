"""
yoro.productIngest primitives — generic public-retailer product/price ingest.

Adapters use only legally-clean public surfaces:
  - amazon-jp     : PA-API 5.0 SearchItems (official, Associates required)
  - rakuten       : Rakuten Ichiba IchibaItem/Search/20170706 (official, free App ID)
  - ikea-jp       : product page schema.org/Product JSON-LD
  - flexispot-jp  : Shopify /products.json public catalog endpoint
  - yodobashi     : sitemap + product page JSON-LD
  - kagu365       : sitemap + product page JSON-LD

Credentials are sourced from etzhayyim Vault at pod bootstrap (CronJob initContainer
`etzhayyim vault run --env-from amazon-paapi,rakuten-ichiba`) and exposed only as
process env. No plaintext caching server-side (vault zero-knowledge invariant).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import urllib.parse
import urllib.robotparser
import urllib.request
from datetime import datetime, timezone
from typing import Any, Iterable

from pydantic import BaseModel, Field, HttpUrl

USER_AGENT = "etzhayyim-yoro-product-ingest/1.0 (+https://yoro.etzhayyim.com/bot)"
DEFAULT_TIMEOUT = 15
DEFAULT_MAX_ITEMS = 20

ALL_RETAILERS = (
    "amazon-jp",
    "rakuten",
    "ikea-jp",
    "flexispot-jp",
    "yodobashi",
    "kagu365",
)


class OfferCard(BaseModel):
    retailer: str
    title: str
    brand: str | None = None
    model: str | None = None
    gtin: str | None = None
    price_jpy: int | None = None
    currency: str = "JPY"
    url: HttpUrl
    image_url: HttpUrl | None = None
    in_stock: bool | None = None
    captured_at: str = Field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    raw: dict[str, Any] = Field(default_factory=dict)


class IngestSummary(BaseModel):
    query: str
    category: str | None = None
    retailers: list[str]
    total_offers: int
    offers_by_retailer: dict[str, int]
    min_price_jpy: int | None = None
    max_price_jpy: int | None = None
    median_price_jpy: int | None = None


# ────────────────────── HTTP helpers ──────────────────────

_robots_cache: dict[str, urllib.robotparser.RobotFileParser] = {}


def _robots_allowed(url: str) -> bool:
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    rp = _robots_cache.get(base)
    if rp is None:
        rp = urllib.robotparser.RobotFileParser()
        rp.set_url(f"{base}/robots.txt")
        try:
            rp.read()
        except Exception:
            return True
        _robots_cache[base] = rp
    return rp.can_fetch(USER_AGENT, url)


def _http_get(url: str, headers: dict[str, str] | None = None) -> str:
    if not _robots_allowed(url):
        raise PermissionError(f"robots.txt disallows {url}")
    req = urllib.request.Request(
        url,
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json,*/*", **(headers or {})},
    )
    with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
        return resp.read().decode(resp.headers.get_content_charset() or "utf-8", errors="replace")


_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)


def _extract_jsonld_products(html: str) -> Iterable[dict[str, Any]]:
    for match in _JSONLD_RE.findall(html):
        try:
            data = json.loads(match.strip())
        except Exception:
            continue
        for node in _walk_jsonld(data):
            t = node.get("@type")
            if t == "Product" or (isinstance(t, list) and "Product" in t):
                yield node


def _walk_jsonld(node: Any) -> Iterable[dict[str, Any]]:
    if isinstance(node, dict):
        yield node
        for v in node.values():
            yield from _walk_jsonld(v)
    elif isinstance(node, list):
        for v in node:
            yield from _walk_jsonld(v)


def _jsonld_to_offer(retailer: str, node: dict[str, Any], page_url: str) -> OfferCard | None:
    title = node.get("name")
    if not title:
        return None
    brand = node.get("brand")
    if isinstance(brand, dict):
        brand = brand.get("name")
    gtin = node.get("gtin13") or node.get("gtin12") or node.get("gtin14") or node.get("gtin8") or node.get("gtin")
    image = node.get("image")
    if isinstance(image, list):
        image = image[0] if image else None
    offers = node.get("offers")
    if isinstance(offers, list):
        offers = offers[0] if offers else None
    price_jpy: int | None = None
    in_stock: bool | None = None
    offer_url = page_url
    if isinstance(offers, dict):
        raw_price = offers.get("price") or offers.get("lowPrice")
        if raw_price is not None:
            try:
                price_jpy = int(float(str(raw_price).replace(",", "")))
            except Exception:
                price_jpy = None
        avail = (offers.get("availability") or "").lower()
        if "instock" in avail:
            in_stock = True
        elif "outofstock" in avail or "soldout" in avail:
            in_stock = False
        offer_url = offers.get("url") or page_url
    return OfferCard(
        retailer=retailer,
        title=str(title),
        brand=str(brand) if brand else None,
        model=node.get("model") or node.get("mpn"),
        gtin=str(gtin) if gtin else None,
        price_jpy=price_jpy,
        url=offer_url,  # type: ignore[arg-type]
        image_url=str(image) if image else None,  # type: ignore[arg-type]
        in_stock=in_stock,
        raw={"jsonld": node},
    )


# ────────────────────── Adapters ──────────────────────


def fetch_amazon_jp(query: str, max_items: int) -> list[OfferCard]:
    access = os.environ.get("AMAZON_PAAPI_ACCESS_KEY")
    secret = os.environ.get("AMAZON_PAAPI_SECRET_KEY")
    partner = os.environ.get("AMAZON_PAAPI_PARTNER_TAG")
    if not (access and secret and partner):
        return []
    host = "webservices.amazon.co.jp"
    path = "/paapi5/searchitems"
    payload = {
        "Keywords": query,
        "PartnerTag": partner,
        "PartnerType": "Associates",
        "Marketplace": "www.amazon.co.jp",
        "ItemCount": min(max_items, 10),
        "Resources": [
            "ItemInfo.Title",
            "ItemInfo.ByLineInfo",
            "ItemInfo.ExternalIds",
            "Images.Primary.Medium",
            "Offers.Listings.Price",
            "Offers.Listings.Availability.Message",
        ],
    }
    body = json.dumps(payload).encode()
    amz_date = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    date_stamp = amz_date[:8]
    target = "com.amazon.paapi5.v1.ProductAdvertisingAPIv1.SearchItems"
    canonical_headers = (
        f"content-encoding:amz-1.0\n"
        f"content-type:application/json; charset=utf-8\n"
        f"host:{host}\n"
        f"x-amz-date:{amz_date}\n"
        f"x-amz-target:{target}\n"
    )
    signed_headers = "content-encoding;content-type;host;x-amz-date;x-amz-target"
    payload_hash = hashlib.sha256(body).hexdigest()
    canonical_request = f"POST\n{path}\n\n{canonical_headers}\n{signed_headers}\n{payload_hash}"
    credential_scope = f"{date_stamp}/us-west-2/ProductAdvertisingAPI/aws4_request"
    string_to_sign = (
        f"AWS4-HMAC-SHA256\n{amz_date}\n{credential_scope}\n"
        + hashlib.sha256(canonical_request.encode()).hexdigest()
    )

    def _sign(key: bytes, msg: str) -> bytes:
        return hmac.new(key, msg.encode(), hashlib.sha256).digest()

    k_date = _sign(("AWS4" + secret).encode(), date_stamp)
    k_region = _sign(k_date, "us-west-2")
    k_service = _sign(k_region, "ProductAdvertisingAPI")
    k_signing = _sign(k_service, "aws4_request")
    signature = hmac.new(k_signing, string_to_sign.encode(), hashlib.sha256).hexdigest()
    auth = (
        f"AWS4-HMAC-SHA256 Credential={access}/{credential_scope}, "
        f"SignedHeaders={signed_headers}, Signature={signature}"
    )
    req = urllib.request.Request(
        f"https://{host}{path}",
        data=body,
        headers={
            "Authorization": auth,
            "Content-Encoding": "amz-1.0",
            "Content-Type": "application/json; charset=utf-8",
            "Host": host,
            "X-Amz-Date": amz_date,
            "X-Amz-Target": target,
            "User-Agent": USER_AGENT,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=DEFAULT_TIMEOUT) as resp:
            data = json.loads(resp.read().decode())
    except Exception:
        return []
    out: list[OfferCard] = []
    for item in (data.get("SearchResult") or {}).get("Items") or []:
        info = item.get("ItemInfo") or {}
        title = ((info.get("Title") or {}).get("DisplayValue")) or ""
        if not title:
            continue
        byline = (info.get("ByLineInfo") or {})
        brand = ((byline.get("Brand") or {}).get("DisplayValue")) or ((byline.get("Manufacturer") or {}).get("DisplayValue"))
        ext = (info.get("ExternalIds") or {})
        ean = ((ext.get("EANs") or {}).get("DisplayValues") or [None])[0]
        listing = ((item.get("Offers") or {}).get("Listings") or [{}])[0]
        price = ((listing.get("Price") or {}).get("Amount"))
        avail_msg = ((listing.get("Availability") or {}).get("Message")) or ""
        out.append(
            OfferCard(
                retailer="amazon-jp",
                title=title,
                brand=brand,
                gtin=ean,
                price_jpy=int(float(price)) if price is not None else None,
                url=item.get("DetailPageURL"),  # type: ignore[arg-type]
                image_url=(((item.get("Images") or {}).get("Primary") or {}).get("Medium") or {}).get("URL"),
                in_stock="在庫" in avail_msg or "In Stock" in avail_msg,
                raw={"asin": item.get("ASIN")},
            )
        )
    return out


def fetch_rakuten(query: str, max_items: int) -> list[OfferCard]:
    app_id = os.environ.get("RAKUTEN_APP_ID")
    if not app_id:
        return []
    affiliate = os.environ.get("RAKUTEN_AFFILIATE_ID", "")
    params = {
        "applicationId": app_id,
        "affiliateId": affiliate,
        "keyword": query,
        "hits": min(max_items, 30),
        "format": "json",
        "formatVersion": "2",
    }
    url = (
        "https://app.rakuten.co.jp/services/api/IchibaItem/Search/20170706?"
        + urllib.parse.urlencode({k: v for k, v in params.items() if v})
    )
    try:
        text = _http_get(url)
        data = json.loads(text)
    except Exception:
        return []
    out: list[OfferCard] = []
    for item in data.get("Items") or []:
        title = item.get("itemName")
        if not title:
            continue
        out.append(
            OfferCard(
                retailer="rakuten",
                title=title,
                brand=item.get("shopName"),
                price_jpy=item.get("itemPrice"),
                url=item.get("itemUrl"),  # type: ignore[arg-type]
                image_url=(item.get("mediumImageUrls") or [None])[0],
                in_stock=(item.get("availability") == 1),
                raw={"itemCode": item.get("itemCode")},
            )
        )
    return out


def _scrape_jsonld_search(retailer: str, search_url: str, max_items: int) -> list[OfferCard]:
    try:
        html = _http_get(search_url)
    except Exception:
        return []
    out: list[OfferCard] = []
    seen: set[str] = set()
    for node in _extract_jsonld_products(html):
        offer = _jsonld_to_offer(retailer, node, search_url)
        if offer is None or str(offer.url) in seen:
            continue
        seen.add(str(offer.url))
        out.append(offer)
        if len(out) >= max_items:
            break
    return out


def fetch_ikea_jp(query: str, max_items: int) -> list[OfferCard]:
    url = f"https://www.ikea.com/jp/ja/search/products/?q={urllib.parse.quote(query)}"
    return _scrape_jsonld_search("ikea-jp", url, max_items)


def fetch_flexispot_jp(query: str, max_items: int) -> list[OfferCard]:
    base = "https://flexispot.jp"
    url = f"{base}/search?q={urllib.parse.quote(query)}&type=product&view=json"
    try:
        text = _http_get(url, headers={"Accept": "application/json"})
        data = json.loads(text) if text.strip().startswith("{") else None
    except Exception:
        data = None
    if isinstance(data, dict) and isinstance(data.get("resources"), dict):
        items = (data["resources"].get("results") or {}).get("products") or []
        out: list[OfferCard] = []
        for p in items[:max_items]:
            handle = p.get("handle") or p.get("url")
            url2 = f"{base}/products/{handle}" if handle and not str(handle).startswith("http") else handle
            price_min = p.get("price_min") or p.get("price")
            try:
                price_jpy = int(float(price_min) / 100) if price_min and float(price_min) > 1000 else int(float(price_min)) if price_min else None
            except Exception:
                price_jpy = None
            out.append(
                OfferCard(
                    retailer="flexispot-jp",
                    title=p.get("title") or "",
                    brand="FlexiSpot",
                    price_jpy=price_jpy,
                    url=url2,  # type: ignore[arg-type]
                    image_url=p.get("featured_image") or p.get("image"),
                    in_stock=p.get("available"),
                    raw={"handle": handle},
                )
            )
        return [o for o in out if o.title]
    return _scrape_jsonld_search("flexispot-jp", f"{base}/search?q={urllib.parse.quote(query)}", max_items)


def fetch_yodobashi(query: str, max_items: int) -> list[OfferCard]:
    url = f"https://www.yodobashi.com/?word={urllib.parse.quote(query)}"
    return _scrape_jsonld_search("yodobashi", url, max_items)


def fetch_kagu365(query: str, max_items: int) -> list[OfferCard]:
    url = f"https://kagu365.jp/?s={urllib.parse.quote(query)}&post_type=product"
    return _scrape_jsonld_search("kagu365", url, max_items)


ADAPTERS = {
    "amazon-jp": fetch_amazon_jp,
    "rakuten": fetch_rakuten,
    "ikea-jp": fetch_ikea_jp,
    "flexispot-jp": fetch_flexispot_jp,
    "yodobashi": fetch_yodobashi,
    "kagu365": fetch_kagu365,
}


def fetch_one(retailer: str, query: str, max_items: int) -> list[OfferCard]:
    adapter = ADAPTERS.get(retailer)
    if adapter is None:
        return []
    try:
        time.sleep(0.5)
        return adapter(query, max_items)
    except Exception:
        return []


def summarize(query: str, category: str | None, offers: list[OfferCard]) -> IngestSummary:
    by_retailer: dict[str, int] = {}
    prices: list[int] = []
    for o in offers:
        by_retailer[o.retailer] = by_retailer.get(o.retailer, 0) + 1
        if o.price_jpy is not None:
            prices.append(o.price_jpy)
    prices.sort()
    median = prices[len(prices) // 2] if prices else None
    return IngestSummary(
        query=query,
        category=category,
        retailers=sorted(by_retailer.keys()),
        total_offers=len(offers),
        offers_by_retailer=by_retailer,
        min_price_jpy=prices[0] if prices else None,
        max_price_jpy=prices[-1] if prices else None,
        median_price_jpy=median,
    )
