"""
global_product_ingest_resident — bounded resident dispatcher for product ingest.

The Kubernetes resident trigger calls this graph repeatedly. Each run seeds any
caller-supplied frontier items, selects a bounded ready batch, dispatches
`global_product_enrich_one` runs through LangGraph Server, and advances frontier
state so the worker can run continuously without one unbounded transaction.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import os
import time
import urllib.parse
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, TypedDict


OWNER_DID = "did:web:gtin.etzhayyim.com"
ACTOR_ID = "sys.langgraph.global-product-ingest-resident"
ENRICH_ASSISTANT_ID = "global_product_enrich_one"
DEFAULT_LANGGRAPH_URL = "http://langgraph-server.mitama-udf.svc.cluster.local:8000"


class GlobalProductIngestResidentState(TypedDict, total=False):
    jobId: str
    runId: str
    maxItems: int
    leaseSeconds: int
    seedTargetCount: int
    forceSeed: bool
    useSeedInference: bool
    seedItems: list[dict[str, Any]]
    generatedSeedItems: list[dict[str, Any]]
    seeded: int
    seedError: str
    reconciled: dict[str, int]
    selected: list[dict[str, Any]]
    dispatched: list[dict[str, Any]]
    failed: list[dict[str, Any]]
    written: dict[str, int]
    ok: bool
    error: str | None


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _now_iso() -> str:
    return _now().isoformat()


def _date_iso(value: str) -> str:
    return value[:10]


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()


def _normalize_url(value: Any) -> str:
    url = str(value or "").strip()
    if not url:
        return ""
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return ""
    return urllib.parse.urlunparse(
        (
            parsed.scheme,
            parsed.netloc.lower(),
            parsed.path or "/",
            "",
            parsed.query,
            "",
        )
    )


def _frontier_id(item: dict[str, Any]) -> str:
    official = _normalize_url(item.get("officialUrl") or item.get("productUrl"))
    merchant = _normalize_url(item.get("merchantUrl"))
    gtin = "".join(ch for ch in str(item.get("gtin") or "") if ch.isdigit())
    query = str(item.get("query") or "").strip().lower()
    brand = str(item.get("brand") or "").strip().lower()
    model = str(item.get("model") or "").strip().lower()
    key = gtin or official or merchant or "|".join([query, brand, model])
    return _sha256(key or uuid.uuid4().hex)[:24]


def _clamp_int(value: Any, default: int, lo: int, hi: int) -> int:
    try:
        num = int(value)
    except Exception:
        num = default
    return max(lo, min(num, hi))


def _frontier_row(item: dict[str, Any], now: str) -> dict[str, Any]:
    frontier_id = _frontier_id(item)
    official_url = _normalize_url(item.get("officialUrl") or item.get("productUrl"))
    merchant_url = _normalize_url(item.get("merchantUrl"))
    return {
        "vertex_id": f"at://{OWNER_DID}/com.etzhayyim.apps.gtin.productIngestFrontier/{frontier_id}",
        "frontier_id": frontier_id,
        "frontier_kind": str(item.get("frontierKind") or "product_hint"),
        "query": str(item.get("query") or ""),
        "official_url": official_url,
        "merchant_url": merchant_url,
        "brand": str(item.get("brand") or ""),
        "model": str(item.get("model") or ""),
        "gtin": "".join(ch for ch in str(item.get("gtin") or "") if ch.isdigit()),
        "category": str(item.get("category") or ""),
        "locale": str(item.get("locale") or "global"),
        "country": str(item.get("country") or ""),
        "priority": _clamp_int(item.get("priority"), 100, 0, 1000),
        "attempts": 0,
        "max_attempts": _clamp_int(item.get("maxAttempts"), 5, 1, 20),
        "next_run_at": str(item.get("nextRunAt") or now),
        "last_run_id": "",
        "last_error": "",
        "evidence_json": json.dumps(item, ensure_ascii=False, sort_keys=True),
        "status": "pending",
        "created_at": now,
        "updated_at": now,
        "created_date": _date_iso(now),
        "sensitivity_ord": 0,
        "owner_did": OWNER_DID,
        "actor_id": ACTOR_ID,
    }


def _row_to_frontier(row: tuple[Any, ...]) -> dict[str, Any]:
    fields = (
        "vertex_id",
        "frontier_id",
        "frontier_kind",
        "query",
        "official_url",
        "merchant_url",
        "brand",
        "model",
        "gtin",
        "category",
        "locale",
        "country",
        "priority",
        "attempts",
        "max_attempts",
    )
    return {field: row[i] for i, field in enumerate(fields)}


def _enrich_input(item: dict[str, Any]) -> dict[str, Any]:
    official_urls = [url for url in [item.get("official_url")] if url]
    merchant_urls = [url for url in [item.get("merchant_url")] if url]
    return {
        "query": item.get("query") or "",
        "officialUrls": official_urls,
        "merchantUrls": merchant_urls,
        "brand": item.get("brand") or "",
        "model": item.get("model") or "",
        "gtin": item.get("gtin") or "",
        "category": item.get("category") or "",
        "jobId": f"product-frontier-{item.get('frontier_id')}",
        "useInference": True,
    }


def _run_status_decision(status: str) -> str:
    normalized = str(status or "").strip().lower()
    if normalized in ("success", "succeeded", "completed", "complete"):
        return "completed"
    if normalized in ("error", "failed", "failure", "cancelled", "canceled", "timeout"):
        return "retry"
    return "active"


def _fallback_seed_items(limit: int) -> list[dict[str, Any]]:
    seeds = [
        {
            "query": "Apple iPhone 15",
            "brand": "Apple",
            "model": "iPhone 15",
            "category": "electronics.smartphone",
            "country": "US",
            "officialUrl": "https://www.apple.com/iphone-15/",
            "merchantUrl": "https://www.amazon.com/s?k=Apple+iPhone+15",
            "priority": 930,
        },
        {
            "query": "Samsung Galaxy S24",
            "brand": "Samsung",
            "model": "Galaxy S24",
            "category": "electronics.smartphone",
            "country": "KR",
            "officialUrl": "https://www.samsung.com/us/smartphones/galaxy-s24/",
            "merchantUrl": "https://www.amazon.com/s?k=Samsung+Galaxy+S24",
            "priority": 910,
        },
        {
            "query": "Sony WH-1000XM5",
            "brand": "Sony",
            "model": "WH-1000XM5",
            "category": "electronics.headphones",
            "country": "JP",
            "officialUrl": "https://electronics.sony.com/audio/headphones/headband/p/wh1000xm5-b",
            "merchantUrl": "https://www.amazon.com/s?k=Sony+WH-1000XM5",
            "priority": 890,
        },
        {
            "query": "Nintendo Switch OLED Model",
            "brand": "Nintendo",
            "model": "Switch OLED Model",
            "category": "game.console",
            "country": "JP",
            "officialUrl": "https://www.nintendo.com/us/store/products/nintendo-switch-oled-model-white-set-115464/",
            "merchantUrl": "https://www.amazon.com/s?k=Nintendo+Switch+OLED",
            "priority": 870,
        },
        {
            "query": "Logitech MX Master 3S",
            "brand": "Logitech",
            "model": "MX Master 3S",
            "category": "computer.mouse",
            "country": "CH",
            "officialUrl": "https://www.logitech.com/en-us/products/mice/mx-master-3s.910-006556.html",
            "merchantUrl": "https://www.amazon.com/s?k=Logitech+MX+Master+3S",
            "priority": 850,
        },
        {
            "query": "Dyson V15 Detect",
            "brand": "Dyson",
            "model": "V15 Detect",
            "category": "home.vacuum",
            "country": "GB",
            "officialUrl": "https://www.dyson.com/vacuum-cleaners/cordless/v15/detect",
            "merchantUrl": "https://www.amazon.com/s?k=Dyson+V15+Detect",
            "priority": 830,
        },
        {
            "query": "IKEA BILLY bookcase",
            "brand": "IKEA",
            "model": "BILLY",
            "category": "home.furniture.bookcase",
            "country": "SE",
            "officialUrl": "https://www.ikea.com/us/en/p/billy-bookcase-white-00263850/",
            "merchantUrl": "https://www.ikea.com/us/en/search/?q=BILLY%20bookcase",
            "priority": 810,
        },
        {
            "query": "Kindle Paperwhite",
            "brand": "Amazon",
            "model": "Kindle Paperwhite",
            "category": "electronics.ereader",
            "country": "US",
            "officialUrl": "https://www.amazon.com/dp/B08KTZ8249",
            "merchantUrl": "https://www.amazon.com/s?k=Kindle+Paperwhite",
            "priority": 790,
        },
    ]
    return seeds[: max(0, limit)]


def _sanitize_seed_item(item: dict[str, Any], default_priority: int = 700) -> dict[str, Any] | None:
    query = str(item.get("query") or "").strip()
    brand = str(item.get("brand") or "").strip()
    model = str(item.get("model") or "").strip()
    official_url = _normalize_url(item.get("officialUrl") or item.get("productUrl"))
    merchant_url = _normalize_url(item.get("merchantUrl"))
    gtin = "".join(ch for ch in str(item.get("gtin") or "") if ch.isdigit())
    if not (query or official_url or merchant_url or gtin or brand or model):
        return None
    if gtin and len(gtin) not in (8, 12, 13, 14):
        gtin = ""
    return {
        "frontierKind": str(item.get("frontierKind") or "llm_global_product_seed"),
        "query": query or " ".join(part for part in (brand, model) if part),
        "brand": brand,
        "model": model,
        "gtin": gtin,
        "category": str(item.get("category") or ""),
        "locale": str(item.get("locale") or "global"),
        "country": str(item.get("country") or ""),
        "officialUrl": official_url,
        "merchantUrl": merchant_url,
        "priority": _clamp_int(item.get("priority"), default_priority, 0, 1000),
        "maxAttempts": _clamp_int(item.get("maxAttempts"), 4, 1, 20),
        "seedSource": str(item.get("seedSource") or "llm"),
    }


def _frontier_counts() -> dict[str, int]:

    counts = {"total": 0, "ready": 0}
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT COUNT(*) FROM vertex_product_ingest_frontier")
        row = (_res[0] if _res else None)
        counts["total"] = int(row[0] or 0) if row else 0
        _res = client.q(
            """
            SELECT COUNT(*)
            FROM vertex_product_ingest_frontier
            WHERE status IN ('pending', 'retry', 'active')
              AND attempts < max_attempts
            """
        )
        row = (_res[0] if _res else None)
        counts["ready"] = int(row[0] or 0) if row else 0
    return counts


def _generate_llm_seed_items(target_count: int) -> tuple[list[dict[str, Any]], str]:
    try:
        from kotodama import llm

        resp = llm.call_tier_json(
            "structured",
            system=(
                "Return JSON only. Generate a diverse global product ingest frontier. "
                "Each item must be a real consumer product or durable retail SKU with "
                "brand, model, category, country, officialUrl when known, and merchantUrl "
                "as a retailer or marketplace URL. Prefer manufacturer official pages for "
                "officialUrl. Do not invent GTIN values."
            ),
            user=json.dumps(
                {
                    "targetCount": target_count,
                    "requiredShape": {
                        "items": [
                            {
                                "query": "string",
                                "brand": "string",
                                "model": "string",
                                "category": "string",
                                "country": "ISO-3166 alpha-2 if known",
                                "officialUrl": "https URL if known",
                                "merchantUrl": "https URL if known",
                                "priority": "0-1000 integer",
                            }
                        ]
                    },
                    "coverageHints": [
                        "smartphones",
                        "home appliances",
                        "game consoles",
                        "computer accessories",
                        "furniture",
                        "consumer electronics",
                        "US/EU/JP/KR/CN brands",
                    ],
                },
                ensure_ascii=False,
            ),
            max_tokens=1800,
            temperature=0.2,
        )
        if not resp.get("ok") or not isinstance(resp.get("data"), dict):
            return [], str(resp.get("error") or "llm seed generation failed")
        raw_items = resp["data"].get("items")
        if not isinstance(raw_items, list):
            return [], "llm seed response missing items"
        items: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in raw_items:
            if not isinstance(raw, dict):
                continue
            item = _sanitize_seed_item(raw)
            if not item:
                continue
            key = _frontier_id(item)
            if key in seen:
                continue
            seen.add(key)
            items.append(item)
            if len(items) >= target_count:
                break
        return items, "" if items else "llm seed response contained no usable items"
    except Exception as exc:
        return [], str(exc)


def seed(state: GlobalProductIngestResidentState) -> dict[str, Any]:
    return {
        "jobId": state.get("jobId") or f"global-product-resident-{uuid.uuid4().hex[:12]}",
        "maxItems": _clamp_int(state.get("maxItems") or os.environ.get("PRODUCT_RESIDENT_MAX_ITEMS"), 10, 1, 100),
        "leaseSeconds": _clamp_int(
            state.get("leaseSeconds") or os.environ.get("PRODUCT_RESIDENT_LEASE_SECONDS"),
            3600,
            60,
            86400,
        ),
        "seedTargetCount": _clamp_int(
            state.get("seedTargetCount") or os.environ.get("PRODUCT_RESIDENT_SEED_TARGET_COUNT"),
            12,
            1,
            100,
        ),
        "useSeedInference": bool(
            state.get("useSeedInference", os.environ.get("PRODUCT_RESIDENT_USE_SEED_LLM", "1") != "0")
        ),
        "forceSeed": bool(state.get("forceSeed", False)),
        "ok": True,
        "error": None,
    }


def expand_seed_frontier(state: GlobalProductIngestResidentState) -> dict[str, Any]:
    explicit = [item for item in state.get("seedItems", []) if isinstance(item, dict)]
    if explicit and not state.get("forceSeed"):
        return {"generatedSeedItems": [], "seedError": ""}
    try:
        counts = _frontier_counts()
    except Exception as exc:
        counts = {"total": 0, "ready": 0}
        count_error = str(exc)
    else:
        count_error = ""
    if not state.get("forceSeed") and counts.get("ready", 0) > 0:
        return {"generatedSeedItems": [], "seedError": count_error}

    target_count = _clamp_int(state.get("seedTargetCount"), 12, 1, 100)
    items: list[dict[str, Any]] = []
    seed_error = count_error
    if state.get("useSeedInference", True):
        items, seed_error = _generate_llm_seed_items(target_count)
    if len(items) < max(1, min(8, target_count)):
        fallback = _fallback_seed_items(target_count - len(items))
        for item in fallback:
            item["frontierKind"] = "fallback_global_product_seed"
            item["seedSource"] = "fallback"
        items.extend(fallback)
    return {"generatedSeedItems": items[:target_count], "seedError": seed_error}


def seed_frontier(state: GlobalProductIngestResidentState) -> dict[str, Any]:
    items = [item for item in state.get("seedItems", []) if isinstance(item, dict)]
    items.extend(item for item in state.get("generatedSeedItems", []) if isinstance(item, dict))
    if not items:
        return {"seeded": 0}

    now = _now_iso()
    rows = [_frontier_row(item, now) for item in items]
    if True:
        client = get_kotoba_client()
        for row in rows:
            _res = client.q("DELETE FROM vertex_product_ingest_frontier WHERE vertex_id = %s", (row["vertex_id"],))
            _res = client.q(
                """
                INSERT INTO vertex_product_ingest_frontier
                  (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                   frontier_id, frontier_kind, query, official_url, merchant_url,
                   brand, model, gtin, category, locale, country, priority,
                   attempts, max_attempts, next_run_at, last_run_id, last_error,
                   evidence_json, status, created_at, updated_at, actor_id)
                VALUES
                  (%(vertex_id)s, 0, %(created_date)s, %(sensitivity_ord)s, %(owner_did)s,
                   %(frontier_id)s, %(frontier_kind)s, %(query)s, %(official_url)s, %(merchant_url)s,
                   %(brand)s, %(model)s, %(gtin)s, %(category)s, %(locale)s, %(country)s, %(priority)s,
                   %(attempts)s, %(max_attempts)s, %(next_run_at)s, %(last_run_id)s, %(last_error)s,
                   %(evidence_json)s, %(status)s, %(created_at)s, %(updated_at)s, %(actor_id)s)
                """,
                row,
            )
    return {"seeded": len(rows)}


def _get_langgraph_run(run_id: str) -> tuple[bool, dict[str, Any]]:
    import httpx

    base = os.environ.get("LANGGRAPH_URL") or os.environ.get("LANGGRAPH_SERVER_URL") or DEFAULT_LANGGRAPH_URL
    timeout = float(os.environ.get("PRODUCT_RESIDENT_HTTP_TIMEOUT", "20"))
    resp = httpx.get(f"{base.rstrip('/')}/runs/{run_id}", timeout=timeout)
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text[:500]}
    return resp.status_code < 300, data


def reconcile_active_runs(state: GlobalProductIngestResidentState) -> dict[str, Any]:

    limit = _clamp_int((state.get("maxItems") or 10) * 2, 20, 1, 200)
    now = _now_iso()
    lease_until = (_now() + timedelta(seconds=int(state.get("leaseSeconds") or 3600))).isoformat()
    rows: list[tuple[str, str, int, int]] = []
    counts = {"completed": 0, "active": 0, "retry": 0, "inspectFailed": 0}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, last_run_id, attempts, max_attempts
            FROM vertex_product_ingest_frontier
            WHERE status = 'active'
              AND last_run_id <> ''
            ORDER BY updated_at ASC
            LIMIT {limit}
            """,
        )
        rows = [(str(row[0]), str(row[1]), int(row[2] or 0), int(row[3] or 1)) for row in _res]

        for vertex_id, run_id, attempts, max_attempts in rows:
            try:
                ok, data = _get_langgraph_run(run_id)
            except Exception as exc:
                ok, data = False, {"error": str(exc)}
            if not ok:
                counts["inspectFailed"] += 1
                _res = client.q(
                    """
                    UPDATE vertex_product_ingest_frontier
                    SET last_error = %s,
                        next_run_at = %s,
                        updated_at = %s
                    WHERE vertex_id = %s
                    """,
                    (json.dumps(data, ensure_ascii=False)[:1000], lease_until, now, vertex_id),
                )
                continue
            decision = _run_status_decision(str(data.get("status") or ""))
            if decision == "completed":
                counts["completed"] += 1
                _res = client.q(
                    """
                    UPDATE vertex_product_ingest_frontier
                    SET status = 'completed',
                        last_error = '',
                        next_run_at = %s,
                        updated_at = %s
                    WHERE vertex_id = %s
                    """,
                    (lease_until, now, vertex_id),
                )
                _res = client.q(
                    """
                    UPDATE vertex_product_ingest_run
                    SET status = 'completed',
                        result_json = %s,
                        finished_at = %s,
                        updated_at = %s
                    WHERE dispatched_run_id = %s
                    """,
                    (json.dumps(data, ensure_ascii=False), now, now, run_id),
                )
            elif decision == "retry":
                next_status = "dead" if attempts >= max_attempts else "retry"
                counts["retry"] += 1
                _res = client.q(
                    """
                    UPDATE vertex_product_ingest_frontier
                    SET status = %s,
                        last_error = %s,
                        next_run_at = %s,
                        updated_at = %s
                    WHERE vertex_id = %s
                    """,
                    (next_status, json.dumps(data, ensure_ascii=False)[:1000], lease_until, now, vertex_id),
                )
                _res = client.q(
                    """
                    UPDATE vertex_product_ingest_run
                    SET status = %s,
                        result_json = %s,
                        finished_at = %s,
                        updated_at = %s
                    WHERE dispatched_run_id = %s
                    """,
                    (next_status, json.dumps(data, ensure_ascii=False)[:4000], now, now, run_id),
                )
            else:
                counts["active"] += 1
                _res = client.q(
                    """
                    UPDATE vertex_product_ingest_frontier
                    SET next_run_at = %s,
                        updated_at = %s
                    WHERE vertex_id = %s
                    """,
                    (lease_until, now, vertex_id),
                )
                _res = client.q(
                    """
                    UPDATE vertex_product_ingest_run
                    SET status = 'active',
                        result_json = %s,
                        updated_at = %s
                    WHERE dispatched_run_id = %s
                    """,
                    (json.dumps(data, ensure_ascii=False)[:4000], now, run_id),
                )
    return {"reconciled": counts}


def select_next_batch(state: GlobalProductIngestResidentState) -> dict[str, Any]:

    limit = _clamp_int(state.get("maxItems"), 10, 1, 100)
    now = _now_iso()
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, frontier_id, frontier_kind, query, official_url,
                   merchant_url, brand, model, gtin, category, locale, country,
                   priority, attempts, max_attempts
            FROM vertex_product_ingest_frontier
            WHERE status IN ('pending', 'retry', 'active')
              AND attempts < max_attempts
              AND next_run_at <= %s
            ORDER BY priority DESC, next_run_at ASC, updated_at ASC
            LIMIT {limit}
            """,
            (now,),
        )
        selected = [_row_to_frontier(row) for row in _res]
    return {"selected": selected}


def _post_langgraph_run(input_data: dict[str, Any]) -> tuple[bool, dict[str, Any]]:
    import httpx

    base = os.environ.get("LANGGRAPH_URL") or os.environ.get("LANGGRAPH_SERVER_URL") or DEFAULT_LANGGRAPH_URL
    timeout = float(os.environ.get("PRODUCT_RESIDENT_HTTP_TIMEOUT", "20"))
    resp = httpx.post(
        f"{base.rstrip('/')}/runs",
        json={"assistant_id": ENRICH_ASSISTANT_ID, "input": input_data},
        headers={"content-type": "application/json"},
        timeout=timeout,
    )
    try:
        data = resp.json()
    except Exception:
        data = {"text": resp.text[:500]}
    return resp.status_code < 300, data


def dispatch_enrich_runs(state: GlobalProductIngestResidentState) -> dict[str, Any]:
    dispatched: list[dict[str, Any]] = []
    failed: list[dict[str, Any]] = []
    for item in state.get("selected", []):
        input_data = _enrich_input(item)
        try:
            ok, data = _post_langgraph_run(input_data)
        except Exception as exc:
            ok, data = False, {"error": str(exc)}
        result = {
            "frontierVid": item.get("vertex_id"),
            "frontierId": item.get("frontier_id"),
            "input": input_data,
            "response": data,
            "ok": ok,
            "runId": data.get("run_id") if isinstance(data, dict) else "",
        }
        (dispatched if ok else failed).append(result)
    return {"dispatched": dispatched, "failed": failed}


def update_frontier_status(state: GlobalProductIngestResidentState) -> dict[str, Any]:

    now = _now_iso()
    lease_until = (_now() + timedelta(seconds=int(state.get("leaseSeconds") or 3600))).isoformat()
    updated = 0
    run_rows = []
    if True:
        client = get_kotoba_client()
        for item in state.get("dispatched", []):
            run_id = str(item.get("runId") or "")
            frontier_vid = str(item.get("frontierVid") or "")
            _res = client.q(
                """
                UPDATE vertex_product_ingest_frontier
                SET status = 'active',
                    attempts = attempts + 1,
                    last_run_id = %s,
                    last_error = '',
                    next_run_at = %s,
                    updated_at = %s
                WHERE vertex_id = %s
                """,
                (run_id, lease_until, now, frontier_vid),
            )
            updated += 1
            run_rows.append((item, "active"))
        for item in state.get("failed", []):
            frontier_vid = str(item.get("frontierVid") or "")
            error = json.dumps(item.get("response") or {}, ensure_ascii=False)[:1000]
            _res = client.q(
                """
                UPDATE vertex_product_ingest_frontier
                SET status = 'retry',
                    attempts = attempts + 1,
                    last_error = %s,
                    next_run_at = %s,
                    updated_at = %s
                WHERE vertex_id = %s
                """,
                (error, lease_until, now, frontier_vid),
            )
            updated += 1
            run_rows.append((item, "dispatch_failed"))
        for item, status in run_rows:
            run_id = str(item.get("runId") or uuid.uuid4().hex)
            vertex_id = f"at://{OWNER_DID}/com.etzhayyim.apps.gtin.productIngestRun/{_sha256(str(item.get('frontierVid')) + '|' + run_id)[:24]}"
            _res = client.q("DELETE FROM vertex_product_ingest_run WHERE vertex_id = %s", (vertex_id,))
            _res = client.q(
                """
                INSERT INTO vertex_product_ingest_run
                  (vertex_id, _seq, created_date, sensitivity_ord, owner_did,
                   run_id, parent_run_id, frontier_vid, assistant_id,
                   dispatched_run_id, input_json, result_json, status,
                   started_at, finished_at, created_at, updated_at, actor_id)
                VALUES
                  (%s, 0, %s, 0, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    vertex_id,
                    _date_iso(now),
                    OWNER_DID,
                    run_id,
                    state.get("jobId") or "",
                    item.get("frontierVid") or "",
                    ENRICH_ASSISTANT_ID,
                    item.get("runId") or "",
                    json.dumps(item.get("input") or {}, ensure_ascii=False),
                    json.dumps(item.get("response") or {}, ensure_ascii=False),
                    status,
                    now,
                    now,
                    now,
                    now,
                    ACTOR_ID,
                ),
            )
    return {"written": {"frontierUpdated": updated, "runRows": len(run_rows)}}


def emit_audit(state: GlobalProductIngestResidentState) -> dict[str, Any]:
    try:
        from kotodama.primitives.audit import emit_audit_event  # type: ignore

        emit_audit_event(
            actor_did=OWNER_DID,
            event_type="globalProduct.ingestResident.completed",
            payload={
                "jobId": state.get("jobId"),
                "seeded": state.get("seeded", 0),
                "generatedSeedItems": len(state.get("generatedSeedItems", [])),
                "seedError": state.get("seedError", ""),
                "reconciled": state.get("reconciled", {}),
                "selected": len(state.get("selected", [])),
                "dispatched": len(state.get("dispatched", [])),
                "failed": len(state.get("failed", [])),
                "written": state.get("written"),
                "error": state.get("error"),
            },
        )
    except Exception as exc:
        return {"auditError": str(exc)}
    return {}


def build_graph():
    from langgraph.graph import END, StateGraph

    builder = StateGraph(GlobalProductIngestResidentState)
    builder.add_node("seed", seed)
    builder.add_node("expand_seed_frontier", expand_seed_frontier)
    builder.add_node("seed_frontier", seed_frontier)
    builder.add_node("reconcile_active_runs", reconcile_active_runs)
    builder.add_node("select_next_batch", select_next_batch)
    builder.add_node("dispatch_enrich_runs", dispatch_enrich_runs)
    builder.add_node("update_frontier_status", update_frontier_status)
    builder.add_node("emit_audit", emit_audit)
    builder.set_entry_point("seed")
    builder.add_edge("seed", "expand_seed_frontier")
    builder.add_edge("expand_seed_frontier", "seed_frontier")
    builder.add_edge("seed_frontier", "reconcile_active_runs")
    builder.add_edge("reconcile_active_runs", "select_next_batch")
    builder.add_edge("select_next_batch", "dispatch_enrich_runs")
    builder.add_edge("dispatch_enrich_runs", "update_frontier_status")
    builder.add_edge("update_frontier_status", "emit_audit")
    builder.add_edge("emit_audit", END)
    return builder.compile()
