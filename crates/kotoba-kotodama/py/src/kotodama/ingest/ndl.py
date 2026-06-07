"""Zeebe task handlers for NDL (National Diet Library / 国立国会図書館) ingest.

Open-data harvester for the NDL OAI-PMH metadata feed (``ndlsearch.ndl.go.jp``).
Ported from the vendor yatabase KG adapter
(``etzhayyimcojp:60-apps/etzhayyim-project-yatabase/lg/lg_yatabase/ndl_ingest.py``);
the substrate-independent fetch + parse logic is kept verbatim in spirit, the
RisingWave persistence is dropped (etzhayyim is RW-free per ADR-2605172000).

Scope (slice 1 — OAI-PMH metadata only):
  * SRU image+OCR / IIIF / B2 blob path is intentionally NOT ported here. It
    needs three further substrate swaps (B2 → IPFS blob, vendor OCR endpoint →
    ``llm.etzhayyim.com``, datomic write) and lands as a named slice 2.

Persistence: the orchestration spine (run / cursor lock) uses the shared
``ingest.core`` RW-free SQLite helpers; the resumable OAI checkpoint and the
domain facts (``vertex_ndl_digital_item``) live in this worker's own
``ingest_ndl.db`` SQLite, matching the houbun / site_common_crawl convention.

The RW→kotoba-datomic refactor (ADR-2605302130) is performed **kotoba-side**:
it swaps the single ``_persist_items`` seam (below) for a kotoba datomic
transact of the same item dicts. Nothing else in this module touches the
domain-fact write path.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import asyncio
import hashlib
import logging
import os
import re
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from contextlib import contextmanager
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

import sqlite3

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

_LOG = logging.getLogger("ingest.ndl")


def _spine(fn: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Best-effort call into the shared ``ingest.core`` orchestration spine.

    The spine (vertex_ingest_run / cursor / artifact) is still RW-coupled via
    ``db_sync.sync_cursor`` (the RW-free migration of the spine itself is
    incomplete — ADR-2605172000). It is telemetry only: this worker's harvest
    and resumption depend solely on the local ``ingest_ndl.db`` SQLite, so a
    missing RW_URL or spine error must never abort an ingest.
    """
    try:
        return fn(*args, **kwargs)
    except Exception as exc:  # noqa: BLE001 — spine is best-effort telemetry
        _LOG.warning("ingest.ndl spine call %s degraded: %s", getattr(fn, "__name__", fn), str(exc)[:160])
        return None

# ── Identity / source constants ───────────────────────────────────────────────
ACTOR_DID = "did:web:ndl.etzhayyim.com"
ONLINE_PATH_DID = f"{ACTOR_DID}:dl-open"
INGEST_FAMILY = "ndl"
SOURCE_ID = "ndl-oai"

# Endpoints (env-overridable; default = current NDL unified search OAI-PMH).
OAI_BASE = os.environ.get("NDL_OAI_ENDPOINT", "https://ndlsearch.ndl.go.jp/api/oaipmh")

# NDL OAI-PMH (oai_dc) setSpec taxonomy — verified 2026-05-31 against
# ndlsearch.ndl.go.jp (from=2024-01-01&until=2024-01-02): digitised + freely
# available items carry `ndl-dl-open` (`ndl-dl` = digitised but possibly
# access-restricted; `ndl-dl-doi` = DOI-assigned). The vendor adapter's
# `ndl-dl-online` / `B00000` / `jpro-*` labels do NOT appear on this feed, so
# filtering on them would reject every record. Override via NDL_OAI_SETS (CSV).
ONLINE_SET_SPECS = {s.strip() for s in (os.environ.get("NDL_OAI_SETS") or "ndl-dl-open").split(",") if s.strip()}

# OAI-PMH / Dublin Core namespaces.
_NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "oai_dc": "http://www.openarchives.org/OAI/2.0/oai_dc/",
    "dc": "http://purl.org/dc/elements/1.1/",
}

_WS = re.compile(r"\s+")


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def today_iso() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _clean(value: Any) -> str:
    return _WS.sub(" ", str(value or "")).strip()


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


# ── Local SQLite (domain facts + resumable OAI checkpoint) ────────────────────
@contextmanager
def sync_cursor():
    db_dir = os.environ.get("ORGANISM_SQLITE_DIR", "/var/lib/etzhayyim/organism")
    os.makedirs(db_dir, exist_ok=True)
    db_path = os.path.join(db_dir, "ingest_ndl.db")
    with sqlite3.connect(db_path) as conn:
        _res = client.q("PRAGMA journal_mode=WAL;")
        _res = client.q(
            """CREATE TABLE IF NOT EXISTS vertex_ndl_bib_item (
                vertex_id TEXT PRIMARY KEY, created_date TEXT, sensitivity_ord INTEGER, owner_did TEXT,
                ndl_id TEXT, provider_id TEXT, title TEXT, creator TEXT, publisher TEXT, issued TEXT,
                language TEXT, material_type TEXT, content_license TEXT, source_url TEXT,
                digital_pid TEXT, manifest_url TEXT, set_specs TEXT, record_xml_sha256 TEXT,
                status TEXT, discovered_at TEXT, updated_at TEXT, actor_did TEXT, org_did TEXT
            )"""
        )
        _res = client.q(
            """CREATE TABLE IF NOT EXISTS vertex_ndl_oai_checkpoint (
                vertex_id TEXT PRIMARY KEY, created_date TEXT, sensitivity_ord INTEGER, owner_did TEXT,
                provider_id TEXT, set_group TEXT, metadata_prefix TEXT, window_start TEXT, window_end TEXT,
                resumption_token TEXT, pages_seen INTEGER, records_seen INTEGER, items_inserted INTEGER,
                status TEXT, error TEXT, updated_at TEXT
            )"""
        )
        yield conn.cursor()


# ── PERSISTENCE SEAM (kotoba datomic refactor target — ADR-2605302130) ────────
# Domain facts currently land in the local RW-free SQLite ingest spine, matching
# the houbun / site_common_crawl convention. The RW→kotoba-datomic refactor is
# performed KOTOBA-SIDE: replace THIS function body with a kotoba datomic
# transact of the same `items` dicts (POST com.etzhayyim.apps.kotoba.datomic.transact,
# one `:ndl/*` entity per item). No other code in this module writes domain
# facts — keep the seam isolated here so the swap is a single, reviewable edit.
def _persist_items(cur: Any, items: list[dict[str, Any]], now: str) -> int:
    inserted = 0
    for item in items:
        ndl_id = item["ndl_id"]
        vid = f"at://{ONLINE_PATH_DID}/com.etzhayyim.apps.ndl.bibItem/{ndl_id}"
        try:
            _res = client.q(
                """INSERT OR REPLACE INTO vertex_ndl_bib_item (
                    vertex_id, created_date, sensitivity_ord, owner_did,
                    ndl_id, provider_id, title, creator, publisher, issued,
                    language, material_type, content_license, source_url,
                    digital_pid, manifest_url, set_specs, record_xml_sha256,
                    status, discovered_at, updated_at, actor_did, org_did
                ) VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'active', ?, ?, ?, 'anon')""",
                (
                    vid, today_iso(), ONLINE_PATH_DID,
                    ndl_id, item.get("provider_id"), item.get("title"), item.get("creator"),
                    item.get("publisher"), item.get("issued"), item.get("language"),
                    item.get("material_type"), item.get("content_license"), item.get("source_url"),
                    item.get("digital_pid"), item.get("manifest_url"), item.get("set_specs"),
                    item.get("record_xml_sha256"), now, now, ONLINE_PATH_DID,
                ),
            )
            inserted += 1
        except sqlite3.Error:
            continue
    return inserted


# ── OAI-PMH fetch + parse (substrate-independent, kept from vendor) ────────────
def _http_get(url: str, accept: str = "application/xml", timeout: float = 60.0) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"Accept": accept, "User-Agent": "ndl.etzhayyim.com/0.1"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 (trusted NDL host)
        return resp.read()


def _oai_url(params: dict[str, str]) -> str:
    return f"{OAI_BASE}?{urllib.parse.urlencode(params)}"


def _month_windows(start_year: int = 2022, start_month: int = 10) -> list[tuple[str, str]]:
    import calendar

    today = datetime.now(timezone.utc).date()
    y, m = int(start_year), int(start_month)
    out: list[tuple[str, str]] = []
    while (y, m) <= (today.year, today.month):
        last = calendar.monthrange(y, m)[1]
        end = date(y, m, last)
        if end > today:
            end = today
        out.append((date(y, m, 1).isoformat(), end.isoformat()))
        m += 1
        if m == 13:
            y, m = y + 1, 1
    return out


_OAI_ID_PREFIX = "oai:ndlsearch.ndl.go.jp:"

# Genuine NDL Digital Collections PID URL forms. A bib/item id such as
# `R100000039-I3388038` (the OAI header identifier on the oai_dc feed) is a
# catalogue key, NOT a digital PID — it must never be turned into an IIIF
# manifest URL. Only these explicit /pid/ forms yield a digital PID. In the
# verified 2024-01 window the oai_dc records carry NO dc:identifier at all, so
# digital_pid/manifest stay empty for bib-level metadata (the digital-image
# resolution is slice 2).
_PID_PATTERNS = (
    r"info:ndljp/pid/(\d+)",
    r"dl\.ndl\.go\.jp/(?:info:ndljp/)?pid/(\d+)",
    r"/pid/(\d+)",
)


def _digital_pid_from(identifiers: list[str]) -> str:
    """Extract a numeric NDL Digital Collections PID from identifier URLs, else ''."""
    for s in identifiers:
        for pat in _PID_PATTERNS:
            m = re.search(pat, s or "")
            if m:
                return m.group(1)
    return ""


def _ndl_id_from_header(identifier: str) -> str:
    """Stable record key = OAI header identifier minus the oai: host prefix."""
    ident = _clean(identifier)
    if ident.startswith(_OAI_ID_PREFIX):
        ident = ident[len(_OAI_ID_PREFIX):]
    return ident or hashlib.sha1((identifier or "").encode("utf-8")).hexdigest()[:24]


def _oai_record_to_item(record: ET.Element, provider_id: str, target_sets: set[str]) -> dict[str, Any] | None:
    header = record.find("oai:header", _NS)
    if header is None or (header.get("status") or "").strip() == "deleted":
        return None
    set_specs = {(_clean(el.text)) for el in header.findall("oai:setSpec", _NS) if el.text}
    if target_sets and not (set_specs & target_sets):
        return None
    identifier = _clean(header.findtext("oai:identifier", default="", namespaces=_NS))
    md = record.find("oai:metadata", _NS)
    dc = md.find("oai_dc:dc", _NS) if md is not None else None

    def dcv(tag: str) -> str:
        if dc is None:
            return ""
        el = dc.find(f"dc:{tag}", _NS)
        return _clean(el.text) if el is not None and el.text else ""

    dc_identifiers = [_clean(el.text) for el in dc.findall("dc:identifier", _NS)] if dc is not None else []
    ndl_id = _ndl_id_from_header(identifier)
    digital_pid = _digital_pid_from(dc_identifiers)
    source_url = next((v for v in dc_identifiers if v.startswith("http")), "")
    if not source_url:
        source_url = f"https://ndlsearch.ndl.go.jp/books/{ndl_id}"
    # IIIF manifest only for genuinely digitised items (digital_pid present).
    manifest_url = (
        f"https://www.dl.ndl.go.jp/api/iiif/{digital_pid}/manifest.json" if digital_pid else ""
    )
    return {
        "ndl_id": ndl_id,
        "provider_id": provider_id,
        "title": dcv("title"),
        "creator": dcv("creator"),
        "publisher": dcv("publisher"),
        "issued": dcv("date"),
        "language": dcv("language"),
        "material_type": dcv("type"),
        "content_license": dcv("rights"),
        "source_url": source_url,
        "digital_pid": digital_pid,
        "manifest_url": manifest_url,
        "set_specs": ",".join(sorted(set_specs)),
        "record_xml_sha256": _sha256(ET.tostring(record, encoding="utf-8")),
    }


def _oai_list_records(
    *, metadata_prefix: str, window_start: str, window_end: str, token: str, provider_id: str
) -> tuple[list[dict[str, Any]], str, int, str]:
    """Fetch one OAI-PMH ListRecords page. Returns (items, next_token, records_seen, page_sha)."""
    if token:
        url = _oai_url({"verb": "ListRecords", "resumptionToken": token})
    else:
        url = _oai_url(
            {
                "verb": "ListRecords",
                "metadataPrefix": metadata_prefix,
                "from": window_start,
                "until": window_end,
            }
        )
    raw = _http_get(url)
    page_sha = _sha256(raw)
    root = ET.fromstring(raw)
    records = root.findall(".//oai:ListRecords/oai:record", _NS)
    items: list[dict[str, Any]] = []
    for rec in records:
        item = _oai_record_to_item(rec, provider_id, ONLINE_SET_SPECS)
        if item is not None:
            items.append(item)
    next_token = _clean(root.findtext(".//oai:resumptionToken", default="", namespaces=_NS))
    return items, next_token, len(records), page_sha


# ── Checkpoint read/write (resumable, local table) ────────────────────────────
def _checkpoint_vid(provider_id: str, set_group: str, window_start: str, window_end: str) -> str:
    key = hashlib.sha1(f"{provider_id}|{set_group}|{window_start}|{window_end}".encode("utf-8")).hexdigest()[:20]
    return f"at://{ACTOR_DID}/com.etzhayyim.apps.ndl.oaiCheckpoint/{key}"


def _read_checkpoint(cur: Any, vid: str) -> dict[str, Any] | None:
    _res = client.q(
        "SELECT resumption_token, pages_seen, records_seen, items_inserted, status "
        "FROM vertex_ndl_oai_checkpoint WHERE vertex_id = ?",
        (vid,),
    )
    row = (_res[0] if _res else None)
    if not row:
        return None
    return {
        "resumption_token": row[0] or "",
        "pages_seen": int(row[1] or 0),
        "records_seen": int(row[2] or 0),
        "items_inserted": int(row[3] or 0),
        "status": row[4] or "",
    }


def _write_checkpoint(
    cur: Any,
    *,
    vid: str,
    provider_id: str,
    set_group: str,
    metadata_prefix: str,
    window_start: str,
    window_end: str,
    token: str,
    pages_seen: int,
    records_seen: int,
    items_inserted: int,
    status: str,
    error: str = "",
) -> None:
    _res = client.q(
        """INSERT OR REPLACE INTO vertex_ndl_oai_checkpoint (
            vertex_id, created_date, sensitivity_ord, owner_did,
            provider_id, set_group, metadata_prefix, window_start, window_end,
            resumption_token, pages_seen, records_seen, items_inserted, status, error, updated_at
        ) VALUES (?, ?, 0, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            vid, today_iso(), ACTOR_DID,
            provider_id, set_group, metadata_prefix, window_start, window_end,
            token, pages_seen, records_seen, items_inserted, status, error or None, now_iso(),
        ),
    )


# ── Zeebe tasks ───────────────────────────────────────────────────────────────
async def task_ndl_create_run(
    runId: str = "",
    sourceId: str = SOURCE_ID,
    mode: str = "delta",
    requestedBy: str = "zeebe",
    inputJson: str = "",
    **_: Any,
) -> dict[str, Any]:
    run = IngestRun(
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        mode=mode or "delta",
        run_id=runId,
        status="running",
        bpmn_process_id="ingest_ndl_oai_metadata_delta",
        requested_by=requestedBy,
        input_json=inputJson,
    ).with_run_id()
    vid = run_vertex_id(run.run_id)
    await asyncio.to_thread(_spine, upsert_run, run)
    return {"ok": True, "runId": run.run_id, "runVertexId": vid, "sourceId": run.source_id}


def _plan_windows(
    set_group: str, metadata_prefix: str, start_year: int, start_month: int, max_windows: int
) -> list[dict[str, Any]]:
    windows = _month_windows(start_year, start_month)
    shards: list[dict[str, Any]] = []
    if True:
        client = get_kotoba_client()
        for win_start, win_end in windows:
            vid = _checkpoint_vid(SOURCE_ID, set_group, win_start, win_end)
            cp = _read_checkpoint(cur, vid)
            if cp and cp["status"] == "completed":
                continue  # already harvested this window
            shards.append(
                {
                    "shardKey": f"{set_group}|{win_start}|{win_end}",
                    "setGroup": set_group,
                    "metadataPrefix": metadata_prefix,
                    "windowStart": win_start,
                    "windowEnd": win_end,
                }
            )
            if len(shards) >= max(1, int(max_windows)):
                break
    return shards


async def task_ndl_oai_plan(
    setGroup: str = "online",
    metadataPrefix: str = "oai_dc",
    startYear: int = 2022,
    startMonth: int = 10,
    maxWindows: int = 10,
    **_: Any,
) -> dict[str, Any]:
    shards = await asyncio.to_thread(
        _plan_windows, setGroup, metadataPrefix, int(startYear), int(startMonth), int(maxWindows)
    )
    return {
        "ok": True,
        "sourceId": SOURCE_ID,
        "plannedShards": len(shards),
        "shards": shards,
        "firstShard": shards[0] if shards else {},
    }


async def task_ndl_acquire_cursor(
    runId: str,
    sourceId: str = SOURCE_ID,
    firstShard: dict[str, Any] | None = None,
    shardKey: str = "",
    **_: Any,
) -> dict[str, Any]:
    shard = str((firstShard or {}).get("shardKey") or shardKey)
    if not shard:
        return {"ok": False, "error": "missing shard key"}
    expires = (datetime.now(timezone.utc) + timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
    cursor_vid = cursor_vertex_id(INGEST_FAMILY, sourceId or SOURCE_ID, shard)
    await asyncio.to_thread(
        _spine,
        upsert_cursor,
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        shard_key=shard,
        locked_by_run_id=runId,
        lock_expires_at=expires,
        status="locked",
    )
    return {"ok": True, "shardKey": shard, "cursorVertexId": cursor_vid, "cursorValue": shard}


def _fetch_window_blocking(
    *,
    run_id: str,
    set_group: str,
    metadata_prefix: str,
    window_start: str,
    window_end: str,
    max_pages: int,
) -> dict[str, Any]:
    vid = _checkpoint_vid(SOURCE_ID, set_group, window_start, window_end)
    if True:
        client = get_kotoba_client()
        cp = _read_checkpoint(cur, vid) or {
            "resumption_token": "",
            "pages_seen": 0,
            "records_seen": 0,
            "items_inserted": 0,
            "status": "",
        }
        token = cp["resumption_token"]
        pages_seen = cp["pages_seen"]
        records_seen = cp["records_seen"]
        items_inserted = cp["items_inserted"]
        page_artifacts: list[tuple[str, str, int]] = []
        pages_this_run = 0
        status = "running"
        error = ""
        try:
            while pages_this_run < max(1, int(max_pages)):
                items, next_token, rec_count, page_sha = _oai_list_records(
                    metadata_prefix=metadata_prefix,
                    window_start=window_start,
                    window_end=window_end,
                    token=token,
                    provider_id=SOURCE_ID,
                )
                now = now_iso()
                items_inserted += _persist_items(cur, items, now)
                records_seen += rec_count
                pages_seen += 1
                pages_this_run += 1
                page_artifacts.append((page_sha, f"inline://ndl/oai/{vid}/{page_sha}", len(items)))
                token = next_token
                if not token:
                    status = "completed"
                    break
            _write_checkpoint(
                cur,
                vid=vid,
                provider_id=SOURCE_ID,
                set_group=set_group,
                metadata_prefix=metadata_prefix,
                window_start=window_start,
                window_end=window_end,
                token=token,
                pages_seen=pages_seen,
                records_seen=records_seen,
                items_inserted=items_inserted,
                status=status,
            )
        except Exception as exc:  # noqa: BLE001 — record failure on the checkpoint, surface to BPMN
            error = str(exc)[:240]
            _write_checkpoint(
                cur,
                vid=vid,
                provider_id=SOURCE_ID,
                set_group=set_group,
                metadata_prefix=metadata_prefix,
                window_start=window_start,
                window_end=window_end,
                token=token,
                pages_seen=pages_seen,
                records_seen=records_seen,
                items_inserted=items_inserted,
                status="failed",
                error=error,
            )
    # Register page artifacts on the cross-domain ingest spine (best-effort).
    for page_sha, uri, count in page_artifacts:
        _spine(
            upsert_artifact,
            IngestArtifact(
                run_id=run_id,
                artifact_kind="raw",
                source_id=SOURCE_ID,
                uri=uri,
                sha256=page_sha,
                record_count=count,
                props={"window": f"{window_start}/{window_end}", "setGroup": set_group},
            ),
        )
    return {
        "ok": not error,
        "error": error,
        "checkpointVertexId": vid,
        "status": status if not error else "failed",
        "pagesThisRun": pages_this_run,
        "pagesSeen": pages_seen,
        "recordsSeen": records_seen,
        "itemsInserted": items_inserted,
        "resumptionToken": token,
        "complete": status == "completed",
    }


async def task_ndl_oai_fetch_window(
    runId: str,
    setGroup: str = "online",
    metadataPrefix: str = "oai_dc",
    windowStart: str = "",
    windowEnd: str = "",
    shardKey: str = "",
    maxPages: int = 25,
    **_: Any,
) -> dict[str, Any]:
    if (not windowStart or not windowEnd) and shardKey and shardKey.count("|") == 2:
        _sg, windowStart, windowEnd = shardKey.split("|")
        setGroup = setGroup or _sg
    if not windowStart or not windowEnd:
        return {"ok": False, "error": "windowStart/windowEnd required"}
    return await asyncio.to_thread(
        _fetch_window_blocking,
        run_id=runId,
        set_group=setGroup,
        metadata_prefix=metadataPrefix,
        window_start=windowStart,
        window_end=windowEnd,
        max_pages=int(maxPages),
    )


def _verify_blocking(set_group: str, window_start: str, window_end: str) -> dict[str, Any]:
    vid = _checkpoint_vid(SOURCE_ID, set_group, window_start, window_end)
    if True:
        client = get_kotoba_client()
        cp = _read_checkpoint(cur, vid)
        _res = client.q("SELECT count(*) FROM vertex_ndl_bib_item WHERE provider_id = ?", (SOURCE_ID,))
        item_total = int(((_res[0] if _res else None) or [0])[0] or 0)
    verified = bool(cp and cp["status"] == "completed")
    return {
        "ok": True,
        "verified": verified,
        "checkpointStatus": (cp or {}).get("status", "missing"),
        "windowItemsInserted": (cp or {}).get("items_inserted", 0),
        "providerItemTotal": item_total,
    }


async def task_ndl_verify_visibility(
    setGroup: str = "online",
    windowStart: str = "",
    windowEnd: str = "",
    shardKey: str = "",
    **_: Any,
) -> dict[str, Any]:
    if (not windowStart or not windowEnd) and shardKey and shardKey.count("|") == 2:
        _sg, windowStart, windowEnd = shardKey.split("|")
        setGroup = setGroup or _sg
    return await asyncio.to_thread(_verify_blocking, setGroup, windowStart, windowEnd)


async def task_ndl_advance_cursor(
    runId: str,
    sourceId: str = SOURCE_ID,
    shardKey: str = "",
    complete: bool = False,
    **_: Any,
) -> dict[str, Any]:
    if not shardKey:
        return {"ok": False, "error": "missing shard key"}
    cursor_vid = cursor_vertex_id(INGEST_FAMILY, sourceId or SOURCE_ID, shardKey)
    await asyncio.to_thread(
        _spine,
        upsert_cursor,
        ingest_family=INGEST_FAMILY,
        source_id=sourceId or SOURCE_ID,
        shard_key=shardKey,
        cursor_value=shardKey,
        locked_by_run_id=runId,
        status="done" if complete else "active",
    )
    return {"ok": True, "shardKey": shardKey, "cursorVertexId": cursor_vid}


async def task_ndl_complete_run(
    runId: str,
    status: str = "completed",
    itemsInserted: int = 0,
    recordsSeen: int = 0,
    error: str = "",
    **_: Any,
) -> dict[str, Any]:
    await asyncio.to_thread(
        _spine,
        mark_run_finished,
        runId,
        status=status or "completed",
        records_read=int(recordsSeen or 0),
        records_written=int(itemsInserted or 0),
        last_error=error or None,
        output={"itemsInserted": int(itemsInserted or 0)},
    )
    return {"ok": True, "runId": runId, "status": status or "completed"}
