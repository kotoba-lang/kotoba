"""Zeebe task handlers for open-data Knowledge-Graph ingest (public internet sources).

Migrates the public/open-data adapters of the vendor yatabase KG ingest
(`etzhayyimcojp:60-apps/etzhayyim-project-yatabase/lg/lg_yatabase/graphs/kg_ingest.py`
`_SOURCES`) onto the etzhayyim RW-free substrate (ADR-2605172000). Same canonical
flat entity shape `{id, qid, type, label_ja, label_en, source_id, license,
extractor, confidence}` the kotoba datomic writer consumes
(`kotoba_datomic.yatabase_entity_to_tx_ops`).

Slice scope (this file): the LIVE-GROUNDED clean-public sources only —
**wikidata** (SPARQL, CC0) and **crossref** (REST, CC0). Both fetch+parse paths
were verified end-to-end against their live endpoints 2026-05-31. The remaining
vendor sources are deliberately excluded here:
  * hf_rebel / hf_conceptnet — already covered by `ingest.hf_dataset`.
  * egov_laws (e-Gov) — excluded: redundant with `ingest.houbun` (which ingests
    the e-Gov api/2 corpus) and the vendor adapter is broken vs the live API.
  * japan_company_registry (gBiz) — out of scope per user direction (2026-05-31);
    not migrated.

The vendor kg_ingest module STAYS in etzhayyimcojp: it is load-bearing for the live
commercial yatabase/kotobase product (server.py scheduler + kg_handlers reads),
and its RW retirement is gated by the 7-step cutover
(`MIGRATION-rw-to-kotoba-datomic.md`). Vendor removal is the post-cutover step,
not part of this port.

Persistence: orchestration spine (run/cursor) via the shared RW-free
`ingest.core` helpers (best-effort, see `_spine`); the canonical entities live in
this worker's own `ingest_kg_open.db` SQLite. The RW→kotoba-datomic refactor
(vendor ADR-2605302130) is performed KOTOBA-SIDE by swapping the single
`_persist_entities` seam for `com.etzhayyim.apps.kotoba.datomic.transact` into an
etzhayyim-owned graph (never vendor `kotobase-kg-v1`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import os
import re
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any, Callable

from kotodama.kotoba_datomic import get_kotoba_client

from kotodama.ingest.core import (
    IngestArtifact,
    IngestRun,
    cursor_vertex_id,
    mark_run_finished,
    run_vertex_id,
    upsert_artifact,
    upsert_cursor,
    upsert_run,
)

_LOG = logging.getLogger("ingest.kg_open")

ACTOR_DID = "did:web:kg.etzhayyim.com"
KG_PATH_DID = f"{ACTOR_DID}:open"
INGEST_FAMILY = "kg-open"


def _spine(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Best-effort call into the RW-coupled `ingest.core` spine (telemetry only);
    a missing RW_URL must never abort an ingest (see ingest.ndl for rationale)."""
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001
        _LOG.warning("ingest.kg_open spine call %s degraded: %s", getattr(fn, "__name__", fn), str(exc)[:160])
        return None


# ── Source registry (live-grounded clean-public sources) ──────────────────────
_SOURCES: dict[str, dict[str, Any]] = {
    "wikidata": {
        "name": "Wikidata",
        "uri": os.environ.get("WIKIDATA_SPARQL_URL", "https://query.wikidata.org/sparql"),
        "adapter": "sparql",
        "license": "CC0",
        "confidence": 0.95,
        "verified": True,  # live-grounded 2026-05-31
        # vendor parity: instances (P31) of Q4830453 located in Japan (P17=Q17).
        "sparql_query": (
            "SELECT ?item ?itemLabel WHERE {"
            "  ?item wdt:P31 wd:Q4830453 ."
            "  ?item wdt:P17 wd:Q17 ."
            "  SERVICE wikibase:label { bd:serviceParam wikibase:language 'ja,en'. }"
            "} LIMIT 1000"
        ),
    },
    "crossref": {
        "name": "Crossref",
        "uri": os.environ.get("CROSSREF_API_URL", "https://api.crossref.org/works"),
        "adapter": "rest_json",
        "license": "CC0",
        "confidence": 0.90,
        "mailto": os.environ.get("CROSSREF_MAILTO", "kg@etzhayyim.com"),
        "rows": 200,
        "verified": True,  # live-grounded 2026-05-31
    },
    "openstreetmap": {
        "name": "OpenStreetMap",
        "uri": os.environ.get("OVERPASS_API_URL", "https://overpass-api.de/api/interpreter"),
        "adapter": "overpass",
        "license": "ODbL",
        "confidence": 0.85,
        "verified": True,  # live-grounded 2026-05-31
        # vendor parity: named cities/towns + hospitals/universities in the JP bbox.
        "overpass_query": (
            "[out:json][timeout:60];"
            "(node[\"place\"~\"^(city|town)$\"][\"name\"](24,123,46,146);"
            "node[\"amenity\"~\"^(hospital|university)$\"][\"name\"](24,123,46,146););"
            "out body 5000;"
        ),
    },
    # NOTE: japan_company_registry (gBiz) is OUT OF SCOPE per user direction
    # (2026-05-31) and is intentionally not migrated.
    #
    # NOTE: e-Gov 法令 (vendor `egov_laws`) is deliberately NOT added here.
    #   (1) Redundant source: the e-Gov laws feed is already ingested by
    #       `ingest.houbun` (EGOV api/2 → vertex_houbun_statute/article, full
    #       corpus). A KG-legislation node should derive from houbun, not
    #       re-fetch e-Gov.
    #   (2) The vendor adapter is broken vs the live API anyway: it GETs
    #       `/api/1/lawdata` and json.loads() it, but the live e-Gov v1 API
    #       returns XML (verified 2026-05-31), while the working JSON surface is
    #       v2 (`/api/2/laws`, which houbun uses).
    # See ADR-2605312100.
}

_UA = "etzhayyim-kg/0.1 (https://etzhayyim.com; kg@etzhayyim.com)"

# PII screen (ADR-0018 Tier 3 parity) — public KG records must not carry PII.
_PII_PATTERNS = [
    re.compile(r"\b[\w.+-]+@[\w-]+\.[a-zA-Z]{2,}\b"),   # email
    re.compile(r"\b\d{3}[-.\s]\d{4}[-.\s]\d{4}\b"),     # JP phone
    re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),               # SSN
    re.compile(r"\b\d{12}\b"),                          # マイナンバー
    re.compile(r"(?:〒|〒\s?)\d{3}-\d{4}"),             # JP postal code
]


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _has_pii(text: str) -> bool:
    return any(p.search(text) for p in _PII_PATTERNS)


def _is_japanese(text: str) -> bool:
    return any("぀" <= c <= "鿿" for c in text)




# ── Persistence (kotoba datomic refactor target — ADR-2605302130) ─────────────
# Canonical entities now land in the kotoba Datom log. The RW→kotoba refactor
# is performed KOTOBA-SIDE: this function calls get_kotoba_client().insert_row()
# with the entities. No other code here writes entities.
def _persist_entities(entities: list[dict[str, Any]], source_id: str, now: str) -> int:
    inserted = 0
    client = get_kotoba_client()
    for e in entities:
        eid = e.get("id")
        if not eid:
            continue
        vid = f"at://{KG_PATH_DID}/com.etzhayyim.apps.kg.entity/{eid}"
        row_dict = {
            "vertex_id": vid,
            "created_date": today_iso(),
            "sensitivity_ord": 0,
            "owner_did": KG_PATH_DID,
            "id": eid,
            "qid": e.get("qid"),
            "type": e.get("type"),
            "label_ja": e.get("label_ja"),
            "label_en": e.get("label_en"),
            "source_id": e.get("source_id") or source_id,
            "license": e.get("license"),
            "extractor": e.get("extractor"),
            "confidence": float(e.get("confidence") or 0.0),
            "status": "active",
            "discovered_at": now,
            "updated_at": now,
            "actor_did": KG_PATH_DID,
            "org_did": "anon",
        }
        try:
            client.insert_row("vertex_kg_entity", row_dict)
            inserted += 1
        except Exception as exc:
            _LOG.warning("Failed to insert entity %s: %s", vid, exc)
            continue
    return inserted


# ── Fetch (substrate-independent, ported + live-verified 2026-05-31) ──────────
def _http_get(url: str, accept: str = "application/json", timeout: float = 180.0, data: bytes | None = None) -> bytes:
    # data is not None → POST (Overpass takes a urlencoded `data=<query>` body).
    req = urllib.request.Request(url, data=data, headers={"Accept": accept, "User-Agent": _UA})
    with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (trusted public hosts)
        return r.read()


def _fetch_sparql(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    params = urllib.parse.urlencode({"query": cfg["sparql_query"], "format": "json"})
    raw = _http_get(f"{cfg['uri']}?{params}", accept="application/sparql-results+json")
    data = json.loads(raw.decode("utf-8"))
    bindings = data.get("results", {}).get("bindings", [])
    return [{"_raw": b, "_adapter": "sparql"} for b in bindings]


def _fetch_crossref(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    rows = int(cfg.get("rows", 200))
    mailto = cfg.get("mailto", "kg@etzhayyim.com")
    url = f"{cfg['uri']}?rows={rows}&select=DOI,title,author,published&mailto={mailto}"
    raw = _http_get(url, accept="application/json", timeout=60.0)
    data = json.loads(raw.decode("utf-8"))
    items = data.get("message", {}).get("items", [])
    return [{"_raw": item, "_adapter": "crossref"} for item in items]


def _fetch_overpass(cfg: dict[str, Any]) -> list[dict[str, Any]]:
    body = urllib.parse.urlencode({"data": cfg["overpass_query"]}).encode("utf-8")
    raw = _http_get(cfg["uri"], accept="application/json", timeout=90.0, data=body)
    data = json.loads(raw.decode("utf-8"))
    elements = data.get("elements", [])
    return [{"_raw": e, "_adapter": "overpass"} for e in elements]


_FETCHERS: dict[str, Callable[[dict[str, Any]], list[dict[str, Any]]]] = {
    "sparql": _fetch_sparql,
    "rest_json": _fetch_crossref,
    "overpass": _fetch_overpass,
}


# ── Extract (ported; entity shape == kotoba datomic input) ────────────────────
def _extract_sparql_record(rec: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any] | None:
    b = rec.get("_raw", {})
    item_uri = (b.get("item") or {}).get("value", "")
    label = (b.get("itemLabel") or {}).get("value", "")
    type_label = (b.get("typeLabel") or {}).get("value", "schema:Thing")
    if not item_uri:
        return None
    qid = item_uri.split("/")[-1] if "wikidata.org" in item_uri else None
    return {
        "id": qid or hashlib.sha256(item_uri.encode()).hexdigest()[:16],
        "qid": qid,
        "type": type_label,
        "label_ja": label if _is_japanese(label) else None,
        "label_en": label if label and not _is_japanese(label) else None,
        "source_id": "wikidata",
        "license": cfg["license"],
        "extractor": "sparql-v1",
        "confidence": cfg.get("confidence", 0.8),
    }


def _extract_crossref_record(rec: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any] | None:
    item = rec.get("_raw", {})
    doi = item.get("DOI", "")
    if not doi:
        return None
    titles = item.get("title", [])
    label_en = (titles[0] if titles else doi)[:500]
    return {
        "id": hashlib.sha256(doi.encode()).hexdigest()[:16],
        "qid": f"doi:{doi}",
        "type": "schema:ScholarlyArticle",
        "label_ja": None,
        "label_en": label_en,
        "source_id": "crossref",
        "license": cfg.get("license", "CC0"),
        "extractor": "crossref-v1",
        "confidence": cfg.get("confidence", 0.8),
    }


_PLACE_TYPE_MAP: dict[str, str] = {
    "city": "schema:City", "town": "schema:City", "village": "schema:City",
    "hospital": "schema:Hospital", "university": "schema:EducationalOrganization",
    "school": "schema:School",
}


def _extract_overpass_record(rec: dict[str, Any], cfg: dict[str, Any]) -> dict[str, Any] | None:
    e = rec.get("_raw", {})
    tags = e.get("tags") or {}
    name = (tags.get("name:ja") or tags.get("name") or "").strip()[:500]
    if not name:
        return None
    osm_id = f"osm:{e.get('type', 'n')}{e.get('id', '')}"
    place_tag = tags.get("place") or tags.get("amenity") or ""
    return {
        "id": hashlib.sha256(osm_id.encode()).hexdigest()[:16],
        "qid": osm_id,
        "type": _PLACE_TYPE_MAP.get(place_tag, "schema:Place"),
        "label_ja": name if _is_japanese(name) else None,
        "label_en": name if not _is_japanese(name) else None,
        "source_id": "openstreetmap",
        "license": cfg.get("license", "ODbL"),
        "extractor": "overpass-v1",
        "confidence": cfg.get("confidence", 0.85),
    }


_EXTRACTORS: dict[str, Callable[[dict[str, Any], dict[str, Any]], dict[str, Any] | None]] = {
    "sparql": _extract_sparql_record,
    "rest_json": _extract_crossref_record,
    "overpass": _extract_overpass_record,
}


def _fetch_extract_persist(source_id: str) -> dict[str, Any]:
    cfg = _SOURCES.get(source_id)
    if not cfg:
        return {"ok": False, "error": f"unknown source_id: {source_id}"}
    adapter = cfg["adapter"]
    try:
        raw = _FETCHERS[adapter](cfg)
    except Exception as exc:  # noqa: BLE001 — a source fetch failure must not crash the task
        _LOG.warning("ingest.kg_open fetch %s failed: %s", source_id, str(exc)[:160])
        return {"ok": False, "sourceId": source_id, "error": str(exc)[:200]}
    # PII screen (drop any raw record carrying PII before extraction).
    screened, pii_dropped = [], 0
    for rec in raw:
        if _has_pii(json.dumps(rec.get("_raw", ""), ensure_ascii=False)):
            pii_dropped += 1
            continue
        screened.append(rec)
    extractor = _EXTRACTORS[adapter]
    entities = []
    for rec in screened:
        try:
            ent = extractor(rec, cfg)
        except Exception:  # noqa: BLE001 — per-record extraction must not abort the run
            ent = None
        if ent is not None:
            entities.append(ent)
    now = now_iso()
    inserted = _persist_entities(entities, source_id, now)
    return {
        "ok": True,
        "sourceId": source_id,
        "rawFetched": len(raw),
        "piiDropped": pii_dropped,
        "extracted": len(entities),
        "inserted": inserted,
    }


# ── Zeebe tasks ───────────────────────────────────────────────────────────────
async def task_kgopen_create_run(
    runId: str = "",
    sourceId: str = "wikidata",
    mode: str = "snapshot",
    requestedBy: str = "zeebe",
    inputJson: str = "",
    **_: Any,
) -> dict[str, Any]:
    run = IngestRun(
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or "wikidata",
        mode=mode or "snapshot",
        run_id=runId,
        status="running",
        bpmn_process_id="ingest_kg_open_snapshot",
        requested_by=requestedBy,
        input_json=inputJson,
    ).with_run_id()
    vid = run_vertex_id(run.run_id)
    await asyncio.to_thread(_spine, upsert_run, run)
    return {"ok": True, "runId": run.run_id, "runVertexId": vid, "sourceId": run.source_id}


async def task_kgopen_plan(sources: str = "", **_: Any) -> dict[str, Any]:
    # Default plan = live-verified sources only (all current sources are). Any
    # future unverified source added to _SOURCES is opt-in: name it in `sources`.
    if sources:
        requested = [s.strip() for s in sources.split(",") if s.strip()]
    else:
        requested = [s for s, cfg in _SOURCES.items() if cfg.get("verified")]
    shards = [{"shardKey": s, "sourceId": s} for s in requested if s in _SOURCES]
    return {
        "ok": True,
        "plannedShards": len(shards),
        "shards": shards,
        "firstShard": shards[0] if shards else {},
        "knownSources": list(_SOURCES),
        "verifiedSources": [s for s, cfg in _SOURCES.items() if cfg.get("verified")],
    }


async def task_kgopen_acquire_cursor(
    runId: str,
    firstShard: dict[str, Any] | None = None,
    sourceId: str = "",
    **_: Any,
) -> dict[str, Any]:
    sid = str((firstShard or {}).get("sourceId") or sourceId)
    if not sid:
        return {"ok": False, "error": "missing sourceId"}
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor_vid = cursor_vertex_id(INGEST_FAMILY, sid, sid)
    await asyncio.to_thread(
        _spine, upsert_cursor,
        ingest_family=INGEST_FAMILY, source_id=sid, shard_key=sid,
        locked_by_run_id=runId, lock_expires_at=expires, status="locked",
    )
    return {"ok": True, "sourceId": sid, "cursorVertexId": cursor_vid}


async def task_kgopen_fetch_source(
    runId: str,
    sourceId: str = "",
    shardKey: str = "",
    **_: Any,
) -> dict[str, Any]:
    sid = sourceId or shardKey
    if not sid:
        return {"ok": False, "error": "sourceId required"}
    res = await asyncio.to_thread(_fetch_extract_persist, sid)
    if res.get("ok"):
        await asyncio.to_thread(
            _spine, upsert_artifact,
            IngestArtifact(
                run_id=runId, artifact_kind="entities", source_id=sid,
                uri=f"inline://kg-open/{sid}/{runId}",
                record_count=int(res.get("inserted", 0)),
                props={"rawFetched": res.get("rawFetched"), "piiDropped": res.get("piiDropped")},
            ),
        )
    return res


async def task_kgopen_verify_visibility(sourceId: str = "", shardKey: str = "", **_: Any) -> dict[str, Any]:
    sid = sourceId or shardKey
    return await asyncio.to_thread(_verify_blocking, sid)


def _verify_blocking(source_id: str) -> dict[str, Any]:
    client = get_kotoba_client()
    n = int(client.aggregate_where("vertex_kg_entity", "count", "*", "source_id", source_id))
    return {"ok": True, "verified": n > 0, "sourceId": source_id, "entityTotal": n}


async def task_kgopen_advance_cursor(
    runId: str, sourceId: str = "", shardKey: str = "", complete: bool = False, **_: Any
) -> dict[str, Any]:
    sid = sourceId or shardKey
    if not sid:
        return {"ok": False, "error": "missing sourceId"}
    cursor_vid = cursor_vertex_id(INGEST_FAMILY, sid, sid)
    await asyncio.to_thread(
        _spine, upsert_cursor,
        ingest_family=INGEST_FAMILY, source_id=sid, shard_key=sid,
        cursor_value=now_iso(), locked_by_run_id=runId,
        status="done" if complete else "active",
    )
    return {"ok": True, "sourceId": sid, "cursorVertexId": cursor_vid}


async def task_kgopen_complete_run(
    runId: str, status: str = "completed", inserted: int = 0, error: str = "", **_: Any
) -> dict[str, Any]:
    await asyncio.to_thread(
        _spine, mark_run_finished, runId,
        status=status or "completed", records_written=int(inserted or 0),
        last_error=error or None, output={"inserted": int(inserted or 0)},
    )
    return {"ok": True, "runId": runId, "status": status or "completed"}
