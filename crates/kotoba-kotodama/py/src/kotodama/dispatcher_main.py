"""
F4 — generic XRPC dispatcher for BPMN-contract actors (ADR-0049 follow-on).

Single HTTP server that owns the entire T1/T2 actor surface:

    POST /xrpc/{nsid}              — kick a BPMN process named by the
                                      vertex_bpmn_lexicon_binding row
                                      for `nsid`. Body becomes the
                                      starting variables. Returns the
                                      instance result variables JSON.

    GET  /health                   — liveness
    GET  /bindings                 — authenticated debug: list known
                                      nsid → process_id
    GET  /xrpc/{nsid}              — convenience for parameterless
                                      lookups; same as POST with empty body

Auth: gated by the `DISPATCHER_AUTH_MODE` env var.

    off                — no auth check. Original behaviour, kept only
                         for local rollback. LB exposure at this mode
                         is a security risk — see ADR 2604231432
                         security posture.
    strict              — require header `x-internal-trust:
                         <DISPATCHER_INTERNAL_SECRET>` on every
                         `/xrpc/*` call. PDS pipethrough adds this
                         header (dispatch.ts); direct callers must
                         supply it too. Unmatched/absent → 401.

`/health` is always open. `/bindings` uses the same gate as `/xrpc/*`
because it reveals the active actor surface.

Run:
    python -m kotodama.dispatcher_main

Env:
    DISPATCHER_PORT               default 8080
    AGENTGATEWAY_MCP_URL          pod-side MCP gateway URL
    RW_URL                        required (binding lookup)
    BINDING_TTL_SEC               default 30 (in-memory cache window)
    DISPATCHER_AUTH_MODE          off | strict (default: strict)
    DISPATCHER_INTERNAL_SECRET    shared secret when mode=strict
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import json
import logging
import os
import re
import time
from typing import Any

from aiohttp import web


LOG = logging.getLogger("dispatcher")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")

PORT = int(os.environ.get("DISPATCHER_PORT", "8080"))
AGENTGATEWAY_MCP_URL = os.environ.get(
    "AGENTGATEWAY_MCP_URL",
    "http://agentgateway-mcp.mitama-udf.svc.cluster.local:8080",
)
BINDING_TTL_SEC = int(os.environ.get("BINDING_TTL_SEC", "30"))

AUTH_MODE = os.environ.get("DISPATCHER_AUTH_MODE", "strict").lower()
INTERNAL_SECRET = os.environ.get("DISPATCHER_INTERNAL_SECRET", "")
INTERNAL_TRUST_HEADER = "x-internal-trust"
PUBLIC_MALAK_PREFIX = "com.etzhayyim.apps.publicMalak."

# Yatabase pod proxy (ADR-2605111200 Option A, P59 2026-05-11).
# Cloudflared on this VKE cannot reach the lg-yatabase pod network namespace
# for reasons unknown (i/o timeout on every dial — FQDN, svc IP, pod IP,
# node IP+hostPort all fail) while bpmn-dispatcher CAN reach it. So we
# proxy the auth/leads XRPC surface through here instead of relying on the
# cloudflared origin dialing the pod directly.
LG_YATABASE_INTERNAL_URL = os.environ.get(
    "LG_YATABASE_INTERNAL_URL",
    "http://lg-yatabase.mitama-udf.svc.cluster.local:8000",
)
LG_YATABASE_PROXY_PREFIXES = (
    # Everything under the yatabase product surface is owned by the pod.
    # Specific NSIDs land on dedicated handlers; unknown ones get a clean
    # 404 from FastAPI instead of crashing here.
    "com.etzhayyim.apps.yata.",
)

# lg-animeka pod proxy (P3c 2026-05-12, same pattern as lg-yatabase).
LG_ANIMEKA_INTERNAL_URL = os.environ.get(
    "LG_ANIMEKA_INTERNAL_URL",
    "http://lg-animeka.mitama-udf.svc.cluster.local:8000",
)
LG_ANIMEKA_PROXY_PREFIXES = (
    "com.etzhayyim.apps.animeka.",
)

# lg-recap pod proxy (2026-05-12, same pattern as lg-animeka).
LG_RECAP_INTERNAL_URL = os.environ.get(
    "LG_RECAP_INTERNAL_URL",
    "http://lg-recap.mitama-udf.svc.cluster.local:8000",
)
LG_RECAP_PROXY_PREFIXES = (
    "com.etzhayyim.apps.recap.",
)

# Mangaka document persistence proxy (ghosthacker import, 2026-05-12).
# Same pattern as yatabase: lg-mangaka owns the synchronous XRPC surface for
# document save/load/list — it INSERTs straight into vertex_mangaka per
# ADR-2605111200. bpmn-dispatcher's standard langgraph path returns 202
# fire-and-forget, which doesn't match the Genko SPA's synchronous
# loadDocument contract. Narrow allowlist intentional: chat/pipelineChat/
# projectChat still flow through the Zeebe binding path until that's
# retired.
LG_MANGAKA_INTERNAL_URL = os.environ.get(
    "LG_MANGAKA_INTERNAL_URL",
    "http://lg-mangaka.mitama-udf.svc.cluster.local:8000",
)
LG_MANGAKA_PROXY_NSIDS = frozenset({
    "com.etzhayyim.apps.mangaka.saveDocument",
    "com.etzhayyim.apps.mangaka.loadDocument",
    "com.etzhayyim.apps.mangaka.listDocuments",
    "com.etzhayyim.apps.mangaka.debugCanvasState",
    "com.etzhayyim.apps.mangaka.detectFaces",
})

# lg-shinshi pod proxy (2026-05-13, Zeebe→LangGraph migration Phase A).
LG_SHINSHI_INTERNAL_URL = os.environ.get(
    "LG_SHINSHI_INTERNAL_URL",
    "http://lg-shinshi.mitama-udf.svc.cluster.local:8000",
)
LG_SHINSHI_PROXY_PREFIXES = ("com.etzhayyim.apps.shinshi.",)

# lg-narou pod proxy (2026-05-13, Zeebe→LangGraph migration Phase A).
LG_NAROU_INTERNAL_URL = os.environ.get(
    "LG_NAROU_INTERNAL_URL",
    "http://lg-narou.mitama-udf.svc.cluster.local:8000",
)
LG_NAROU_PROXY_PREFIXES = ("com.etzhayyim.apps.narou.",)

# lg-dougaka pod proxy (2026-05-13, Zeebe→LangGraph migration Phase A).
LG_DOUGAKA_INTERNAL_URL = os.environ.get(
    "LG_DOUGAKA_INTERNAL_URL",
    "http://lg-dougaka.mitama-udf.svc.cluster.local:8000",
)
LG_DOUGAKA_PROXY_PREFIXES = ("com.etzhayyim.apps.dougaka.",)

# lg-x pod proxy (2026-05-13, Zeebe→LangGraph migration Phase A).
LG_X_INTERNAL_URL = os.environ.get(
    "LG_X_INTERNAL_URL",
    "http://lg-x.mitama-udf.svc.cluster.local:8000",
)
LG_X_PROXY_PREFIXES = ("com.etzhayyim.apps.x.",)

# lg-yukkuri pod proxy (2026-05-13, Zeebe→LangGraph migration Phase A).
LG_YUKKURI_INTERNAL_URL = os.environ.get(
    "LG_YUKKURI_INTERNAL_URL",
    "http://lg-yukkuri.mitama-udf.svc.cluster.local:8000",
)
LG_YUKKURI_PROXY_PREFIXES = ("com.etzhayyim.apps.yukkuri.",)

# lg-open-jpn-mynumber pod proxy (2026-05-13, Zeebe→LangGraph migration Phase B).
LG_OPEN_JPN_MYNUMBER_INTERNAL_URL = os.environ.get(
    "LG_OPEN_JPN_MYNUMBER_INTERNAL_URL",
    "http://lg-open-jpn-mynumber.mitama-udf.svc.cluster.local:8000",
)
LG_OPEN_JPN_MYNUMBER_PROXY_PREFIXES = ("com.etzhayyim.apps.openJpnMynumber.",)

# lg-curpus2skill pod proxy (2026-05-13, Zeebe→LangGraph migration Phase B).
LG_CURPUS2SKILL_INTERNAL_URL = os.environ.get(
    "LG_CURPUS2SKILL_INTERNAL_URL",
    "http://lg-curpus2skill.mitama-udf.svc.cluster.local:8000",
)
LG_CURPUS2SKILL_PROXY_PREFIXES = ("com.etzhayyim.apps.curpus2skill.",)

# lg-pd-color pod proxy (2026-05-13, Zeebe→LangGraph migration Phase B).
LG_PD_COLOR_INTERNAL_URL = os.environ.get(
    "LG_PD_COLOR_INTERNAL_URL",
    "http://lg-pd-color.mitama-udf.svc.cluster.local:8000",
)
LG_PD_COLOR_PROXY_PREFIXES = ("com.etzhayyim.apps.pdColor.",)

# lg-karma pod proxy (2026-05-13, Zeebe→LangGraph migration Phase C).
LG_KARMA_INTERNAL_URL = os.environ.get(
    "LG_KARMA_INTERNAL_URL",
    "http://lg-karma.mitama-udf.svc.cluster.local:8000",
)
LG_KARMA_PROXY_PREFIXES = ("com.etzhayyim.apps.karma.",)

# lg-legal-entity pod proxy (2026-05-13, Zeebe→LangGraph migration Phase D).
LG_LEGAL_ENTITY_INTERNAL_URL = os.environ.get(
    "LG_LEGAL_ENTITY_INTERNAL_URL",
    "http://lg-legal-entity.mitama-udf.svc.cluster.local:8000",
)
LG_LEGAL_ENTITY_PROXY_PREFIXES = ("com.etzhayyim.apps.legalEntity.",)

# lg-organism pod proxy (2026-05-13, Zeebe→LangGraph migration Phase E).
LG_ORGANISM_INTERNAL_URL = os.environ.get(
    "LG_ORGANISM_INTERNAL_URL",
    "http://lg-organism.mitama-udf.svc.cluster.local:8000",
)
LG_ORGANISM_PROXY_PREFIXES = (
    "com.etzhayyim.apps.hakkou.",
    "com.etzhayyim.apps.kabi.",
    "com.etzhayyim.apps.ki.",
    "com.etzhayyim.apps.kinoko.",
    "com.etzhayyim.apps.kobo.",
    "com.etzhayyim.apps.koke.",
    "com.etzhayyim.apps.saikin.",
)

# maps read facade (World Monitor parity P0, 2026-05-14).
# Edge Workers must not open RisingWave connections directly; these read-heavy
# XRPCs are served by the pod-side worker API and proxied through dispatcher so
# Cloudflare only needs the existing shared-secret origin.
MAPS_LANGSERVER_INTERNAL_URL = os.environ.get(
    "MAPS_LANGSERVER_INTERNAL_URL",
    "http://zeebe-worker-api.mitama-udf.svc.cluster.local:8081",
)
MAPS_LANGSERVER_PROXY_NSIDS = frozenset({
    "com.etzhayyim.apps.maps.getDashboard",
    "com.etzhayyim.apps.maps.getLatestBrief",
    "com.etzhayyim.apps.maps.getRiskSnapshot",
    "com.etzhayyim.apps.maps.getWorldMonitorDashboard",
    "com.etzhayyim.apps.maps.listIntelAlerts",
    "com.etzhayyim.apps.maps.listIntelEvents",
    "com.etzhayyim.apps.maps.listLiveAircraft",
    "com.etzhayyim.apps.maps.listLiveSatellites",
})
MAPS_LANGSERVER_PROXY_NSIDS_LOWER = frozenset(nsid.lower() for nsid in MAPS_LANGSERVER_PROXY_NSIDS)
MAPS_LANGSERVER_PROXY_SUFFIXES = frozenset(nsid.rsplit(".", 1)[-1].lower() for nsid in MAPS_LANGSERVER_PROXY_NSIDS)
MAPS_DASHBOARD_CACHE_TTL_SEC = float(os.environ.get("MAPS_DASHBOARD_CACHE_TTL_SEC", "3600"))
_MAPS_DASHBOARD_CACHE: dict[str, Any] = {}

# ameno (browser WebGPU inference persist, ADR-2605111200, 2026-05-15).
# saveResult INSERTs into vertex_ameno_inferenceresult; listHistory SELECTs.
# Both run on ameno-langserver pod via the shared kotodama.worker_api surface.
AMENO_LANGSERVER_INTERNAL_URL = os.environ.get(
    "AMENO_LANGSERVER_INTERNAL_URL",
    "http://ameno-langserver.mitama-udf.svc.cluster.local:8081",
)
AMENO_LANGSERVER_PROXY_NSIDS = frozenset({
    "com.etzhayyim.apps.ameno.saveResult",
    "com.etzhayyim.apps.ameno.listHistory",
    "com.etzhayyim.apps.ameno.listActorAdapters",
    "com.etzhayyim.apps.ameno.listMyCredits",
})
AMENO_LANGSERVER_PROXY_NSIDS_LOWER = frozenset(nsid.lower() for nsid in AMENO_LANGSERVER_PROXY_NSIDS)


# Phase 0 dry-run: pod env pins MALAK_PHASE=0 + MALAK_LIVE_WRITE=false.
# Phase 1 (G1+G2+G3 GREEN, target 2026-08-01) flips live writes via pod env.
MALAK_LANGSERVER_INTERNAL_URL = os.environ.get(
    "MALAK_LANGSERVER_INTERNAL_URL",
)
MALAK_LANGSERVER_PROXY_NSIDS = frozenset({
    "com.etzhayyim.apps.malak.bitnestExitPursuit",
    "com.etzhayyim.apps.malak.exportSurveillanceEvidence",
    "com.etzhayyim.apps.malak.agencyOutreachFullFlow",
    "com.etzhayyim.apps.malak.draftAgencyBriefing",
})
MALAK_LANGSERVER_PROXY_NSIDS_LOWER = frozenset(nsid.lower() for nsid in MALAK_LANGSERVER_PROXY_NSIDS)

# LangGraph Server routing (ADR-2605080600 Phase 3).
# When LANGGRAPH_SERVER_URL is set and a binding has routing_target='langgraph',
# bpmn-dispatcher POSTs to /runs instead of calling Zeebe gRPC.
LANGGRAPH_SERVER_URL = os.environ.get(
    "LANGGRAPH_SERVER_URL",
    "http://langgraph-server.mitama-udf.svc.cluster.local:8000",
)


# ─── Binding cache ───────────────────────────────────────────────────────

# vertex_bpmn_lexicon_binding lookup is small but hot. Cache for a few
# seconds so a burst of XRPC traffic doesn't hammer RW.

_binding_cache: dict[str, tuple[dict[str, Any] | None, float]] = {}


def _lookup_binding_sync(nsid: str) -> dict[str, Any] | None:
    # `langgraph_url` is optional (added by ADR-2605080700 migration
    # 20260508250000); legacy clusters return NULL → falls back to the
    # global LANGGRAPH_SERVER_URL env var. We tolerate the column being
    # missing entirely so this dispatcher pod can roll out before the
    # ALTER TABLE finishes.
    select_with_url = (
        "SELECT bpmn_process_id, bpmn_version, result_timeout_ms, status, "
        "routing_target, langgraph_url "
        "FROM vertex_bpmn_lexicon_binding "
        "WHERE nsid = %s AND status = 'active' "
        "LIMIT 1"
    )
    select_legacy = (
        "SELECT bpmn_process_id, bpmn_version, result_timeout_ms, status, "
        "routing_target, NULL "
        "FROM vertex_bpmn_lexicon_binding "
        "WHERE nsid = %s AND status = 'active' "
        "LIMIT 1"
    )
    if True:
        client = get_kotoba_client()
        try:
            _res = client.q(select_with_url, (nsid,))
        except Exception:  # pragma: no cover — column-not-yet-created path
            _res = client.q(select_legacy, (nsid,))
        row = (_res[0] if _res else None)
    if not row:
        return None
    timeout_raw = row[2]
    return {
        "bpmn_process_id": row[0],
        "bpmn_version": int(row[1] or 0),
        "result_timeout_ms": 60_000 if timeout_raw is None else int(timeout_raw),
        "routing_target": row[4] or "zeebe",
        "langgraph_url": row[5] if len(row) > 5 else None,
    }


async def lookup_binding(nsid: str) -> dict[str, Any] | None:
    now = time.monotonic()
    hit = _binding_cache.get(nsid)
    if hit and (now - hit[1]) < BINDING_TTL_SEC:
        LOG.info("binding cache hit nsid=%s ageMs=%d", nsid, int((now - hit[1]) * 1000))
        return hit[0]
    try:
        binding = await asyncio.to_thread(_lookup_binding_sync, nsid)
    except Exception:
        if hit:
            LOG.warning("binding lookup failed nsid=%s; using stale cache", nsid, exc_info=True)
            return hit[0]
        raise
    _binding_cache[nsid] = (binding, now)
    return binding


# ─── HTTP handlers ───────────────────────────────────────────────────────

async def health(_request: web.Request) -> web.Response:
    return web.json_response({"status": "ok"})


async def list_bindings(_request: web.Request) -> web.Response:
    """Debug endpoint — list active bindings (no cache, fresh DB read)."""
    def _all() -> list[dict[str, Any]]:
        select_with_url = (
            "SELECT nsid, bpmn_process_id, bpmn_version, result_timeout_ms, "
            "routing_target, langgraph_url "
            "FROM vertex_bpmn_lexicon_binding "
            "WHERE status = 'active' "
            "ORDER BY nsid"
        )
        select_legacy = (
            "SELECT nsid, bpmn_process_id, bpmn_version, result_timeout_ms, "
            "routing_target, NULL "
            "FROM vertex_bpmn_lexicon_binding "
            "WHERE status = 'active' "
            "ORDER BY nsid"
        )
        if True:
            client = get_kotoba_client()
            try:
                _res = client.q(select_with_url)
            except Exception:  # pragma: no cover
                _res = client.q(select_legacy)
            return [
                {
                    "nsid": r[0],
                    "bpmnProcessId": r[1],
                    "bpmnVersion": int(r[2] or 0),
                    "resultTimeoutMs": 60_000 if r[3] is None else int(r[3]),
                    "routingTarget": r[4] or "zeebe",
                    "langgraphUrl": r[5] if len(r) > 5 else None,
                }
                for r in (_res or [])
            ]
    rows = await asyncio.to_thread(_all)
    now = time.monotonic()
    for row in rows:
        _binding_cache[str(row["nsid"])] = (
            {
                "bpmn_process_id": row["bpmnProcessId"],
                "bpmn_version": row["bpmnVersion"],
                "result_timeout_ms": row["resultTimeoutMs"],
                "routing_target": row["routingTarget"],
                "langgraph_url": row["langgraphUrl"],
            },
            now,
        )
    return web.json_response({"bindings": rows, "count": len(rows)})


def _int_param(value: Any, default: int, *, lo: int = 1, hi: int = 500) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = default
    return max(lo, min(parsed, hi))


def _bool_param(value: Any) -> bool | None:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    raw = str(value).strip().lower()
    if raw in {"1", "true", "t", "yes", "y"}:
        return True
    if raw in {"0", "false", "f", "no", "n"}:
        return False
    return None


def _permille(value: Any) -> int | None:
    if value is None or value == "":
        return None
    try:
        return int(float(value) * 1000)
    except (TypeError, ValueError):
        return None


def _request_params(request: web.Request, body: dict[str, Any] | None = None) -> dict[str, Any]:
    params = dict(body or {})
    for key, value in request.query.items():
        params.setdefault(key, value)
    return params


def _str_param(params: dict[str, Any], key: str, default: str = "") -> str:
    value = params.get(key)
    if value is None:
        return default
    return str(value).strip()


def _public_malak_search_terms(params: dict[str, Any]) -> list[str]:
    raw = params.get("searchTerms") or params.get("search_terms") or params.get("queryValue") or params.get("query")
    values = raw if isinstance(raw, list) else str(raw or "").split(",")
    return [str(value).strip() for value in values if str(value).strip()]


def _public_malak_crawl_ads_sync(params: dict[str, Any]) -> dict[str, Any]:
    from kotodama.primitives import public_malak_ads

    platform = _str_param(params, "platform")
    query_kind = _str_param(params, "queryKind", "search") or _str_param(params, "query_kind", "search")
    country = _str_param(params, "country").upper()
    search_terms = _public_malak_search_terms(params)
    seeds = [
        {
            "platform": platform,
            "queryKind": query_kind,
            "queryValue": term,
            "country": country,
        }
        for term in search_terms
    ]
    out = public_malak_ads.queue_seed_runs(seeds=seeds, limit=_int_param(params.get("limit"), 50, hi=500))
    runs = out.get("runs") if isinstance(out.get("runs"), list) else []
    first_run = runs[0] if runs and isinstance(runs[0], dict) else {}
    return {
        "scraperRunUri": first_run.get("vertexId"),
        "searchTerms": search_terms,
        "country": country or None,
        "platform": platform or None,
        "status": "queued" if int(out.get("queued") or 0) > 0 else "completed",
        "adsSeen": 0,
        "adsNew": 0,
        "adsUpdated": 0,
        "queued": int(out.get("queued") or 0),
        "skipped": int(out.get("skipped") or 0),
        "runs": runs,
    }


def _public_malak_process_scraper_queue_sync(params: dict[str, Any]) -> dict[str, Any]:
    from kotodama.primitives import public_malak_ads

    return public_malak_ads.process_queue(
        max_runs=_int_param(params.get("limit") or params.get("max") or params.get("maxRuns"), 3, hi=50),
        timeout_sec=float(_int_param(params.get("timeoutSec") or params.get("timeout_sec"), 20, lo=1, hi=600)),
        platform=_str_param(params, "platform"),
        reclaim_after_sec=_int_param(params.get("reclaimAfterSec"), 1800, lo=60, hi=86400),
    )


def _public_malak_analyze_recent_ads_sync(params: dict[str, Any]) -> dict[str, Any]:
    from kotodama.primitives import public_malak_ads

    return public_malak_ads.analyze_recent(
        limit=_int_param(params.get("limit"), 10, hi=100),
        platform=_str_param(params, "platform"),
        analysis_kind=_str_param(params, "analysisKind", "competitive") or "competitive",
        model_id=_str_param(params, "modelId"),
    )


def _public_malak_cluster_recent_ads_sync(params: dict[str, Any]) -> dict[str, Any]:
    from kotodama.primitives import public_malak_ads

    return public_malak_ads.cluster_recent(
        limit=_int_param(params.get("limit"), 25, hi=200),
        platform=_str_param(params, "platform"),
        platform_scope=_str_param(params, "platformScope", "platform") or "platform",
    )


def _public_malak_campaign_view(row: Any) -> dict[str, Any]:
    return {
        "vertexId": row[0],
        "campaignKey": row[1],
        "platformScope": row[2],
        "advertiserVertexId": row[3],
        "advertiserName": row[4],
        "landingDomain": row[5],
        "claimToken": row[6],
        "sampleHeadline": row[7],
        "sampleBodyText": row[8],
        "creativeCount": int(row[9] or 0),
        "platformCount": int(row[10] or 0),
        "firstSeenAt": row[11],
        "lastSeenAt": row[12],
        "riskScorePermille": int(row[13] or 0),
        "summary": row[14],
    }


def _public_malak_cluster_creative_view(row: Any) -> dict[str, Any]:
    return {
        "vertexId": row[0],
        "platform": row[1],
        "platformAdId": row[2],
        "advertiserName": row[3],
        "headline": row[4],
        "bodyText": row[5],
        "landingUrl": row[6],
        "lastSeenAt": row[7],
        "matchBasis": row[8],
    }


def _public_malak_scraper_run_view(row: Any) -> dict[str, Any]:
    return {
        "vertexId": row[0],
        "platform": row[1],
        "queryKind": row[2],
        "queryValue": row[3],
        "country": row[4],
        "startedAt": row[5],
        "finishedAt": row[6],
        "status": row[7],
        "adsSeen": int(row[8] or 0),
        "adsNew": int(row[9] or 0),
        "adsUpdated": int(row[10] or 0),
        "errorMessage": row[11],
        "userAgent": row[12],
        "proxyCountry": row[13],
        "playwrightTraceCid": row[14],
        "robotsTxtSnapshotCid": row[15],
        "rateLimitSleepMs": int(row[16] or 0),
    }


def _public_malak_creative_view(row: Any) -> dict[str, Any]:
    return {
        "vertexId": row[0],
        "platform": row[1],
        "platformAdId": row[2],
        "advertiserVertexId": row[3],
        "advertiserName": row[4],
        "creativeType": row[5],
        "headline": row[6],
        "bodyText": row[7],
        "ctaText": row[8],
        "landingUrl": row[9],
        "displayUrl": row[10],
        "mediaUrl": row[11],
        "mediaCid": row[12],
        "thumbnailCid": row[13],
        "languages": row[14],
        "currency": row[15],
        "impressionsMin": None if row[16] is None else int(row[16]),
        "impressionsMax": None if row[17] is None else int(row[17]),
        "spendMinPermille": _permille(row[18]),
        "spendMaxPermille": _permille(row[19]),
        "reachMin": None if row[20] is None else int(row[20]),
        "reachMax": None if row[21] is None else int(row[21]),
        "isPolitical": None if row[22] is None else bool(row[22]),
        "isActive": None if row[23] is None else bool(row[23]),
        "adDeliveryStartDate": row[24],
        "adDeliveryStopDate": row[25],
        "firstSeenAt": row[26],
        "lastSeenAt": row[27],
        "sourceUrl": row[28],
    }


def _public_malak_snapshot_view(row: Any) -> dict[str, Any]:
    return {
        "vertexId": row[0],
        "creativeVertexId": row[1],
        "platform": row[2],
        "platformAdId": row[3],
        "scraper": row[4],
        "scraperRunId": row[5],
        "scrapedAt": row[6],
        "sourceUrl": row[7],
        "httpStatus": None if row[8] is None else int(row[8]),
        "htmlCid": row[9],
        "screenshotCid": row[10],
        "harCid": row[11],
        "observedIsActive": None if row[12] is None else bool(row[12]),
        "observedImpressionsMin": None if row[13] is None else int(row[13]),
        "observedImpressionsMax": None if row[14] is None else int(row[14]),
        "observedSpendMinPermille": _permille(row[15]),
        "observedSpendMaxPermille": _permille(row[16]),
        "parserVersion": row[17],
        "parseOk": None if row[18] is None else bool(row[18]),
        "parseError": row[19],
    }


def _public_malak_advertiser_view(row: Any) -> dict[str, Any]:
    return {
        "vertexId": row[0],
        "platform": row[1],
        "platformAdvertiserId": row[2],
        "name": row[3],
        "verifiedName": row[4],
        "legalName": row[5],
        "pageUrl": row[6],
        "pageCategory": row[7],
        "country": row[8],
        "fundingEntity": row[9],
        "isPolitical": None if row[10] is None else bool(row[10]),
        "legalEntityDid": row[11],
        "firstSeenAt": row[12],
        "lastSeenAt": row[13],
    }


def _public_malak_analysis_view(row: Any) -> dict[str, Any]:
    return {
        "vertexId": row[0],
        "creativeVertexId": row[1],
        "platform": row[2],
        "platformAdId": row[3],
        "analysisKind": row[4],
        "modelId": row[5],
        "status": row[6],
        "summary": row[7],
        "riskScorePermille": None if row[8] is None else int(row[8]),
        "claimJson": row[9],
        "targetingJson": row[10],
        "signalsJson": row[11],
        "sourceSnapshotId": row[12],
        "analyzedAt": row[13],
    }


def _public_malak_creative_select_sql() -> str:
    return """
        SELECT vertex_id, platform, platform_ad_id, advertiser_vertex_id,
               advertiser_name, creative_type, headline, body_text, cta_text,
               landing_url, display_url, media_url, media_cid, thumbnail_cid,
               languages, currency, impressions_min, impressions_max,
               spend_min, spend_max, reach_min, reach_max, is_political,
               is_active, ad_delivery_start_date, ad_delivery_stop_date,
               first_seen_at, last_seen_at, source_url
        FROM vertex_ads_creative
    """


def _public_malak_analysis_select_sql() -> str:
    return """
        SELECT vertex_id, creative_vertex_id, platform, platform_ad_id,
               analysis_kind, model_id, status, summary, risk_score_permille,
               claim_json, targeting_json, signals_json, source_snapshot_id,
               analyzed_at
        FROM vertex_ads_analysis
    """


def _list_public_malak_ads_sync(params: dict[str, Any]) -> dict[str, Any]:
    limit = _int_param(params.get("limit"), 50, hi=500)
    filters: list[str] = []
    sql_params: list[Any] = []
    if params.get("platform"):
        filters.append("platform = %s")
        sql_params.append(str(params["platform"]))
    if params.get("advertiserVertexId"):
        filters.append("advertiser_vertex_id = %s")
        sql_params.append(str(params["advertiserVertexId"]))
    if params.get("country"):
        filters.append(
            "EXISTS (SELECT 1 FROM vertex_ads_snapshot s "
            "JOIN vertex_ads_scraper_run r ON r.vertex_id = s.scraper_run_id "
            "WHERE s.creative_vertex_id = vertex_ads_creative.vertex_id AND r.country = %s)"
        )
        sql_params.append(str(params["country"]).upper())
    political = _bool_param(params.get("isPolitical"))
    if political is not None:
        filters.append("is_political = %s")
        sql_params.append(political)
    active = _bool_param(params.get("isActive"))
    if active is not None:
        filters.append("is_active = %s")
        sql_params.append(active)
    if params.get("cursor"):
        filters.append("last_seen_at < %s")
        sql_params.append(str(params["cursor"]))
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            {_public_malak_creative_select_sql()}
            {where}
            ORDER BY last_seen_at DESC
            LIMIT {limit + 1}
            """,
            tuple(sql_params),
        )
        rows = _res or []
    views = [_public_malak_creative_view(row) for row in rows[:limit]]
    next_cursor = str(rows[limit][27]) if len(rows) > limit and rows[limit][27] else None
    return {"ads": views, "total": len(views), "cursor": next_cursor}


def _list_public_malak_analyses_sync(params: dict[str, Any]) -> dict[str, Any]:
    limit = _int_param(params.get("limit"), 50, hi=500)
    filters: list[str] = []
    sql_params: list[Any] = []
    if params.get("creativeVertexId"):
        filters.append("creative_vertex_id = %s")
        sql_params.append(str(params["creativeVertexId"]))
    if params.get("platform"):
        filters.append("platform = %s")
        sql_params.append(str(params["platform"]))
    if params.get("platformAdId"):
        filters.append("platform_ad_id = %s")
        sql_params.append(str(params["platformAdId"]))
    if params.get("analysisKind"):
        filters.append("analysis_kind = %s")
        sql_params.append(str(params["analysisKind"]))
    if params.get("status"):
        filters.append("status = %s")
        sql_params.append(str(params["status"]))
    if params.get("minRiskScorePermille") is not None:
        filters.append("risk_score_permille >= %s")
        sql_params.append(_int_param(params.get("minRiskScorePermille"), 0, lo=0, hi=1000))
    if params.get("cursor"):
        filters.append("analyzed_at < %s")
        sql_params.append(str(params["cursor"]))
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            {_public_malak_analysis_select_sql()}
            {where}
            ORDER BY analyzed_at DESC
            LIMIT {limit + 1}
            """,
            tuple(sql_params),
        )
        rows = _res or []
    views = [_public_malak_analysis_view(row) for row in rows[:limit]]
    next_cursor = str(rows[limit][13]) if len(rows) > limit and rows[limit][13] else None
    return {"analyses": views, "total": len(views), "cursor": next_cursor}


def _get_public_malak_analysis_sync(params: dict[str, Any]) -> dict[str, Any]:
    vertex_id = _str_param(params, "vertexId") or _str_param(params, "analysisVertexId")
    creative_vertex_id = _str_param(params, "creativeVertexId")
    analysis_kind = _str_param(params, "analysisKind")
    model_id = _str_param(params, "modelId")
    if vertex_id:
        where = "vertex_id = %s"
        sql_params: tuple[Any, ...] = (vertex_id,)
    elif creative_vertex_id and analysis_kind and model_id:
        where = "creative_vertex_id = %s AND analysis_kind = %s AND model_id = %s"
        sql_params = (creative_vertex_id, analysis_kind, model_id)
    elif creative_vertex_id and analysis_kind:
        where = "creative_vertex_id = %s AND analysis_kind = %s"
        sql_params = (creative_vertex_id, analysis_kind)
    else:
        return {"error": "vertexId or creativeVertexId+analysisKind required"}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            {_public_malak_analysis_select_sql()}
            WHERE {where}
            ORDER BY analyzed_at DESC
            LIMIT 1
            """,
            sql_params,
        )
        row = (_res[0] if _res else None)
    if not row:
        return {"error": "AnalysisNotFound"}
    return {"analysis": _public_malak_analysis_view(row)}


def _get_public_malak_creative_sync(params: dict[str, Any]) -> dict[str, Any]:
    vertex_id = _str_param(params, "vertexId")
    platform = _str_param(params, "platform")
    platform_ad_id = _str_param(params, "platformAdId")
    if vertex_id:
        where = "vertex_id = %s"
        sql_params: tuple[Any, ...] = (vertex_id,)
    elif platform and platform_ad_id:
        where = "platform = %s AND platform_ad_id = %s"
        sql_params = (platform, platform_ad_id)
    else:
        return {"error": "vertexId or platform+platformAdId required"}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            {_public_malak_creative_select_sql()}
            WHERE {where}
            LIMIT 1
            """,
            sql_params,
        )
        row = (_res[0] if _res else None)
    if not row:
        return {"error": "CreativeNotFound"}
    return {"creative": _public_malak_creative_view(row)}


def _get_public_malak_advertiser_sync(params: dict[str, Any]) -> dict[str, Any]:
    vertex_id = _str_param(params, "vertexId")
    platform = _str_param(params, "platform")
    platform_advertiser_id = _str_param(params, "platformAdvertiserId")
    if vertex_id:
        where = "vertex_id = %s"
        sql_params: tuple[Any, ...] = (vertex_id,)
    elif platform and platform_advertiser_id:
        where = "platform = %s AND platform_advertiser_id = %s"
        sql_params = (platform, platform_advertiser_id)
    else:
        return {"error": "vertexId or platform+platformAdvertiserId required"}
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, platform, platform_advertiser_id, name,
                   verified_name, legal_name, page_url, page_category, country,
                   funding_entity, is_political, legal_entity_did,
                   first_seen_at, last_seen_at
            FROM vertex_ads_advertiser
            WHERE {where}
            LIMIT 1
            """,
            sql_params,
        )
        row = (_res[0] if _res else None)
    if not row:
        return {"error": "AdvertiserNotFound"}
    return {"advertiser": _public_malak_advertiser_view(row)}


def _public_malak_analyze_ad_sync(params: dict[str, Any]) -> dict[str, Any]:
    from kotodama.primitives import public_malak_ads

    creative_vertex_id = _str_param(params, "creativeVertexId")
    if not creative_vertex_id:
        return {"error": "creativeVertexId required", "status": "failed"}
    return public_malak_ads.analyze_creative(
        creative_vertex_id=creative_vertex_id,
        analysis_kind=_str_param(params, "analysisKind", "competitive") or "competitive",
        model_id=_str_param(params, "modelId"),
    )


def _list_public_malak_snapshots_sync(params: dict[str, Any]) -> dict[str, Any]:
    limit = _int_param(params.get("limit"), 50, hi=500)
    filters: list[str] = []
    sql_params: list[Any] = []
    if params.get("creativeVertexId"):
        filters.append("creative_vertex_id = %s")
        sql_params.append(str(params["creativeVertexId"]))
    if params.get("scraperRunId"):
        filters.append("scraper_run_id = %s")
        sql_params.append(str(params["scraperRunId"]))
    if params.get("platform"):
        filters.append("platform = %s")
        sql_params.append(str(params["platform"]))
    if params.get("platformAdId"):
        filters.append("platform_ad_id = %s")
        sql_params.append(str(params["platformAdId"]))
    if params.get("cursor"):
        filters.append("scraped_at < %s")
        sql_params.append(str(params["cursor"]))
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, creative_vertex_id, platform, platform_ad_id,
                   scraper, scraper_run_id, scraped_at, source_url, http_status,
                   html_cid, screenshot_cid, har_cid, observed_is_active,
                   observed_impressions_min, observed_impressions_max,
                   observed_spend_min, observed_spend_max, parser_version,
                   parse_ok, parse_error
            FROM vertex_ads_snapshot
            {where}
            ORDER BY scraped_at DESC, vertex_id DESC
            LIMIT {limit + 1}
            """,
            tuple(sql_params),
        )
        rows = _res or []
    views = [_public_malak_snapshot_view(row) for row in rows[:limit]]
    next_cursor = str(rows[limit][6]) if len(rows) > limit and rows[limit][6] else None
    return {"snapshots": views, "cursor": next_cursor}


def _list_public_malak_scraper_runs_sync(params: dict[str, Any]) -> dict[str, Any]:
    limit = _int_param(params.get("limit"), 50, hi=500)
    filters: list[str] = []
    sql_params: list[Any] = []
    if params.get("platform"):
        filters.append("platform = %s")
        sql_params.append(str(params["platform"]))
    if params.get("status"):
        filters.append("status = %s")
        sql_params.append(str(params["status"]))
    if params.get("cursor"):
        filters.append("started_at < %s")
        sql_params.append(str(params["cursor"]))
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, platform, query_kind, query_value, country,
                   started_at, finished_at, status, ads_seen, ads_new,
                   ads_updated, error_message, user_agent, proxy_country,
                   playwright_trace_cid, robots_txt_snapshot_cid,
                   rate_limit_sleep_ms
            FROM vertex_ads_scraper_run
            {where}
            ORDER BY started_at DESC
            LIMIT {limit + 1}
            """,
            tuple(sql_params),
        )
        rows = _res or []
    views = [_public_malak_scraper_run_view(row) for row in rows[:limit]]
    next_cursor = str(rows[limit][5]) if len(rows) > limit and rows[limit][5] else None
    return {"runs": views, "cursor": next_cursor}


def _list_public_malak_campaign_clusters_sync(params: dict[str, Any]) -> dict[str, Any]:
    limit = _int_param(params.get("limit"), 50, hi=200)
    filters: list[str] = []
    sql_params: list[Any] = []
    if params.get("platformScope"):
        filters.append("platform_scope = %s")
        sql_params.append(str(params["platformScope"]))
    if params.get("advertiserVertexId"):
        filters.append("advertiser_vertex_id = %s")
        sql_params.append(str(params["advertiserVertexId"]))
    if params.get("landingDomain"):
        filters.append("landing_domain = %s")
        sql_params.append(str(params["landingDomain"]).lower())
    if params.get("minCreativeCount") is not None:
        filters.append("creative_count >= %s")
        sql_params.append(_int_param(params.get("minCreativeCount"), 1, hi=1_000_000))
    if params.get("cursor"):
        filters.append("last_seen_at < %s")
        sql_params.append(str(params["cursor"]))
    where = ("WHERE " + " AND ".join(filters)) if filters else ""
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, campaign_key, platform_scope, advertiser_vertex_id,
                   advertiser_name, landing_domain, claim_token, sample_headline,
                   sample_body_text, creative_count, platform_count, first_seen_at,
                   last_seen_at, risk_score_permille, summary
            FROM vertex_ads_campaign_cluster
            {where}
            ORDER BY last_seen_at DESC
            LIMIT {limit + 1}
            """,
            tuple(sql_params),
        )
        rows = _res or []
    views = [_public_malak_campaign_view(row) for row in rows[:limit]]
    next_cursor = str(rows[limit][12]) if len(rows) > limit and rows[limit][12] else None
    return {"clusters": views, "cursor": next_cursor}


def _get_public_malak_campaign_cluster_sync(params: dict[str, Any]) -> dict[str, Any]:
    vertex_id = str(params.get("vertexId") or "")
    campaign_key = str(params.get("campaignKey") or "")
    creative_limit = _int_param(params.get("creativeLimit"), 50, hi=200)
    analysis_limit = _int_param(params.get("analysisLimit"), 100, hi=500)
    if not vertex_id and not campaign_key:
        return {"error": "vertexId or campaignKey required"}
    if vertex_id:
        where = "vertex_id = %s"
        sql_params: tuple[Any, ...] = (vertex_id,)
    else:
        where = "campaign_key = %s"
        sql_params = (campaign_key,)
    if True:
        client = get_kotoba_client()
        _res = client.q(
            f"""
            SELECT vertex_id, campaign_key, platform_scope, advertiser_vertex_id,
                   advertiser_name, landing_domain, claim_token, sample_headline,
                   sample_body_text, creative_count, platform_count, first_seen_at,
                   last_seen_at, risk_score_permille, summary
            FROM vertex_ads_campaign_cluster
            WHERE {where}
            LIMIT 1
            """,
            sql_params,
        )
        rows = _res or []
        if not rows:
            return {"error": "CampaignClusterNotFound"}
        cluster = _public_malak_campaign_view(rows[0])
        _res = client.q(
            f"""
            SELECT c.vertex_id, c.platform, c.platform_ad_id, c.advertiser_name,
                   c.headline, c.body_text, c.landing_url, c.last_seen_at,
                   e.match_basis
            FROM edge_ads_creative_in_campaign e
            JOIN vertex_ads_creative c ON c.vertex_id = e.src_vid
            WHERE e.dst_vid = %s
            ORDER BY c.last_seen_at DESC
            LIMIT {creative_limit}
            """,
            (cluster["vertexId"],),
        )
        creative_rows = _res or []
        _res = client.q(
            f"""
            SELECT a.vertex_id, a.creative_vertex_id, a.platform, a.platform_ad_id,
                   a.analysis_kind, a.model_id, a.status, a.summary,
                   a.risk_score_permille, a.claim_json, a.targeting_json,
                   a.signals_json, a.source_snapshot_id, a.analyzed_at
            FROM edge_ads_creative_in_campaign e
            JOIN vertex_ads_analysis a ON a.creative_vertex_id = e.src_vid
            WHERE e.dst_vid = %s
            ORDER BY a.analyzed_at DESC
            LIMIT {analysis_limit}
            """,
            (cluster["vertexId"],),
        )
        analysis_rows = _res or []
    return {
        "cluster": cluster,
        "creatives": [_public_malak_cluster_creative_view(row) for row in creative_rows],
        "analyses": [_public_malak_analysis_view(row) for row in analysis_rows],
    }


async def public_malak_direct_query(request: web.Request, nsid: str, body: dict[str, Any] | None = None) -> web.Response | None:
    params = _request_params(request, body)
    if nsid == f"{PUBLIC_MALAK_PREFIX}listCampaignClusters":
        out = await asyncio.to_thread(_list_public_malak_campaign_clusters_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}getCampaignCluster":
        out = await asyncio.to_thread(_get_public_malak_campaign_cluster_sync, params)
        status = 400 if out.get("error") == "vertexId or campaignKey required" else 404 if out.get("error") else 200
        return web.json_response(out, status=status)
    if nsid == f"{PUBLIC_MALAK_PREFIX}listScraperRuns":
        out = await asyncio.to_thread(_list_public_malak_scraper_runs_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}listAds":
        out = await asyncio.to_thread(_list_public_malak_ads_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}listAnalyses":
        out = await asyncio.to_thread(_list_public_malak_analyses_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}getAnalysis":
        out = await asyncio.to_thread(_get_public_malak_analysis_sync, params)
        status = 400 if out.get("error") == "vertexId or creativeVertexId+analysisKind required" else 404 if out.get("error") else 200
        return web.json_response(out, status=status)
    if nsid == f"{PUBLIC_MALAK_PREFIX}getCreative":
        out = await asyncio.to_thread(_get_public_malak_creative_sync, params)
        status = 400 if out.get("error") == "vertexId or platform+platformAdId required" else 404 if out.get("error") else 200
        return web.json_response(out, status=status)
    if nsid == f"{PUBLIC_MALAK_PREFIX}getAdvertiser":
        out = await asyncio.to_thread(_get_public_malak_advertiser_sync, params)
        status = 400 if out.get("error") == "vertexId or platform+platformAdvertiserId required" else 404 if out.get("error") else 200
        return web.json_response(out, status=status)
    if nsid == f"{PUBLIC_MALAK_PREFIX}listSnapshots":
        out = await asyncio.to_thread(_list_public_malak_snapshots_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}crawlAds":
        out = await asyncio.to_thread(_public_malak_crawl_ads_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}processScraperQueue":
        out = await asyncio.to_thread(_public_malak_process_scraper_queue_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}analyzeRecentAds":
        out = await asyncio.to_thread(_public_malak_analyze_recent_ads_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}clusterRecentAds":
        out = await asyncio.to_thread(_public_malak_cluster_recent_ads_sync, params)
        return web.json_response(out)
    if nsid == f"{PUBLIC_MALAK_PREFIX}analyzeAd":
        out = await asyncio.to_thread(_public_malak_analyze_ad_sync, params)
        status = 400 if out.get("error") == "creativeVertexId required" else 404 if out.get("error") == "CreativeNotFound" else 200
        return web.json_response(out, status=status)
    return None




def _langgraph_request_headers() -> dict[str, str]:
    """Headers for dispatcher → LangGraph internal calls.

    The LangGraph Server currently lives behind ClusterIP, but this keeps the
    same shared-secret boundary as `/xrpc/*` when the server starts enforcing it.
    """
    headers: dict[str, str] = {}
    if INTERNAL_SECRET:
        headers[INTERNAL_TRUST_HEADER] = INTERNAL_SECRET
    return headers


def _first_str(mapping: dict[str, Any], *keys: str) -> str | None:
    for key in keys:
        value = mapping.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def _langgraph_run_payload(assistant_id: str, process_vars: dict[str, Any]) -> dict[str, Any]:
    """Build the LangGraph `/runs` payload from dispatcher process variables.

    Keep identity fields top-level so LangGraph Server can bind the run to the
    same actor/thread regardless of the graph input schema. The full process
    variables remain in `input` for graph-local logic and audit.
    """
    payload: dict[str, Any] = {
        "assistant_id": assistant_id,
        "input": process_vars,
    }
    thread_id = _first_str(process_vars, "thread_id", "threadId", "_threadId")
    actor_did = _first_str(process_vars, "actor_did", "actorDid", "_actorDid")
    if thread_id:
        payload["thread_id"] = thread_id
    if actor_did:
        payload["actor_did"] = actor_did
    config = process_vars.get("config")
    if isinstance(config, dict):
        payload["config"] = config
    return payload


async def _dispatch_langgraph(
    nsid: str,
    binding: dict[str, Any],
    process_vars: dict[str, Any],
    started: float,
    override_assistant_id: str | None = None,
) -> web.Response:
    """Route to LangGraph Server POST /runs (ADR-2605080600 Phase 3).

    The assistant_id maps from bpmn_process_id (e.g. 'shosha_agent_loop' →
    'shosha_agent_loop').  LangGraph Server returns {run_id, status} for
    background runs.  We return immediately with 202 + run_id so the caller
    can poll GET /runs/{run_id} if needed.
    """
    import aiohttp

    assistant_id = override_assistant_id or binding["bpmn_process_id"]
    # Per-binding URL override (ADR-2605080700). voxelforge ships its
    # own Helm release exposing voxelforge-langgraph.mitama-udf.svc...:8000;
    # other actors fall back to the global langgraph-server pod.
    base = (binding.get("langgraph_url") or LANGGRAPH_SERVER_URL).rstrip("/")
    url = f"{base}/runs"
    payload = _langgraph_run_payload(assistant_id, process_vars)
    headers = _langgraph_request_headers()
    timeout_ms = binding["result_timeout_ms"]

    try:
        async with aiohttp.ClientSession() as session:
            async with session.post(
                url,
                json=payload,
                headers=headers,
                timeout=aiohttp.ClientTimeout(total=max(10.0, timeout_ms / 1000.0)),
            ) as resp:
                try:
                    body = await resp.json(content_type=None)
                except Exception:
                    text = await resp.text()
                    body = {"detail": text[:500]}
                latency_ms = int((time.monotonic() - started) * 1000)
                LOG.info(
                    "langgraph dispatch nsid=%s assistant=%s run_id=%s status=%s latencyMs=%d",
                    nsid,
                    assistant_id,
                    body.get("run_id"),
                    body.get("status"),
                    latency_ms,
                )
                if resp.status >= 400:
                    return web.json_response(
                        {"error": body.get("detail", "langgraph error"),
                         "nsid": nsid, "assistant_id": assistant_id},
                        status=resp.status,
                    )
                return web.json_response({
                    "ok": True,
                    "asyncStarted": True,
                    "nsid": nsid,
                    "assistant_id": assistant_id,
                    "run_id": body.get("run_id"),
                    "thread_id": body.get("thread_id"),
                    "actor_did": payload.get("actor_did"),
                    "status": body.get("status", "pending"),
                    "latencyMs": latency_ms,
                }, status=202)
    except Exception as e:  # noqa: BLE001
        LOG.exception("langgraph dispatch failed nsid=%s", nsid)
        return web.json_response(
            {"error": f"{type(e).__name__}: {str(e)[:300]}",
             "nsid": nsid, "assistant_id": assistant_id},
            status=502,
        )


async def _dispatch_mailer_direct(nsid: str, body: dict[str, Any]) -> web.Response | None:
    """Serve mailer single-step commands synchronously.

    Dispatcher Phase G routes all generic bindings through LangGraph /runs,
    which is async and requires assistant rows. The mailer appview still has
    synchronous read surfaces (/api/stats, /api/emails), so keep this small
    direct bridge until mailer has a first-class LangGraph facade.
    """
    if not nsid.startswith("com.etzhayyim.apps.mailer."):
        return None

    op = nsid.rsplit(".", 1)[-1]
    fn_name = {
        "health": "health",
        "listEmails": "list_emails",
        "listBindings": "list_bindings",
        "stats": "stats",
        "sendEmail": "send_email",
        "provisionMailbox": "provision_mailbox",
        "handleCommit": "handle_commit",
        "heartbeat": "heartbeat",
    }.get(op)
    if not fn_name:
        return None

    def _run() -> dict[str, Any]:
        from kotodama.ingest import mailer

        fn = getattr(mailer, fn_name)
        return fn(**(body or {}))

    try:
        result = await asyncio.to_thread(_run)
        return web.json_response(result)
    except Exception as exc:  # noqa: BLE001
        LOG.exception("mailer direct dispatch failed nsid=%s", nsid)
        return web.json_response(
            {"error": f"{type(exc).__name__}: {str(exc)[:300]}", "nsid": nsid},
            status=502,
        )


async def _proxy_to_lg_yatabase(
    request: web.Request, nsid: str, body: dict[str, Any],
) -> web.Response:
    """Forward yatabase XRPC NSIDs to the lg-yatabase Granian pod.

    bpmn-dispatcher can reach the lg-yatabase pod over cluster networking;
    cloudflared currently cannot (i/o timeout on dial). The Worker still
    HMAC-signs the body with DISPATCHER_INTERNAL_SECRET, which the pod's
    `_verify_trust` also recomputes — so we forward the x-internal-trust
    header verbatim and the pod accepts it.

    CRITICAL: forward the original RAW body bytes, not a re-serialized
    json.dumps(body). The pod recomputes HMAC over the raw bytes, so any
    re-serialization changes the digest and the pod returns 401.
    """
    import aiohttp as _aiohttp
    target = f"{LG_YATABASE_INTERNAL_URL.rstrip('/')}/xrpc/{nsid}"
    method = request.method
    headers: dict[str, str] = {}
    # Forward HMAC + identity + trace headers verbatim.
    for h in (
        INTERNAL_TRUST_HEADER,
        "x-etzhayyim-actor-did",
        "x-etzhayyim-org-did",
        "x-etzhayyim-trace-id",
        "content-type",
    ):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    started = time.monotonic()
    try:
        async with _aiohttp.ClientSession() as session:
            if method == "GET":
                # GET params travel as querystring on the proxied request.
                params = {k: v for k, v in request.query.items()}
                async with session.get(
                    target,
                    params=params,
                    headers=headers,
                    timeout=_aiohttp.ClientTimeout(total=30),
                ) as resp:
                    raw = await resp.read()
                    LOG.info(
                        "lg-yatabase proxy GET nsid=%s status=%s ms=%d",
                        nsid, resp.status, int((time.monotonic() - started) * 1000),
                    )
                    ct = (resp.headers.get("content-type") or "application/json").split(";")[0].strip()
                    return web.Response(status=resp.status, body=raw, content_type=ct)
            # POST: forward the exact bytes the Worker signed (the body was
            # already buffered by auth_middleware's `request.read()`).
            try:
                payload = await request.read()
            except Exception:
                payload = json.dumps(body).encode()
            async with session.post(
                target,
                data=payload,
                headers=headers,
                timeout=_aiohttp.ClientTimeout(total=30),
            ) as resp:
                raw = await resp.read()
                LOG.info(
                    "lg-yatabase proxy POST nsid=%s status=%s ms=%d",
                    nsid, resp.status, int((time.monotonic() - started) * 1000),
                )
                ct = (resp.headers.get("content-type") or "application/json").split(";")[0].strip()
                return web.Response(status=resp.status, body=raw, content_type=ct)
    except _aiohttp.ClientError as exc:
        LOG.exception("lg-yatabase proxy failed nsid=%s err=%s", nsid, exc)
        return web.json_response(
            {"error": "ProxyFailed", "message": str(exc)[:300], "nsid": nsid},
            status=502,
        )
    except asyncio.TimeoutError:
        return web.json_response(
            {"error": "ProxyTimeout", "nsid": nsid}, status=504,
        )


async def _proxy_to_lg_animeka(
    request: web.Request, nsid: str, body: dict[str, Any],
) -> web.Response:
    """Forward animeka XRPC NSIDs to the lg-animeka LangGraph pod (P3c 2026-05-12)."""
    import aiohttp as _aiohttp
    target = f"{LG_ANIMEKA_INTERNAL_URL.rstrip('/')}/xrpc/{nsid}"
    method = request.method
    headers: dict[str, str] = {}
    for h in (
        INTERNAL_TRUST_HEADER,
        "x-etzhayyim-actor-did",
        "x-etzhayyim-org-did",
        "x-etzhayyim-trace-id",
        "content-type",
    ):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    started = time.monotonic()
    try:
        async with _aiohttp.ClientSession() as session:
            if method == "GET":
                params = {k: v for k, v in request.query.items()}
                async with session.get(
                    target,
                    params=params,
                    headers=headers,
                    timeout=_aiohttp.ClientTimeout(total=30),
                ) as resp:
                    raw = await resp.read()
                    LOG.info(
                        "lg-animeka proxy GET nsid=%s status=%s ms=%d",
                        nsid, resp.status, int((time.monotonic() - started) * 1000),
                    )
                    return web.Response(
                        status=resp.status, body=raw,
                        content_type=resp.headers.get("content-type", "application/json"),
                    )
            try:
                payload = await request.read()
            except Exception:
                payload = json.dumps(body).encode()
            async with session.post(
                target,
                data=payload,
                headers=headers,
                timeout=_aiohttp.ClientTimeout(total=30),
            ) as resp:
                raw = await resp.read()
                LOG.info(
                    "lg-animeka proxy POST nsid=%s status=%s ms=%d",
                    nsid, resp.status, int((time.monotonic() - started) * 1000),
                )
                return web.Response(
                    status=resp.status, body=raw,
                    content_type=resp.headers.get("content-type", "application/json"),
                )
    except _aiohttp.ClientError as exc:
        LOG.exception("lg-animeka proxy failed nsid=%s err=%s", nsid, exc)
        return web.json_response(
            {"error": "ProxyFailed", "message": str(exc)[:300], "nsid": nsid},
            status=502,
        )
    except asyncio.TimeoutError:
        return web.json_response(
            {"error": "ProxyTimeout", "nsid": nsid}, status=504,
        )


async def _proxy_to_lg_recap(
    request: web.Request, nsid: str, body: dict[str, Any],
) -> web.Response:
    """Forward recap XRPC NSIDs to the lg-recap LangGraph pod (2026-05-12)."""
    import aiohttp as _aiohttp
    target = f"{LG_RECAP_INTERNAL_URL.rstrip('/')}/xrpc/{nsid}"
    method = request.method
    headers: dict[str, str] = {}
    for h in (
        INTERNAL_TRUST_HEADER,
        "x-etzhayyim-actor-did",
        "x-etzhayyim-org-did",
        "x-etzhayyim-trace-id",
        "content-type",
    ):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    started = time.monotonic()
    try:
        async with _aiohttp.ClientSession() as session:
            if method == "GET":
                params = {k: v for k, v in request.query.items()}
                async with session.get(
                    target,
                    params=params,
                    headers=headers,
                    timeout=_aiohttp.ClientTimeout(total=60),
                ) as resp:
                    raw = await resp.read()
                    LOG.info(
                        "lg-recap proxy GET nsid=%s status=%s ms=%d",
                        nsid, resp.status, int((time.monotonic() - started) * 1000),
                    )
                    return web.Response(
                        status=resp.status, body=raw,
                        content_type=resp.headers.get("content-type", "application/json"),
                    )
            try:
                payload = await request.read()
            except Exception:
                payload = json.dumps(body).encode()
            async with session.post(
                target,
                data=payload,
                headers=headers,
                timeout=_aiohttp.ClientTimeout(total=60),
            ) as resp:
                raw = await resp.read()
                LOG.info(
                    "lg-recap proxy POST nsid=%s status=%s ms=%d",
                    nsid, resp.status, int((time.monotonic() - started) * 1000),
                )
                return web.Response(
                    status=resp.status, body=raw,
                    content_type=resp.headers.get("content-type", "application/json"),
                )
    except _aiohttp.ClientError as exc:
        LOG.exception("lg-recap proxy failed nsid=%s err=%s", nsid, exc)
        return web.json_response(
            {"error": "ProxyFailed", "message": str(exc)[:300], "nsid": nsid},
            status=502,
        )
    except asyncio.TimeoutError:
        return web.json_response(
            {"error": "ProxyTimeout", "nsid": nsid}, status=504,
        )


async def _proxy_to_lg_mangaka(
    request: web.Request, nsid: str, body: dict[str, Any],
) -> web.Response:
    """Forward mangaka XRPC NSIDs to the lg-mangaka LangGraph pod (2026-05-12)."""
    import aiohttp as _aiohttp
    target = f"{LG_MANGAKA_INTERNAL_URL.rstrip('/')}/xrpc/{nsid}"
    method = request.method
    headers: dict[str, str] = {}
    for h in (
        INTERNAL_TRUST_HEADER,
        "x-etzhayyim-actor-did",
        "x-etzhayyim-org-did",
        "x-etzhayyim-trace-id",
        "content-type",
    ):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    started = time.monotonic()
    try:
        async with _aiohttp.ClientSession() as session:
            if method == "GET":
                params = {k: v for k, v in request.query.items()}
                async with session.get(
                    target,
                    params=params,
                    headers=headers,
                    timeout=_aiohttp.ClientTimeout(total=30),
                ) as resp:
                    raw = await resp.read()
                    LOG.info(
                        "lg-mangaka proxy GET nsid=%s status=%s ms=%d",
                        nsid, resp.status, int((time.monotonic() - started) * 1000),
                    )
                    return web.Response(
                        status=resp.status, body=raw,
                        content_type=resp.headers.get("content-type", "application/json"),
                    )
            try:
                payload = await request.read()
            except Exception:
                payload = json.dumps(body).encode()
            async with session.post(
                target,
                data=payload,
                headers=headers,
                timeout=_aiohttp.ClientTimeout(total=30),
            ) as resp:
                raw = await resp.read()
                LOG.info(
                    "lg-mangaka proxy POST nsid=%s status=%s ms=%d",
                    nsid, resp.status, int((time.monotonic() - started) * 1000),
                )
                return web.Response(
                    status=resp.status, body=raw,
                    content_type=resp.headers.get("content-type", "application/json"),
                )
    except _aiohttp.ClientError as exc:
        LOG.exception("lg-mangaka proxy failed nsid=%s err=%s", nsid, exc)
        return web.json_response(
            {"error": "ProxyFailed", "message": str(exc)[:300], "nsid": nsid},
            status=502,
        )
    except asyncio.TimeoutError:
        return web.json_response(
            {"error": "ProxyTimeout", "nsid": nsid}, status=504,
        )


async def _proxy_to_lg_pod_sse(
    request: web.Request,
    nsid: str,
    internal_url: str,
    pod_name: str,
) -> web.StreamResponse:
    """Stream-pass SSE response from an lg-* pod without buffering.

    Used for com.etzhayyim.apps.ameno.subscribeBriefs (NATS firehose → browser).
    Connection lifetime is bounded by the pod (idleTimeoutSec / maxEvents);
    we just relay chunks until the upstream closes.
    """
    import aiohttp as _aiohttp
    target = f"{internal_url.rstrip('/')}/xrpc/{nsid}"
    headers: dict[str, str] = {"accept": "text/event-stream"}
    for h in (INTERNAL_TRUST_HEADER, "x-etzhayyim-actor-did", "x-etzhayyim-org-did", "x-etzhayyim-trace-id"):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    params = {k: v for k, v in request.query.items()}
    timeout = _aiohttp.ClientTimeout(total=None, sock_read=None)
    started = time.monotonic()
    resp_stream = web.StreamResponse(
        status=200,
        headers={
            "content-type": "text/event-stream",
            "cache-control": "no-cache, no-transform",
            "x-accel-buffering": "no",
            "connection": "keep-alive",
        },
    )
    await resp_stream.prepare(request)
    try:
        async with _aiohttp.ClientSession() as session:
            async with session.get(target, params=params, headers=headers, timeout=timeout) as resp:
                LOG.info("%s sse-proxy nsid=%s status=%s", pod_name, nsid, resp.status)
                async for chunk in resp.content.iter_chunked(4096):
                    if not chunk:
                        continue
                    await resp_stream.write(chunk)
    except Exception as exc:  # noqa: BLE001
        LOG.warning("%s sse-proxy error nsid=%s exc=%s", pod_name, nsid, exc)
        try:
            await resp_stream.write(
                f"event: error\ndata: {json.dumps({'error': str(exc)})}\n\n".encode()
            )
        except Exception:
            pass
    finally:
        elapsed_ms = int((time.monotonic() - started) * 1000)
        LOG.info("%s sse-proxy closed nsid=%s ms=%d", pod_name, nsid, elapsed_ms)
        await resp_stream.write_eof()
    return resp_stream


async def _proxy_to_lg_pod(
    request: web.Request,
    nsid: str,
    body: dict[str, Any],
    internal_url: str,
    pod_name: str,
    timeout: float = 60,
) -> web.Response:
    """Generic proxy to any lg-* LangGraph pod (Zeebe→LangGraph Phase A, 2026-05-13)."""
    import aiohttp as _aiohttp
    target = f"{internal_url.rstrip('/')}/xrpc/{nsid}"
    method = request.method
    cache_key = ""
    if pod_name == "maps-langserver" and nsid == "com.etzhayyim.apps.maps.getWorldMonitorDashboard" and method == "POST":
        cache_key = nsid
        cached = _MAPS_DASHBOARD_CACHE.get(cache_key)
        if cached and (time.monotonic() - float(cached["stored_at"])) <= MAPS_DASHBOARD_CACHE_TTL_SEC:
            return web.Response(
                status=200,
                body=cached["body"],
                content_type=cached.get("content_type") or "application/json",
            )
    headers: dict[str, str] = {}
    for h in (
        INTERNAL_TRUST_HEADER,
        "x-etzhayyim-actor-did",
        "x-etzhayyim-org-did",
        "x-etzhayyim-trace-id",
        "content-type",
    ):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    started = time.monotonic()
    try:
        async with _aiohttp.ClientSession() as session:
            if method == "GET":
                params = {k: v for k, v in request.query.items()}
                async with session.get(
                    target, params=params, headers=headers,
                    timeout=_aiohttp.ClientTimeout(total=timeout),
                ) as resp:
                    raw = await resp.read()
                    LOG.info(
                        "%s proxy GET nsid=%s status=%s ms=%d",
                        pod_name, nsid, resp.status,
                        int((time.monotonic() - started) * 1000),
                    )
                    return web.Response(
                        status=resp.status, body=raw,
                        content_type=resp.headers.get("content-type", "application/json"),
                    )
            try:
                payload = await request.read()
            except Exception:
                payload = json.dumps(body).encode()
            async with session.post(
                target, data=payload, headers=headers,
                timeout=_aiohttp.ClientTimeout(total=timeout),
            ) as resp:
                raw = await resp.read()
                if cache_key and resp.status == 200:
                    _MAPS_DASHBOARD_CACHE[cache_key] = {
                        "stored_at": time.monotonic(),
                        "body": raw,
                        "content_type": resp.headers.get("content-type", "application/json"),
                    }
                LOG.info(
                    "%s proxy POST nsid=%s status=%s ms=%d",
                    pod_name, nsid, resp.status,
                    int((time.monotonic() - started) * 1000),
                )
                return web.Response(
                    status=resp.status, body=raw,
                    content_type=resp.headers.get("content-type", "application/json"),
                )
    except _aiohttp.ClientError as exc:
        LOG.exception("%s proxy failed nsid=%s err=%s", pod_name, nsid, exc)
        return web.json_response(
            {"error": "ProxyFailed", "message": str(exc)[:300], "nsid": nsid},
            status=502,
        )
    except asyncio.TimeoutError:
        return web.json_response(
            {"error": "ProxyTimeout", "nsid": nsid}, status=504,
        )


async def mcp_route(request: web.Request) -> web.Response:
    """POST /mcp — MCP JSON-RPC facade for pod-owned tools.

    Tool names intentionally use the same Lexicon NSID strings as the XRPC
    surface. Phase 1 routes Shinshi through the lg-shinshi pod MCP endpoint;
    other app namespaces can be added here or moved behind a registry-backed
    router without changing edge callers.
    """
    try:
        body = await request.json()
    except json.JSONDecodeError as exc:
        return web.json_response(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": f"invalid JSON body: {exc}"}},
            status=400,
        )
    if not isinstance(body, dict):
        return web.json_response(
            {"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "body must be a JSON object"}},
            status=400,
        )

    method = str(body.get("method") or "")
    params = body.get("params")
    tool_name = ""
    if isinstance(params, dict):
        tool_name = str(params.get("name") or "")

    if method == "tools/call" and not tool_name.startswith("com.etzhayyim.apps.shinshi."):
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {
                    "code": -32601,
                    "message": f"no MCP route for tool {tool_name!r}",
                },
            },
            status=404,
        )

    import aiohttp as _aiohttp
    target = f"{LG_SHINSHI_INTERNAL_URL.rstrip('/')}/mcp"
    headers: dict[str, str] = {"content-type": "application/json"}
    for h in (
        INTERNAL_TRUST_HEADER,
        "x-etzhayyim-actor-did",
        "x-etzhayyim-org-did",
        "x-etzhayyim-trace-id",
    ):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    started = time.monotonic()
    try:
        async with _aiohttp.ClientSession() as session:
            async with session.post(
                target,
                data=json.dumps(body).encode("utf-8"),
                headers=headers,
                timeout=_aiohttp.ClientTimeout(total=60),
            ) as resp:
                raw = await resp.read()
                LOG.info(
                    "mcp proxy method=%s tool=%s target=lg-shinshi status=%s ms=%d",
                    method,
                    tool_name,
                    resp.status,
                    int((time.monotonic() - started) * 1000),
                )
                content_type = (resp.headers.get("content-type") or "application/json").split(";")[0].strip()
                return web.Response(status=resp.status, body=raw, content_type=content_type)
    except _aiohttp.ClientError as exc:
        LOG.exception("mcp proxy failed method=%s tool=%s err=%s", method, tool_name, exc)
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32000, "message": f"MCP proxy failed: {str(exc)[:300]}"},
            },
            status=502,
        )
    except asyncio.TimeoutError:
        return web.json_response(
            {
                "jsonrpc": "2.0",
                "id": body.get("id"),
                "error": {"code": -32001, "message": "MCP proxy timeout"},
            },
            status=504,
        )


async def _proxy_to_lg_mangaka(
    request: web.Request, nsid: str, body: dict[str, Any],
) -> web.Response:
    """Forward mangaka document XRPC NSIDs to the lg-mangaka pod.

    Same shape as _proxy_to_lg_yatabase: bpmn-dispatcher reaches the pod
    over cluster networking (cloudflared path rules in this remotely-
    managed tunnel don't route externally) and forwards the synchronous
    XRPC call. lg-mangaka's /xrpc/{nsid} surface is unauthenticated
    (trusted at the edge), so we forward x-internal-trust verbatim but
    the pod itself does not verify it.
    """
    import aiohttp as _aiohttp
    target = f"{LG_MANGAKA_INTERNAL_URL.rstrip('/')}/xrpc/{nsid}"
    method = request.method
    headers: dict[str, str] = {}
    for h in (
        INTERNAL_TRUST_HEADER,
        "x-etzhayyim-actor-did",
        "x-etzhayyim-org-did",
        "x-etzhayyim-trace-id",
        "content-type",
    ):
        v = request.headers.get(h)
        if v is not None:
            headers[h] = v
    started = time.monotonic()
    try:
        async with _aiohttp.ClientSession() as session:
            if method == "GET":
                params = {k: v for k, v in request.query.items()}
                async with session.get(
                    target,
                    params=params,
                    headers=headers,
                    timeout=_aiohttp.ClientTimeout(total=30),
                ) as resp:
                    raw = await resp.read()
                    LOG.info(
                        "lg-mangaka proxy GET nsid=%s status=%s ms=%d",
                        nsid, resp.status, int((time.monotonic() - started) * 1000),
                    )
                    return web.Response(
                        status=resp.status, body=raw,
                        content_type=resp.headers.get("content-type", "application/json"),
                    )
            try:
                payload = await request.read()
            except Exception:
                payload = json.dumps(body).encode()
            async with session.post(
                target,
                data=payload,
                headers=headers,
                timeout=_aiohttp.ClientTimeout(total=30),
            ) as resp:
                raw = await resp.read()
                LOG.info(
                    "lg-mangaka proxy POST nsid=%s status=%s ms=%d",
                    nsid, resp.status, int((time.monotonic() - started) * 1000),
                )
                return web.Response(
                    status=resp.status, body=raw,
                    content_type=resp.headers.get("content-type", "application/json"),
                )
    except _aiohttp.ClientError as exc:
        LOG.exception("lg-mangaka proxy failed nsid=%s err=%s", nsid, exc)
        return web.json_response(
            {"error": "ProxyFailed", "message": str(exc)[:300], "nsid": nsid},
            status=502,
        )
    except asyncio.TimeoutError:
        return web.json_response(
            {"error": "ProxyTimeout", "nsid": nsid}, status=504,
        )


async def dispatch(request: web.Request) -> web.Response:
    """POST /xrpc/{nsid} — start a BPMN process and await result."""
    nsid = request.match_info.get("nsid", "")
    LOG.info("dispatch start method=%s nsid=%s", request.method, nsid)
    if not nsid:
        return web.json_response({"error": "nsid required in path"}, status=400)

    body: dict[str, Any] = {}
    if request.body_exists and request.method == "POST":
        try:
            body = await request.json()
        except json.JSONDecodeError as e:
            return web.json_response(
                {"error": f"invalid JSON body: {e}"}, status=400,
            )
        if not isinstance(body, dict):
            return web.json_response(
                {"error": "body must be a JSON object"}, status=400,
            )

    # ADR-2605091700 Phase 3: fan-out every dispatch to NATS for observability,
    # replay, and decoupling. Subject = `mitama.{nsid}` (nsid keeps its dots).
    nc = request.app.get("nats")
    if nc is not None:
        try:
            await nc.publish(
                f"mitama.{nsid}",
                json.dumps({"nsid": nsid, "method": request.method, "body": body}).encode(),
            )
        except Exception as exc:  # noqa: BLE001
            LOG.debug("nats fan-out failed (non-fatal) nsid=%s err=%s", nsid, exc)

    direct_response = await public_malak_direct_query(request, nsid, body)
    if direct_response is not None:
        return direct_response

    # ADR-2605111200 Option A (P59): proxy yatabase auth/leads/bmc XRPC NSIDs
    # to lg-yatabase pod over cluster networking that bpmn-dispatcher can
    # actually reach (cloudflared cannot dial the lg-yatabase pod network
    # namespace from this VKE — see deps.toml cycle_20260511_02 blocker).
    if any(nsid.startswith(p) for p in LG_YATABASE_PROXY_PREFIXES):
        return await _proxy_to_lg_yatabase(request, nsid, body)

    if any(nsid.startswith(p) for p in LG_ANIMEKA_PROXY_PREFIXES):
        return await _proxy_to_lg_animeka(request, nsid, body)

    if any(nsid.startswith(p) for p in LG_RECAP_PROXY_PREFIXES):
        return await _proxy_to_lg_recap(request, nsid, body)

    # Mangaka document persistence (ghosthacker import, 2026-05-12):
    # narrow allowlist forwards save/load/list document calls to lg-mangaka
    # so the Genko SPA gets synchronous {document}/{items} responses.
    if nsid in LG_MANGAKA_PROXY_NSIDS:
        return await _proxy_to_lg_mangaka(request, nsid, body)

    if any(nsid.startswith(p) for p in LG_SHINSHI_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_SHINSHI_INTERNAL_URL, "lg-shinshi")

    if any(nsid.startswith(p) for p in LG_NAROU_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_NAROU_INTERNAL_URL, "lg-narou")

    if any(nsid.startswith(p) for p in LG_DOUGAKA_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_DOUGAKA_INTERNAL_URL, "lg-dougaka")

    if any(nsid.startswith(p) for p in LG_X_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_X_INTERNAL_URL, "lg-x")

    if any(nsid.startswith(p) for p in LG_YUKKURI_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_YUKKURI_INTERNAL_URL, "lg-yukkuri")

    if any(nsid.startswith(p) for p in LG_OPEN_JPN_MYNUMBER_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_OPEN_JPN_MYNUMBER_INTERNAL_URL, "lg-open-jpn-mynumber")

    if any(nsid.startswith(p) for p in LG_CURPUS2SKILL_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_CURPUS2SKILL_INTERNAL_URL, "lg-curpus2skill")

    if any(nsid.startswith(p) for p in LG_PD_COLOR_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_PD_COLOR_INTERNAL_URL, "lg-pd-color")

    if any(nsid.startswith(p) for p in LG_KARMA_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_KARMA_INTERNAL_URL, "lg-karma")

    if any(nsid.startswith(p) for p in LG_LEGAL_ENTITY_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_LEGAL_ENTITY_INTERNAL_URL, "lg-legal-entity")

    if any(nsid.startswith(p) for p in LG_ORGANISM_PROXY_PREFIXES):
        return await _proxy_to_lg_pod(request, nsid, body, LG_ORGANISM_INTERNAL_URL, "lg-organism")

    mailer_direct = await _dispatch_mailer_direct(nsid, body)
    if mailer_direct is not None:
        return mailer_direct

    if nsid in MAPS_LANGSERVER_PROXY_NSIDS or nsid.lower() in MAPS_LANGSERVER_PROXY_NSIDS_LOWER:
        return await _proxy_to_lg_pod(request, nsid, body, MAPS_LANGSERVER_INTERNAL_URL, "maps-langserver", timeout=45)

    if nsid in AMENO_LANGSERVER_PROXY_NSIDS or nsid.lower() in AMENO_LANGSERVER_PROXY_NSIDS_LOWER:
        return await _proxy_to_lg_pod(request, nsid, body, AMENO_LANGSERVER_INTERNAL_URL, "ameno-langserver", timeout=15)

    if nsid == "com.etzhayyim.apps.ameno.subscribeBriefs":
        return await _proxy_to_lg_pod_sse(request, nsid, AMENO_LANGSERVER_INTERNAL_URL, "ameno-langserver")

    if nsid in MALAK_LANGSERVER_PROXY_NSIDS or nsid.lower() in MALAK_LANGSERVER_PROXY_NSIDS_LOWER:
        return await _proxy_to_lg_pod(request, nsid, body, MALAK_LANGSERVER_INTERNAL_URL, "malak-langserver", timeout=120)

    binding = await lookup_binding(nsid)
    if nsid.startswith("com.etzhayyim.apps.maps.") and nsid.rsplit(".", 1)[-1].lower() in MAPS_LANGSERVER_PROXY_SUFFIXES:
        return await _proxy_to_lg_pod(request, nsid, body, MAPS_LANGSERVER_INTERNAL_URL, "maps-langserver", timeout=45)
    if not binding:
        return web.json_response(
            {"error": "no active binding", "nsid": nsid}, status=404,
        )
    LOG.info(
        "dispatch binding nsid=%s process=%s timeoutMs=%s",
        nsid,
        binding["bpmn_process_id"],
        binding["result_timeout_ms"],
    )

    timeout_ms = binding["result_timeout_ms"]
    started = time.monotonic()
    # Inject the resolved bpmn_process_id as a process variable so worker
    # tasks (e.g. generic.db.insert) can scope writes to the binding's
    # write_table_allowlist. Caller body cannot override this (we set
    # last-write-wins after spread). NSID is also injected for audit
    # correlation; it's not used for enforcement.
    process_vars = {
        **(body or {}),
        "_bpmnProcessId": binding["bpmn_process_id"],
        "_nsid": nsid,
    }
    LOG.info("dispatch process_vars keys=%s body_keys=%s", list(process_vars.keys()), list(body.keys()))

    # Phase G (2026-05-13): all vertex_bpmn_lexicon_binding rows migrated to routing_target='langgraph'.
    # Zeebe/Spiff fallback removed.
    return await _dispatch_langgraph(
        nsid=nsid,
        binding=binding,
        process_vars=process_vars,
        started=started,
    )








# ─── Auth middleware ─────────────────────────────────────────────────────

@web.middleware
async def auth_middleware(request: web.Request, handler):
    """Gate `/xrpc/*` on shared-secret header when strict mode enabled.

    `/health` is always open. `/bindings` is gated because it enumerates
    the live NSID → BPMN process surface.
    Unknown `DISPATCHER_AUTH_MODE` fails closed to avoid mis-configuration
    silently dropping the gate.
    """
    if request.path == "/health":
        return await handler(request)
    if not (request.path.startswith("/xrpc/") or request.path == "/mcp" or request.path == "/bindings"):
        return await handler(request)
    if AUTH_MODE == "off":
        return await handler(request)
    if AUTH_MODE == "strict":
        if not INTERNAL_SECRET:
            LOG.error("DISPATCHER_AUTH_MODE=strict but DISPATCHER_INTERNAL_SECRET empty")
            return web.json_response(
                {"error": "AuthMisconfigured",
                 "message": "dispatcher strict mode requires DISPATCHER_INTERNAL_SECRET"},
                status=500,
            )
        import hmac as _hmac
        import hashlib as _hashlib
        provided = request.headers.get(INTERNAL_TRUST_HEADER, "")
        if not provided:
            return web.json_response(
                {"error": "Unauthorized",
                 "message": f"missing {INTERNAL_TRUST_HEADER} header"},
                status=401,
            )
        # Accept either raw shared-secret (legacy) OR HMAC-SHA256(body, secret)
        # so callers like the yatabase Worker (P55 onwards) that already sign
        # against DISPATCHER_INTERNAL_SECRET keep working.
        if _hmac.compare_digest(provided, INTERNAL_SECRET):
            return await handler(request)
        try:
            body_bytes = await request.read()
        except Exception:  # noqa: BLE001
            body_bytes = b""
        expected_hmac = _hmac.new(
            INTERNAL_SECRET.encode("utf-8"), body_bytes, _hashlib.sha256
        ).hexdigest()
        if _hmac.compare_digest(provided, expected_hmac):
            return await handler(request)
        return web.json_response(
            {"error": "Unauthorized",
             "message": f"missing or invalid {INTERNAL_TRUST_HEADER} header"},
            status=401,
        )
    LOG.error("unknown DISPATCHER_AUTH_MODE=%r (expected off|strict)", AUTH_MODE)
    return web.json_response(
        {"error": "AuthMisconfigured",
         "message": f"unknown DISPATCHER_AUTH_MODE={AUTH_MODE!r}"},
        status=500,
    )


# ─── App bootstrap ───────────────────────────────────────────────────────

async def make_app() -> web.Application:
    app = web.Application(middlewares=[auth_middleware])

    # ─── NATS JetStream fan-out (ADR-2605091700, Phase 3) ────────────────
    # Every /xrpc/{nsid} dispatch publishes a copy to NATS subject
    # `mitama.{nsid-with-dots}` so all actor invocations become observable
    # / replayable / decoupled from RW availability. Fire-and-forget;
    # publish failure does not block the dispatch.
    nats_url = os.environ.get("NATS_URL", "")
    nats_enabled = bool(nats_url) and os.environ.get("DISPATCHER_NATS_ENABLED", "1") == "1"
    if nats_enabled:
        try:
            import nats as _nats  # type: ignore[import-not-found]
            nc = await _nats.connect(
                nats_url,
                max_reconnect_attempts=-1,
                reconnect_time_wait=2,
                connect_timeout=3,
            )
            app["nats"] = nc
            LOG.info("dispatcher NATS connected url=%s", nats_url)
        except Exception as exc:  # noqa: BLE001
            LOG.warning("dispatcher NATS connect failed (continuing without): %s", exc)
            app["nats"] = None
    else:
        app["nats"] = None
    app.router.add_get("/health", health)
    app.router.add_get("/bindings", list_bindings)
    # MCP envelope route (ADR-2605082000 §2.6 + ADR-0087). Must be registered
    # BEFORE the wildcard so /xrpc/com.etzhayyim.mcp.message hits the dedicated
    # handler instead of the BPMN-binding lookup.
    from kotodama.mcp_dispatch import aiohttp_route as _mcp_route, build_default_handlers
    app["mcp_handlers"] = build_default_handlers()
    app.router.add_post("/xrpc/com.etzhayyim.mcp.message", _mcp_route)
    app.router.add_post("/mcp", mcp_route)
    app.router.add_post("/xrpc/{nsid}", dispatch)
    app.router.add_get("/xrpc/{nsid}", dispatch)

    LOG.info(
        "dispatcher ready, agentgateway_mcp_url=%s, port=%d, binding_ttl=%ds",
        AGENTGATEWAY_MCP_URL,
        PORT,
        BINDING_TTL_SEC,
    )
    return app


def main() -> None:
    if not os.environ.get("RW_URL"):
        LOG.warning("RW_URL not set — binding lookup will fail")
    web.run_app(make_app(), host="0.0.0.0", port=PORT, access_log=None)


if __name__ == "__main__":
    main()
