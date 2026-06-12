"""
global_product_enrich_one — Phase 1 product evidence LangGraph.

ADR-2605091200 makes product ingest an evidence-first graph:
official product pages establish identity/spec facts, merchant pages establish
offers/prices, and inference/intel are explicit checkpointed nodes.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import time
import urllib.parse
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict


OWNER_DID = "did:web:gtin.etzhayyim.com"
ACTOR_ID = "sys.langgraph.global-product-enrich-one"
PROMPT_VERSION = "global-product-enrich-one-v1"
DEFAULT_TIMEOUT = 30.0

_JSONLD_RE = re.compile(
    r'<script[^>]*type=["\']application/ld\+json["\'][^>]*>(.*?)</script>',
    re.DOTALL | re.IGNORECASE,
)
_TAG_RE = re.compile(r"<[^>]+>")
_GTIN_LABEL_RE = re.compile(
    r"(?:GTIN|JAN|UPC|EAN|barcode|バーコード)[^\d]{0,24}(\d{8,14})",
    re.IGNORECASE,
)
_GTIN_ANY_RE = re.compile(r"\b(\d{8}|\d{12,14})\b")


class GlobalProductEnrichState(TypedDict, total=False):
    query: str
    productUrl: str
    merchantUrl: str
    officialUrls: list[str]
    merchantUrls: list[str]
    brand: str
    model: str
    gtin: str
    category: str
    useInference: bool
    jobId: str
    officialEvidence: list[dict[str, Any]]
    merchantEvidence: list[dict[str, Any]]
    productFacts: dict[str, Any]
    brandOwnerCandidates: list[dict[str, Any]]
    canonicalProduct: dict[str, Any]
    matchDecision: dict[str, Any]
    written: dict[str, int]
    ok: bool
    error: str | None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _url_domain(url: str) -> str:
    try:
        return urllib.parse.urlparse(url).hostname or ""
    except Exception:
        return ""


def _normalize_urls(*values: Any) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for value in values:
        items = value if isinstance(value, list) else [value]
        for item in items:
            url = str(item or "").strip()
            if not url or not (url.startswith("http://") or url.startswith("https://")):
                continue
            if url in seen:
                continue
            seen.add(url)
            out.append(url)
    return out


def _strip_tags(html: str) -> str:
    return _TAG_RE.sub(" ", html).replace("\xa0", " ")


def _walk_json(value: Any) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    if isinstance(value, dict):
        found.append(value)
        for child in value.values():
            found.extend(_walk_json(child))
    elif isinstance(value, list):
        for child in value:
            found.extend(_walk_json(child))
    return found


def _jsonld_products(html: str) -> list[dict[str, Any]]:
    products: list[dict[str, Any]] = []
    for raw in _JSONLD_RE.findall(html or ""):
        try:
            parsed = json.loads(raw.strip())
        except Exception:
            continue
        for node in _walk_json(parsed):
            typ = node.get("@type")
            if typ == "Product" or (isinstance(typ, list) and "Product" in typ):
                products.append(node)
    return products


def _first_text(*values: Any) -> str:
    for value in values:
        if value is None:
            continue
        if isinstance(value, dict):
            value = value.get("name") or value.get("@id")
        if isinstance(value, list):
            value = value[0] if value else ""
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _extract_gtin(text: str, products: list[dict[str, Any]]) -> str:
    for node in products:
        value = _first_text(
            node.get("gtin14"),
            node.get("gtin13"),
            node.get("gtin12"),
            node.get("gtin8"),
            node.get("gtin"),
        )
        digits = re.sub(r"\D+", "", value)
        if len(digits) in (8, 12, 13, 14):
            return digits
    for pattern in (_GTIN_LABEL_RE, _GTIN_ANY_RE):
        match = pattern.search(text or "")
        if match:
            return match.group(1)
    return ""


def _extract_facts(evidence: list[dict[str, Any]], hints: dict[str, str]) -> dict[str, Any]:
    products: list[dict[str, Any]] = []
    text_parts: list[str] = []
    official_urls: list[str] = []
    image_url = ""
    for item in evidence:
        markdown = str(item.get("markdown") or "")
        html = str(item.get("html") or "")
        text_parts.append(markdown or _strip_tags(html))
        if item.get("sourceKind") == "official":
            official_urls.append(str(item.get("url") or ""))
        products.extend(_jsonld_products(html))

    first_product = products[0] if products else {}
    brand = _first_text(hints.get("brand"), first_product.get("brand"))
    name = _first_text(first_product.get("name"), hints.get("query"), hints.get("model"))
    model = _first_text(hints.get("model"), first_product.get("model"), first_product.get("mpn"))
    mpn = _first_text(first_product.get("mpn"), first_product.get("sku"), model)
    image = first_product.get("image")
    if isinstance(image, list):
        image_url = str(image[0]) if image else ""
    elif image:
        image_url = str(image)
    text = "\n".join(text_parts)
    gtin = re.sub(r"\D+", "", hints.get("gtin") or "") or _extract_gtin(text, products)
    confidence = 0.9 if gtin else 0.72 if (brand and model) else 0.45
    product_key = (
        f"gtin_{gtin}" if gtin else
        f"brand_model_{_sha256((brand + '|' + model).lower())[:16]}" if brand or model else
        f"title_{_sha256(name.lower())[:16]}" if name else
        f"job_{uuid.uuid4().hex[:12]}"
    )
    return {
        "name": name,
        "brand": brand,
        "model": model,
        "mpn": mpn,
        "gtin": gtin,
        "category": hints.get("category") or "",
        "officialUrl": official_urls[0] if official_urls else "",
        "imageUrl": image_url,
        "productKey": product_key,
        "confidence": confidence,
        "extractionMethod": "jsonld+heuristic" if products else "heuristic",
    }


def seed(state: GlobalProductEnrichState) -> dict[str, Any]:
    official_urls = _normalize_urls(state.get("officialUrls"), state.get("productUrl"))
    merchant_urls = _normalize_urls(state.get("merchantUrls"), state.get("merchantUrl"))
    if not official_urls and not merchant_urls and not state.get("query"):
        return {"ok": False, "error": "query, officialUrls, productUrl, merchantUrls, or merchantUrl is required"}
    return {
        "officialUrls": official_urls,
        "merchantUrls": merchant_urls,
        "jobId": state.get("jobId") or f"product-enrich-{uuid.uuid4().hex[:12]}",
        "useInference": bool(state.get("useInference", os.environ.get("PRODUCT_INGEST_USE_LLM", "1") != "0")),
        "ok": True,
        "error": None,
    }


def discover_candidates(state: GlobalProductEnrichState) -> dict[str, Any]:
    # Phase 1 uses caller-supplied URLs. Resident frontier/search expansion is Phase 2.
    official_urls = _normalize_urls(state.get("officialUrls"), state.get("productUrl"))
    merchant_urls = _normalize_urls(state.get("merchantUrls"), state.get("merchantUrl"))
    return {"officialUrls": official_urls, "merchantUrls": merchant_urls}


def _crawl_page(url: str, source_kind: str) -> dict[str, Any]:
    import httpx

    pds_base = os.environ.get("PDS_BASE_URL", "https://atproto.etzhayyim.com")
    token = os.environ.get("INTERNAL_TRUST_TOKEN", "")
    headers = {"content-type": "application/json", "x-kotoba-kotodama-verified": "true"}
    if token:
        headers["x-internal-trust"] = token
    started = time.time()
    try:
        resp = httpx.post(
            f"{pds_base}/xrpc/com.etzhayyim.apps.site.crawlPage",
            json={"url": url, "topics": ["product", "commerce", "pricing", source_kind]},
            headers=headers,
            timeout=DEFAULT_TIMEOUT,
        )
        data = resp.json() if resp.status_code < 500 else {}
        markdown = str(data.get("markdown") or data.get("wet") or "")
        html = str(data.get("html") or "")
        title = str(data.get("title") or "")
        return {
            "url": url,
            "domain": _url_domain(url),
            "sourceKind": source_kind,
            "fetchMethod": "site.crawlPage",
            "httpStatus": resp.status_code,
            "title": title,
            "markdown": markdown,
            "html": html,
            "contentSha256": _sha256(markdown or html or title or url),
            "fetchedAt": _now_iso(),
            "latencyMs": int((time.time() - started) * 1000),
            "ok": resp.status_code < 400,
            "error": "" if resp.status_code < 400 else f"http {resp.status_code}",
        }
    except Exception as exc:
        return {
            "url": url,
            "domain": _url_domain(url),
            "sourceKind": source_kind,
            "fetchMethod": "site.crawlPage",
            "httpStatus": 0,
            "title": "",
            "markdown": "",
            "html": "",
            "contentSha256": _sha256(url),
            "fetchedAt": _now_iso(),
            "latencyMs": int((time.time() - started) * 1000),
            "ok": False,
            "error": str(exc),
        }


def fetch_official_pages(state: GlobalProductEnrichState) -> dict[str, Any]:
    return {"officialEvidence": [_crawl_page(url, "official") for url in state.get("officialUrls", [])]}


def fetch_merchant_pages(state: GlobalProductEnrichState) -> dict[str, Any]:
    return {"merchantEvidence": [_crawl_page(url, "merchant") for url in state.get("merchantUrls", [])]}


def extract_product_facts(state: GlobalProductEnrichState) -> dict[str, Any]:
    hints = {
        "query": str(state.get("query") or ""),
        "brand": str(state.get("brand") or ""),
        "model": str(state.get("model") or ""),
        "gtin": str(state.get("gtin") or ""),
        "category": str(state.get("category") or ""),
    }
    evidence = list(state.get("officialEvidence", [])) + list(state.get("merchantEvidence", []))
    return {"productFacts": _extract_facts(evidence, hints)}


def resolve_brand_owner(state: GlobalProductEnrichState) -> dict[str, Any]:
    facts = state.get("productFacts", {})
    official_url = str(facts.get("officialUrl") or "")
    brand = str(facts.get("brand") or "")
    candidates = []
    if brand:
        try:
            ok, data = _post_xrpc(
                "com.etzhayyim.apps.intel.resolveEntity",
                {
                    "query": brand,
                    "entityKind": "legal_entity",
                    "hints": {"domain": _url_domain(official_url), "source": "global_product_enrich_one"},
                    "maxCandidates": 5,
                },
            )
            if ok and isinstance(data.get("candidates"), list):
                for item in data["candidates"][:5]:
                    if isinstance(item, dict):
                        candidates.append({**item, "source": "intel.resolveEntity"})
        except Exception as exc:
            candidates.append({"brand": brand, "source": "intel.resolveEntity", "error": str(exc), "confidence": 0.0})
    if official_url or brand:
        candidates.append(
            {
                "brand": brand,
                "domain": _url_domain(official_url),
                "source": "official_url" if official_url else "brand_hint",
                "confidence": 0.7 if official_url else 0.45,
            }
        )
    return {"brandOwnerCandidates": candidates}


def infer_match_confidence(state: GlobalProductEnrichState) -> dict[str, Any]:
    facts = state.get("productFacts", {})
    if not state.get("useInference") or float(facts.get("confidence") or 0) >= 0.86:
        return {"matchDecision": {"confidence": facts.get("confidence", 0), "method": facts.get("extractionMethod", "heuristic")}}
    try:
        from kotodama import llm

        resp = llm.call_tier_json(
            "structured",
            system="Return JSON only. Judge whether product facts identify one canonical trade item.",
            user=json.dumps(
                {
                    "facts": facts,
                    "officialEvidence": state.get("officialEvidence", [])[:2],
                    "merchantEvidence": state.get("merchantEvidence", [])[:2],
                },
                ensure_ascii=False,
            ),
            max_tokens=300,
            temperature=0.0,
        )
        if resp.get("ok") and isinstance(resp.get("data"), dict):
            data = resp["data"]
            confidence = float(data.get("confidence") or facts.get("confidence") or 0)
            return {
                "matchDecision": {
                    "confidence": max(0.0, min(confidence, 1.0)),
                    "method": "llm",
                    "model": resp.get("model", ""),
                    "rationale": str(data.get("rationale") or ""),
                }
            }
        return {"matchDecision": {"confidence": facts.get("confidence", 0), "method": "heuristic", "llmError": resp.get("error")}}
    except Exception as exc:
        return {"matchDecision": {"confidence": facts.get("confidence", 0), "method": "heuristic", "llmError": str(exc)}}


def resolve_canonical_product(state: GlobalProductEnrichState) -> dict[str, Any]:
    facts = state.get("productFacts", {})
    decision = state.get("matchDecision", {})
    product_key = str(facts.get("productKey") or "")
    gtin = str(facts.get("gtin") or "")
    product_did = (
        f"did:web:gtin.etzhayyim.com:product:gtin_{gtin}" if gtin else
        f"did:web:gtin.etzhayyim.com:product:{product_key}"
    )
    return {
        "canonicalProduct": {
            "productId": product_key,
            "productDid": product_did,
            "globalProductDid": product_did,
            "confidence": float(decision.get("confidence") or facts.get("confidence") or 0),
            "status": "accepted" if float(decision.get("confidence") or facts.get("confidence") or 0) >= 0.65 else "needs_review",
        }
    }


def quality_gate(state: GlobalProductEnrichState) -> dict[str, Any]:
    canonical = state.get("canonicalProduct", {})
    facts = state.get("productFacts", {})
    confidence = float(canonical.get("confidence") or 0)
    if facts.get("gtin"):
        return {"ok": True, "error": None}
    if confidence >= 0.65 and (facts.get("brand") or facts.get("model") or facts.get("officialUrl")):
        return {"ok": True, "error": None}
    return {"ok": False, "error": "insufficient product identity evidence"}


def _post_xrpc(method: str, body: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    import httpx

    pds_base = os.environ.get("PDS_BASE_URL", "https://atproto.etzhayyim.com")
    token = os.environ.get("INTERNAL_TRUST_TOKEN", "")
    headers = {"content-type": "application/json"}
    if token:
        headers["x-internal-trust"] = token
    resp = httpx.post(f"{pds_base}/xrpc/{method}", json=body, headers=headers, timeout=DEFAULT_TIMEOUT)
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text[:500]}
    return resp.status_code < 300, data


def write_graph(state: GlobalProductEnrichState) -> dict[str, Any]:
    if state.get("ok") is False:
        return {"written": {"skipped": 1}}
    facts = state.get("productFacts", {})
    canonical = state.get("canonicalProduct", {})
    written = {"gtinProduct": 0, "kakakuOffer": 0, "sourcePage": 0, "factEvidence": 0, "edge": 0}
    errors: list[str] = []

    if facts.get("name"):
        ok, data = _post_xrpc(
            "com.etzhayyim.apps.gtin.registerProduct",
            {
                "productId": canonical.get("productId"),
                "name": facts.get("name"),
                "brand": facts.get("brand"),
                "model": facts.get("model"),
                "gtin": facts.get("gtin"),
                "packSize": "",
                "category": facts.get("category"),
            },
        )
        if ok:
            written["gtinProduct"] = 1
            if data.get("productDid"):
                canonical["productDid"] = data.get("productDid")
        else:
            errors.append(f"gtin.registerProduct: {data}")

    for evidence in state.get("merchantEvidence", []):
        if not evidence.get("url"):
            continue
        ok, data = _post_xrpc(
            "com.etzhayyim.apps.kakaku.ingestOfferFromUrl",
            {
                "productUrl": evidence.get("url"),
                "merchantName": evidence.get("domain") or "unknown",
                "productId": canonical.get("productId"),
                "name": facts.get("name"),
                "brand": facts.get("brand"),
                "model": facts.get("model"),
                "gtin": facts.get("gtin"),
            },
        )
        if ok:
            written["kakakuOffer"] += 1
        else:
            errors.append(f"kakaku.ingestOfferFromUrl {evidence.get('url')}: {data}")

    evidence_written = _write_evidence_rows(state)
    written.update(evidence_written)
    return {"written": written, "canonicalProduct": canonical, "error": "; ".join(errors) if errors else state.get("error")}


def _write_evidence_rows(state: GlobalProductEnrichState) -> dict[str, Any]:
    from kotodama.kotoba_datomic import get_kotoba_client

    now = _now_iso()
    today = now[:10]
    canonical = state.get("canonicalProduct", {})
    facts = state.get("productFacts", {})
    product_vid = str(canonical.get("productDid") or "")
    product_key = str(canonical.get("productId") or facts.get("productKey") or state.get("jobId") or "")





    source_rows: list[dict[str, Any]] = []
    fact_rows: list[dict[str, Any]] = []
    official_edge_rows: list[dict[str, Any]] = []
    brand_owner_edge_rows: list[dict[str, Any]] = []
    source_vid_by_url: dict[str, str] = {}
    for item in list(state.get("officialEvidence", [])) + list(state.get("merchantEvidence", [])):
        url = str(item.get("url") or "")
        if not url:
            continue
        source_id = _sha256(url)[:24]
        vertex_id = f"at://{OWNER_DID}/com.etzhayyim.apps.gtin.productSourcePage/{source_id}"
        source_vid_by_url[url] = vertex_id
        source_kind = str(item.get("sourceKind") or "unknown")
        source_rows.append(
            {
                "vertex_id": vertex_id,
                "source_page_id": source_id,
                "product_vid": product_vid,
                "product_key": product_key,
                "source_kind": source_kind,
                "authority_rank": 1 if source_kind == "official" else 4,
                "url": url,
                "domain": item.get("domain") or _url_domain(url),
                "title": item.get("title") or "",
                "content_sha256": item.get("contentSha256") or _sha256(url),
                "fetched_at": item.get("fetchedAt") or now,
                "fetch_method": item.get("fetchMethod") or "site.crawlPage",
                "http_status": int(item.get("httpStatus") or 0),
                "evidence_json": json.dumps({k: v for k, v in item.items() if k not in ("html", "markdown")}, ensure_ascii=False),
                "status": "active" if item.get("ok") else "fetch_failed",
                "created_at": now,
                "updated_at": now,
                "created_date": today,
                "sensitivity_ord": 0,
                "owner_did": OWNER_DID,
                "actor_id": ACTOR_ID,
            }
        )
        if product_vid and source_kind == "official":
            edge_id = f"edge:product-official-source:{_sha256(product_vid + '|' + vertex_id)[:32]}"
            official_edge_rows.append(
                {
                    "edge_id": edge_id,
                    "src_vid": product_vid,
                    "dst_vid": vertex_id,
                    "relation_type": "OfficialSource",
                    "source_kind": source_kind,
                    "authority_rank": 1,
                    "confidence": float(facts.get("confidence") or 0.7),
                    "evidence_json": json.dumps({"url": url, "jobId": state.get("jobId")}, ensure_ascii=False),
                    "status": "active",
                    "created_at": now,
                    "created_date": today,
                    "sensitivity_ord": 0,
                    "owner_did": OWNER_DID,
                    "actor_id": ACTOR_ID,
                }
            )

    source_page_vid = source_vid_by_url.get(str(facts.get("officialUrl") or "")) or (next(iter(source_vid_by_url.values()), ""))
    for field in ("name", "brand", "model", "mpn", "gtin", "category", "officialUrl", "imageUrl"):
        value = str(facts.get(field) or "").strip()
        if not value:
            continue
        fact_id = _sha256(f"{product_key}|{field}|{value}")[:24]
        fact_rows.append(
            {
                "vertex_id": f"at://{OWNER_DID}/com.etzhayyim.apps.gtin.productFactEvidence/{fact_id}",
                "fact_id": fact_id,
                "product_vid": product_vid,
                "product_key": product_key,
                "source_page_vid": source_page_vid,
                "source_kind": "official" if field in ("officialUrl", "imageUrl") else "mixed",
                "field_name": field,
                "field_value": value,
                "normalized_value": value.lower(),
                "extraction_method": facts.get("extractionMethod") or "heuristic",
                "confidence": float(facts.get("confidence") or 0),
                "model": state.get("matchDecision", {}).get("model") or "",
                "prompt_version": PROMPT_VERSION,
                "evidence_json": json.dumps({"jobId": state.get("jobId")}, ensure_ascii=False),
                "status": "active",
                "created_at": now,
                "updated_at": now,
                "created_date": today,
                "sensitivity_ord": 0,
                "owner_did": OWNER_DID,
                "actor_id": ACTOR_ID,
            }
        )
    for candidate in state.get("brandOwnerCandidates", []):
        domain = str(candidate.get("domain") or "").strip()
        brand_name = str(candidate.get("brand") or facts.get("brand") or "").strip()
        if not product_vid or not (domain or brand_name):
            continue
        owner_key = domain or f"brand:{brand_name.lower()}"
        dst_vid = f"did:web:{domain}" if domain else f"did:web:gtin.etzhayyim.com:brand:{_sha256(brand_name.lower())[:16]}"
        edge_id = f"edge:product-brand-owner:{_sha256(product_vid + '|' + owner_key)[:32]}"
        brand_owner_edge_rows.append(
            {
                "edge_id": edge_id,
                "src_vid": product_vid,
                "dst_vid": dst_vid,
                "relation_type": "BrandOwnerCandidate",
                "brand_name": brand_name,
                "owner_name": domain or brand_name,
                "confidence": float(candidate.get("confidence") or 0.45),
                "evidence_json": json.dumps(candidate, ensure_ascii=False),
                "status": "candidate",
                "created_at": now,
                "created_date": today,
                "sensitivity_ord": 0,
                "owner_did": OWNER_DID,
                "actor_id": ACTOR_ID,
            }
        )
    try:
        if source_rows:
            get_kotoba_client().insert_rows("vertex_product_source_page", source_rows)
        if fact_rows:
            get_kotoba_client().insert_rows("vertex_product_fact_evidence", fact_rows)
        if official_edge_rows:
            get_kotoba_client().insert_rows("edge_product_official_source", official_edge_rows)
        if brand_owner_edge_rows:
            get_kotoba_client().insert_rows("edge_product_brand_owner", brand_owner_edge_rows)
    except Exception as exc:
        return {"sourcePage": 0, "factEvidence": 0, "edge": 0, "evidenceWriteError": 1, "evidenceError": str(exc)}
    return {
        "sourcePage": len(source_rows),
        "factEvidence": len(fact_rows),
        "edge": len(official_edge_rows) + len(brand_owner_edge_rows),
    }


def emit_audit(state: GlobalProductEnrichState) -> dict[str, Any]:
    try:
        from kotodama.primitives.audit import emit_audit_event  # type: ignore

        emit_audit_event(
            actor_did=OWNER_DID,
            event_type="globalProduct.enrichOne.completed",
            payload={
                "jobId": state.get("jobId"),
                "ok": state.get("ok"),
                "product": state.get("canonicalProduct"),
                "written": state.get("written"),
                "error": state.get("error"),
            },
        )
    except Exception as exc:
        return {"auditError": str(exc)}
    return {}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(GlobalProductEnrichState)
    builder.add_node("seed", seed)
    builder.add_node("discover_candidates", discover_candidates)
    builder.add_node("fetch_official_pages", fetch_official_pages)
    builder.add_node("fetch_merchant_pages", fetch_merchant_pages)
    builder.add_node("extract_product_facts", extract_product_facts)
    builder.add_node("resolve_brand_owner", resolve_brand_owner)
    builder.add_node("infer_match_confidence", infer_match_confidence)
    builder.add_node("resolve_canonical_product", resolve_canonical_product)
    builder.add_node("quality_gate", quality_gate)
    builder.add_node("write_graph", write_graph)
    builder.add_node("emit_audit", emit_audit)
    builder.set_entry_point("seed")
    builder.add_edge("seed", "discover_candidates")
    builder.add_edge("discover_candidates", "fetch_official_pages")
    builder.add_edge("fetch_official_pages", "fetch_merchant_pages")
    builder.add_edge("fetch_merchant_pages", "extract_product_facts")
    builder.add_edge("extract_product_facts", "resolve_brand_owner")
    builder.add_edge("resolve_brand_owner", "infer_match_confidence")
    builder.add_edge("infer_match_confidence", "resolve_canonical_product")
    builder.add_edge("resolve_canonical_product", "quality_gate")
    builder.add_edge("quality_gate", "write_graph")
    builder.add_edge("write_graph", "emit_audit")
    builder.add_edge("emit_audit", END)
    return builder.compile()
