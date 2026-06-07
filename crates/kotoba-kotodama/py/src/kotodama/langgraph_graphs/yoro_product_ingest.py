"""
yoro.productIngest — LangGraph StateGraph (ADR-2605080600 Phase 5).

Generic public-retailer product/price ingest under the yoro actor.

Graph:
  START → seed → fanout (Send per retailer) → collect → write_offers → write_research → emit_audit → END

Inputs (state):
  query                 str           required. e.g. "スタンディングデスク器具"
  category              str           optional. e.g. "office.standing-desk"
  retailers             list[str]     optional. defaults to all enabled
  maxItemsPerRetailer   int           optional. default 20
  actorPath             str           optional. default "research:product"
  jobId                 str           optional. populated if absent

Outputs (state):
  totalOffers           int
  offersByRetailer      dict[str,int]
  researchVertexId      str
  ok                    bool
  error                 str | None

RisingWave persistence (ADR-0036 Tier 2 + ADR-0095 canonical columns):
  - vertex_kakaku_offer       (1 row per retailer × product, via kakaku.ingestOfferFromUrl XRPC)
  - vertex_yoro_productResearch (1 row per ingest run, summary)
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import datetime, timezone
from typing import Any, TypedDict

YORO_DID_BASE = "did:web:yoro.etzhayyim.com"
DEFAULT_RETAILERS = ("amazon-jp", "rakuten", "ikea-jp", "flexispot-jp", "yodobashi", "kagu365")
DEFAULT_MAX = 20


class YoroProductIngestState(TypedDict, total=False):
    query: str
    category: str | None
    retailers: list[str]
    maxItemsPerRetailer: int
    actorPath: str
    jobId: str
    offers: list[dict]
    offersByRetailer: dict[str, int]
    totalOffers: int
    researchVertexId: str
    ok: bool
    error: str | None


# ── nodes ────────────────────────────────────────────────────────────────


def seed(state: YoroProductIngestState) -> dict:
    if not state.get("query"):
        return {"ok": False, "error": "query is required"}
    retailers = state.get("retailers") or list(DEFAULT_RETAILERS)
    return {
        "retailers": retailers,
        "maxItemsPerRetailer": state.get("maxItemsPerRetailer") or DEFAULT_MAX,
        "actorPath": state.get("actorPath") or "research:product",
        "jobId": state.get("jobId") or f"job-{uuid.uuid4().hex[:12]}",
        "offers": [],
    }


def _fanout_one(retailer: str, query: str, max_items: int) -> list[dict]:
    from kotodama.primitives.yoro_product import fetch_one

    offers = fetch_one(retailer, query, max_items)
    return [json.loads(o.model_dump_json()) for o in offers]


def fanout(state: YoroProductIngestState) -> dict:
    """Sequential fanout (LangGraph Send is alternative; sequential keeps rate limits sane)."""
    query = state["query"]
    max_items = state.get("maxItemsPerRetailer") or DEFAULT_MAX
    retailers = state.get("retailers") or list(DEFAULT_RETAILERS)
    all_offers: list[dict] = []
    by_retailer: dict[str, int] = {}
    errors: list[str] = []
    for r in retailers:
        try:
            rows = _fanout_one(r, query, max_items)
            all_offers.extend(rows)
            by_retailer[r] = len(rows)
        except Exception as e:
            errors.append(f"{r}: {e}")
            by_retailer[r] = 0
    return {
        "offers": all_offers,
        "offersByRetailer": by_retailer,
        "totalOffers": len(all_offers),
        "error": "; ".join(errors) if errors else None,
    }


def write_offers(state: YoroProductIngestState) -> dict:
    """Forward each offer to kakaku.ingestOfferFromUrl XRPC (kakaku owns vertex_kakaku_offer)."""
    import httpx

    pds_base = os.environ.get("PDS_BASE_URL", "https://atproto.etzhayyim.com")
    token = os.environ.get("INTERNAL_TRUST_TOKEN", "")
    headers = {"content-type": "application/json"}
    if token:
        headers["x-internal-trust"] = token
    written = 0
    failed = 0
    for o in state.get("offers", []):
        body = {
            "productUrl": o.get("url"),
            "merchantName": o.get("retailer"),
            "name": o.get("title"),
            "brand": o.get("brand"),
            "model": o.get("model"),
            "gtin": o.get("gtin"),
            "currency": o.get("currency") or "JPY",
            "availability": "in_stock" if o.get("in_stock") else ("out_of_stock" if o.get("in_stock") is False else None),
        }
        body = {k: v for k, v in body.items() if v is not None}
        try:
            r = httpx.post(
                f"{pds_base}/xrpc/com.etzhayyim.apps.kakaku.ingestOfferFromUrl",
                json=body,
                headers=headers,
                timeout=30.0,
            )
            if r.status_code < 300:
                written += 1
            else:
                failed += 1
        except Exception:
            failed += 1
    return {"offersByRetailer": {**state.get("offersByRetailer", {}), "_written": written, "_failed": failed}}


def write_research(state: YoroProductIngestState) -> dict:
    """Write 1 vertex_yoro_productResearch row summarizing the run."""
    from kotodama.kotoba_datomic import get_kotoba_client
    from kotodama.primitives.yoro_product import OfferCard, summarize

    offers = [OfferCard.model_validate(o) for o in state.get("offers", [])]
    summary = summarize(state["query"], state.get("category"), offers)
    actor_path = state.get("actorPath") or "research:product"
    actor_did = f"{YORO_DID_BASE}:{actor_path.replace(':', '_')}"
    job_id = state.get("jobId") or "job-unknown"
    rkey = f"{int(time.time() * 1000)}-{job_id}"
    vertex_id = f"at://{actor_did}/com.etzhayyim.apps.yoro.productResearch/{rkey}"
    now_iso = datetime.now(timezone.utc).isoformat()

    row = {
        "vertex_id": vertex_id,
        "actor_did": actor_did,
        "org_did": os.environ.get("YORO_ORG_DID", "did:erc725:etzhayyim:260425:etzhayyim"),
        "at_did": actor_did,
        "created_at": now_iso,
        "query": state["query"],
        "category": state.get("category"),
        "retailers": json.dumps(summary.retailers, ensure_ascii=False),
        "total_offers": summary.total_offers,
        "offers_by_retailer": json.dumps(summary.offers_by_retailer, ensure_ascii=False),
        "min_price_jpy": summary.min_price_jpy,
        "max_price_jpy": summary.max_price_jpy,
        "median_price_jpy": summary.median_price_jpy,
        "job_id": job_id,
    }
    try:
        get_kotoba_client().insert_row("vertex_yoro_product_research", row)
    except Exception as e:
        return {"researchVertexId": vertex_id, "ok": False, "error": f"write_research failed: {e}"}
    return {"researchVertexId": vertex_id, "ok": True}


def emit_audit(state: YoroProductIngestState) -> dict:
    try:
        from kotodama.primitives.audit import emit_audit_event  # type: ignore

        emit_audit_event(
            actor_did=YORO_DID_BASE,
            event_type="yoro.productIngest.completed",
            payload={
                "jobId": state.get("jobId"),
                "query": state.get("query"),
                "totalOffers": state.get("totalOffers", 0),
                "researchVertexId": state.get("researchVertexId"),
            },
        )
    except Exception:
        pass
    return {}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(YoroProductIngestState)
    builder.add_node("seed", seed)
    builder.add_node("fanout", fanout)
    builder.add_node("write_offers", write_offers)
    builder.add_node("write_research", write_research)
    builder.add_node("emit_audit", emit_audit)
    builder.set_entry_point("seed")
    builder.add_edge("seed", "fanout")
    builder.add_edge("fanout", "write_offers")
    builder.add_edge("write_offers", "write_research")
    builder.add_edge("write_research", "emit_audit")
    builder.add_edge("emit_audit", END)
    return builder.compile()
