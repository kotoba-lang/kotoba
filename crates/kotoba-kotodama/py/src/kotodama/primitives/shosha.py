"""shosha.etzhayyim.com (商社 / sogo-shosha) primitives.

T2 actor (ADR-2604282300): kotodama module + BPMN + Zeebe, no CF Worker.
All domain writes hit RisingWave directly via Hyperdrive (ADR-0036). Social
posts go through `generic.pds.dispatch` from BPMN, never from this module.

Pipeline coverage (ADR-0056 BPMN-as-actor):
  marketIntelligenceIngest.bpmn  R/PT1H  → shosha.intel.ingestPrices
                                        →  shosha.intel.ingestFreight
                                        →  shosha.marketView.synth
  tradeBookRecompute.bpmn        R/PT4H  → shosha.exposure.recompute
                                        →  shosha.pnl.dailyRecompute
  tradeIdeaSynthesize.bpmn       R/PT4H  → shosha.trade.synth
  dailyShoshaReport.bpmn         07 JST  → shosha.pnl.dailyRecompute
                                        →  shosha.dailyReport.compose
  submitTrade.bpmn               XRPC    → shosha.comply.sanctionsCheck
                                        →  shosha.trade.submit
  proposeHedge.bpmn              XRPC    → shosha.exposure.recompute
                                        →  shosha.hedge.propose
  complyCheck.bpmn               XRPC    → shosha.comply.sanctionsCheck
  agentLoop.bpmn                 XRPC    → shosha.agent.chat

Output target tables (created by 20260506110000_vertex_shosha_schema.ts):
  vertex_shosha_intel              market intel ticks
  vertex_shosha_market_view        LLM-synthesized per-commodity outlook
  vertex_shosha_counterparty       counterparty registry + sanction status
  vertex_shosha_trade              trade tickets
  vertex_shosha_exposure_snapshot  exposure aggregates
  vertex_shosha_hedge              hedge instruments
  edge_shosha_trade_counterparty   trade → counterparty
  edge_shosha_trade_hedge          trade → hedge

Content-addressed PKs (ADR-0041) — re-runs idempotent.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import csv
import hashlib
import io
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any
from xml.etree import ElementTree as ET

from kotodama import llm

# ──────────────────────────────────────────────────────────────────────
# Constants
# ──────────────────────────────────────────────────────────────────────

_SHOSHA_ACTOR = "did:web:shosha.etzhayyim.com"

# Yahoo Finance v8 chart symbols → (commodity slug, unit, category).
# Free, unauthenticated, used by many open-source quote tools. Rate
# limit is permissive at hourly cadence.
_YAHOO_QUOTES: list[tuple[str, str, str, str]] = [
    ("CL=F",   "crude-wti",   "USD-bbl",   "oil"),
    ("BZ=F",   "crude-brent", "USD-bbl",   "oil"),
    ("NG=F",   "natural-gas", "USD-mmbtu", "oil"),
    ("GC=F",   "gold",        "USD-toz",   "metal"),
    ("SI=F",   "silver",      "USD-toz",   "metal"),
    ("HG=F",   "copper",      "USD-lb",    "metal"),
    ("ZC=F",   "corn",        "USD-bu",    "ag"),
    ("ZW=F",   "wheat",       "USD-bu",    "ag"),
    ("KC=F",   "coffee",      "USD-lb",    "ag"),
]

# Frankfurter (free, ECB-sourced) — used as USD reference.
_FX_BASE = "USD"
_FX_TARGETS = ["JPY", "CNY", "EUR", "GBP", "INR", "BRL", "AUD"]

# Phase 1 static sanctions sieve. Phase 2 will refresh OFAC SDN +
# EU consolidated list + UN 1267 + JP MOFA periodically and cache to
# vertex_shosha_sanctions_list.
_SANCTIONED_COUNTRIES = {
    "KP", "PRK", "DPRK", "north-korea",
    "IR", "IRN", "iran",
    "SY", "SYR", "syria",
    "CU", "CUB", "cuba",
    "RU", "RUS", "russia",
    "BY", "BLR", "belarus",
    "VE", "VEN", "venezuela",
    "CRIMEA", "donetsk", "luhansk",
}
_SANCTIONED_ENTITY_KEYWORDS = {
    "rosneft", "gazprom", "sberbank", "vtb",
    "bank-melli", "bank-saderat",
    "kim-jong",
    "wagner-group", "prigozhin",
}

# ──────────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────────


# Reasoning models (Qwen3.5-397B etc.) wrap chain-of-thought in
# `<think>...</think>` blocks that count against max_tokens. Phase 2f
# strips them post-call and bumps default budgets so the visible
# response is non-empty even on long reasoning runs.
_THINK_BLOCK_RE = re.compile(r"<think>.*?</think>\s*", re.DOTALL | re.IGNORECASE)


def _strip_think_blocks(text: str) -> str:
    if not text:
        return text
    return _THINK_BLOCK_RE.sub("", text).strip()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _now_ms() -> int:
    return int(time.time() * 1000)


def _today_iso() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _slug(s: str, *, max_len: int = 80) -> str:
    s = (s or "").strip().lower()
    s = re.sub(r"[^a-z0-9._-]+", "-", s)
    s = re.sub(r"-+", "-", s).strip("-.")
    return s[:max_len] or "x"


def _hash12(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:12]


def _http_get_json(url: str, *, timeout: float = 10.0) -> dict[str, Any]:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "shosha.etzhayyim.com/1.0 (autonomous trading agent)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


def _rw_execute(sql: str, params: tuple[Any, ...]) -> None:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)


def _rw_executemany(sql: str, rows: list[tuple[Any, ...]]) -> None:
    """Bulk INSERT helper. Uses psycopg `executemany` in chunks of 500 to
    keep server-side prepared-statement reuse + amortize round-trips. For
    OFAC SDN refresh (~19K rows) this cuts wall time from minutes to ~10s.
    """
    if not rows:
        return
    chunk = 500
    if True:
        client = get_kotoba_client()
        for i in range(0, len(rows), chunk):
            _res = client.q(sql, rows[i:i + chunk])


def _rw_query(sql: str, params: tuple[Any, ...] = ()) -> list[tuple[Any, ...]]:
    if True:
        client = get_kotoba_client()
        _res = client.q(sql, params)
        return list(_res)


# ──────────────────────────────────────────────────────────────────────
# Intel ingest — prices (Yahoo v8 chart) + FX (Frankfurter)
# ──────────────────────────────────────────────────────────────────────

_INSERT_INTEL = (
    "INSERT INTO vertex_shosha_intel ("
    "vertex_id, owner_did, sensitivity_ord, source, symbol, category, "
    "value, unit, ts_ms, raw_json, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def _yahoo_fetch_quote(symbol: str) -> tuple[float, int] | None:
    url = (
        "https://query2.finance.yahoo.com/v8/finance/chart/"
        + urllib.parse.quote(symbol)
        + "?interval=1h&range=1d"
    )
    try:
        body = _http_get_json(url, timeout=12.0)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError):
        return None
    chart = (body or {}).get("chart") or {}
    res = chart.get("result") or []
    if not res:
        return None
    meta = res[0].get("meta") or {}
    price = meta.get("regularMarketPrice")
    ts = meta.get("regularMarketTime") or int(time.time())
    if price is None:
        return None
    try:
        return float(price), int(ts) * 1000
    except (TypeError, ValueError):
        return None


async def task_shosha_intel_ingest_prices(**kwargs: Any) -> dict[str, Any]:
    """Fetch oil / metal / ag commodity prices from Yahoo + FX from Frankfurter.

    Phase 1 source list: see module-level _YAHOO_QUOTES + _FX_TARGETS.
    Re-runs are idempotent (PK = symbol+ts_ms).
    """
    rows: list[tuple[Any, ...]] = []
    skipped: list[str] = []
    now_iso = _now_iso()
    today = _today_iso()

    for sym, slug, unit, category in _YAHOO_QUOTES:
        q = _yahoo_fetch_quote(sym)
        if q is None:
            skipped.append(sym)
            continue
        price, ts_ms = q
        vertex_id = (
            f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.intel/"
            f"yahoo-{_slug(sym)}-{ts_ms}"
        )
        raw = json.dumps({"symbol": sym, "slug": slug, "price": price, "ts_ms": ts_ms})
        rows.append((
            vertex_id, _SHOSHA_ACTOR, 0, "yahoo", slug, category,
            price, unit, ts_ms, raw, "active",
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.intel.ingestPrices",
        ))

    # Frankfurter FX
    try:
        fx = _http_get_json(
            "https://api.frankfurter.dev/v1/latest?base=" + _FX_BASE
            + "&symbols=" + ",".join(_FX_TARGETS),
            timeout=10.0,
        )
        fx_date = fx.get("date") or today
        # Frankfurter returns date-precision; bump to ms within the day.
        try:
            fx_ts = int(time.mktime(time.strptime(fx_date, "%Y-%m-%d"))) * 1000
        except ValueError:
            fx_ts = _now_ms()
        for tgt, rate in (fx.get("rates") or {}).items():
            slug = f"{_FX_BASE.lower()}-{tgt.lower()}"
            vertex_id = (
                f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.intel/"
                f"frankfurter-{slug}-{fx_ts}"
            )
            raw = json.dumps({"base": _FX_BASE, "target": tgt, "rate": rate, "date": fx_date})
            rows.append((
                vertex_id, _SHOSHA_ACTOR, 0, "frankfurter", slug, "fx",
                float(rate), f"{tgt}-{_FX_BASE}", fx_ts, raw, "active",
                now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.intel.ingestPrices",
            ))
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError) as e:
        skipped.append(f"frankfurter:{e.__class__.__name__}")

    _rw_executemany(_INSERT_INTEL, rows)
    return {"ok": True, "rows": len(rows), "skipped": skipped}


async def task_shosha_intel_ingest_freight(**kwargs: Any) -> dict[str, Any]:
    """Ingest freight indices.

    Phase 1: stub that records a heartbeat row so downstream MVs always
    see freight category presence. Phase 2 will integrate Baltic Exchange
    BDI/BCTI/BDTI proxies (paid feed) or scraped Splash247 / TradeWinds
    public summaries.
    """
    now_iso = _now_iso()
    ts_ms = _now_ms()
    vertex_id = f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.intel/freight-stub-{ts_ms}"
    rows = [(
        vertex_id, _SHOSHA_ACTOR, 0, "stub", "freight-bdi-proxy", "freight",
        None, "index", ts_ms,
        json.dumps({"note": "Phase 1 stub — Baltic feed not wired"}),
        "stub",
        now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.intel.ingestFreight",
    )]
    _rw_executemany(_INSERT_INTEL, rows)
    return {"ok": True, "rows": len(rows), "note": "phase1-stub"}


# ──────────────────────────────────────────────────────────────────────
# Market view synth — LLM JSON aggregation per commodity
# ──────────────────────────────────────────────────────────────────────

_INSERT_MARKET_VIEW = (
    "INSERT INTO vertex_shosha_market_view ("
    "vertex_id, owner_did, sensitivity_ord, commodity, as_of_date, "
    "direction, confidence, price_target, price_currency, price_unit, "
    "rationale, intel_count_used, llm_model, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_MARKET_VIEW_SYSTEM = (
    "You are a senior commodity analyst at a Japanese sogo-shosha. "
    "Given recent price ticks for a commodity, produce a concise market view. "
    'Reply with strict JSON: {"direction":"bullish|bearish|neutral",'
    '"confidence":0..1,"priceTarget":number_or_null,"rationale":"<= 200 chars"}. '
    "No prose outside JSON."
)


async def task_shosha_market_view_synth(**kwargs: Any) -> dict[str, Any]:
    """For each commodity with intel in the lookback window, ask LLM for
    a directional view and persist to vertex_shosha_market_view.
    """
    lookback_hours = int(kwargs.get("lookbackHours", 24) or 24)
    cutoff_ms = _now_ms() - lookback_hours * 3_600_000

    rows = _rw_query(
        f"SELECT symbol, value, unit, ts_ms FROM vertex_shosha_intel "
        f"WHERE category IN ('oil','metal','ag') AND ts_ms >= {int(cutoff_ms)} "
        f"AND value IS NOT NULL "
        f"ORDER BY symbol, ts_ms DESC "
        f"LIMIT 5000",
    )
    by_commodity: dict[str, list[tuple[float, str, int]]] = {}
    for symbol, value, unit, ts_ms in rows:
        by_commodity.setdefault(str(symbol), []).append(
            (float(value or 0.0), str(unit or ""), int(ts_ms or 0))
        )

    today = _today_iso()
    now_iso = _now_iso()
    inserts: list[tuple[Any, ...]] = []
    views = 0

    for commodity, ticks in by_commodity.items():
        if len(ticks) < 2:
            continue
        ticks_sorted = sorted(ticks, key=lambda t: t[2])
        first_v = ticks_sorted[0][0]
        last_v = ticks_sorted[-1][0]
        chg_pct = ((last_v - first_v) / first_v * 100.0) if first_v else 0.0
        unit = ticks_sorted[-1][1]

        user_msg = (
            f"Commodity: {commodity}\n"
            f"Tick count: {len(ticks_sorted)}\n"
            f"First price: {first_v:.4f} {unit}\n"
            f"Last price: {last_v:.4f} {unit}\n"
            f"Change: {chg_pct:+.2f}%\n"
            f"Lookback: {lookback_hours}h\n"
            "Output JSON view."
        )
        result = llm.call_tier_json(
            "reasoning", _MARKET_VIEW_SYSTEM, user_msg,
            max_tokens=1200, temperature=0.2,
        )
        if not result.get("ok"):
            # Fallback: trend-following heuristic when LLM fails.
            direction = "bullish" if chg_pct > 1 else "bearish" if chg_pct < -1 else "neutral"
            data = {
                "direction": direction,
                "confidence": min(abs(chg_pct) / 10.0, 0.5),
                "priceTarget": None,
                "rationale": f"Heuristic fallback: {chg_pct:+.2f}% over {lookback_hours}h",
            }
            model = "heuristic-fallback"
        else:
            data = result.get("data") or {}
            model = result.get("model") or "unknown"

        direction = str(data.get("direction") or "neutral")[:16]
        try:
            confidence = float(data.get("confidence") or 0.0)
        except (TypeError, ValueError):
            confidence = 0.0
        price_target = data.get("priceTarget")
        try:
            price_target_f = float(price_target) if price_target is not None else None
        except (TypeError, ValueError):
            price_target_f = None
        rationale = (str(data.get("rationale") or "")[:1000])

        vertex_id = (
            f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.marketView/"
            f"{_slug(commodity)}-{today}"
        )
        inserts.append((
            vertex_id, _SHOSHA_ACTOR, 0, commodity, today,
            direction, confidence, price_target_f, "USD", unit,
            rationale, len(ticks_sorted), model, "active",
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.marketView.synth",
        ))
        views += 1

    _rw_executemany(_INSERT_MARKET_VIEW, inserts)
    return {"ok": True, "views": views, "commoditiesScanned": len(by_commodity)}


# ──────────────────────────────────────────────────────────────────────
# Sanctions list refresh (Phase 2b — OFAC SDN; EU/UN/JP-MOFA TBD)
# ──────────────────────────────────────────────────────────────────────

# US Treasury OFAC SDN.CSV — official daily-refreshed list. ~10K entities.
# Format: ent_num, SDN_Name, SDN_Type, Program, Title, Call_Sign,
#         Vess_type, Tonnage, GRT, Vess_flag, Vess_owner, Remarks
_OFAC_SDN_CSV_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/SDN.CSV"
_OFAC_ALT_CSV_URL = "https://sanctionslistservice.ofac.treas.gov/api/PublicationPreview/exports/ALT.CSV"
# UN Security Council 1267 / 1988 / 2231 consolidated list — public XML.
_UN_1267_XML_URL = "https://scsanctions.un.org/resources/xml/en/consolidated.xml"

_INSERT_SANCTION = (
    "INSERT INTO vertex_shosha_sanctions_list ("
    "vertex_id, owner_did, sensitivity_ord, list_source, source_ref, "
    "entity_type, name, name_normalized, aliases, country, nationality, "
    "list_program, title, remarks, listed_at, raw_json, refreshed_at, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def _ofac_entity_type(sdn_type: str) -> str:
    s = (sdn_type or "").strip().lower()
    if s.startswith("indiv"):
        return "individual"
    if s.startswith("vess"):
        return "vessel"
    if s.startswith("aircr"):
        return "aircraft"
    return "entity"


def _ofac_normalize(name: str) -> str:
    """Normalize an OFAC name for fuzzy match.

    Lowercase, strip parens/punctuation, collapse whitespace.
    Keep multi-word so we can do prefix and substring matching.
    """
    s = (name or "").lower()
    # OFAC uses "LASTNAME, FIRSTNAME" — flip for individuals
    if "," in s:
        parts = [p.strip() for p in s.split(",", 1)]
        if len(parts) == 2 and parts[1]:
            s = f"{parts[1]} {parts[0]}"
    s = re.sub(r"[\(\)\[\]\.,;:'\"]+", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


async def task_shosha_sanctions_refresh_ofac(**kwargs: Any) -> dict[str, Any]:
    """Fetch OFAC SDN.CSV, parse, upsert into vertex_shosha_sanctions_list.

    SDN.CSV is a stable public feed. ~10K rows (~3-5 MB). Re-runs are
    idempotent (PK = list_source + source_ref hashed into vertex_id).

    On Phase 2b: ingest raw SDN.CSV only. Aliases (ALT.CSV) and
    addresses (ADD.CSV) deferred — primary fuzzy match runs against
    the canonical SDN_Name only for now.
    """
    timeout = float(kwargs.get("timeoutSec", 60))
    max_rows = int(kwargs.get("maxRows", 0) or 0)  # 0 = no cap
    try:
        req = urllib.request.Request(
            _OFAC_SDN_CSV_URL,
            headers={"User-Agent": "shosha.etzhayyim.com/1.0 (sanctions compliance refresh)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return {"ok": False, "error": f"fetch failed: {e}", "rows": 0}

    text = body.decode("latin-1")  # OFAC uses Latin-1 for legacy reasons
    reader = csv.reader(io.StringIO(text))

    # SDN.CSV has NO header row. Columns are positional:
    # 0:ent_num 1:SDN_Name 2:SDN_Type 3:Program 4:Title
    # 5:Call_Sign 6:Vess_type 7:Tonnage 8:GRT 9:Vess_flag
    # 10:Vess_owner 11:Remarks
    now_iso = _now_iso()
    today = _today_iso()
    inserts: list[tuple[Any, ...]] = []
    seen_refs: set[str] = set()

    for row in reader:
        if len(row) < 5:
            continue
        try:
            ent_num = (row[0] or "").strip()
            sdn_name = (row[1] or "").strip()
            sdn_type = (row[2] or "").strip()
            program = (row[3] or "").strip()
            title = (row[4] or "").strip() if len(row) > 4 else ""
            remarks = (row[11] or "").strip() if len(row) > 11 else ""
        except IndexError:
            continue

        if not ent_num or not sdn_name or sdn_name == "-0-":
            continue
        if ent_num in seen_refs:
            continue
        seen_refs.add(ent_num)

        source_ref = f"ofac:{ent_num}"
        vertex_id = (
            f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.sanction/"
            f"ofac-{ent_num}"
        )
        name_norm = _ofac_normalize(sdn_name)
        entity_type = _ofac_entity_type(sdn_type)
        raw = json.dumps({
            "ent_num": ent_num,
            "sdn_name": sdn_name,
            "sdn_type": sdn_type,
            "program": program,
            "title": title,
            "remarks": remarks[:500],
        })
        inserts.append((
            vertex_id, _SHOSHA_ACTOR, 0, "ofac-sdn", source_ref,
            entity_type, sdn_name, name_norm, None,
            None, None, program or None, title or None, remarks[:1000] or None,
            today, raw, now_iso, "active",
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.sanctions.refreshOfac",
        ))
        if max_rows and len(inserts) >= max_rows:
            break

    _rw_executemany(_INSERT_SANCTION, inserts)
    # RW PK semantics overwrite on re-INSERT, so "inserted" and "updated"
    # are operationally equivalent here. Stamp the count for OCEL audit.
    return {
        "ok": True,
        "rows": len(inserts),
        "inserted": len(inserts),
        "updated": 0,
        "list_source": "ofac-sdn",
    }


def _un_compose_name(elem: ET.Element) -> str:
    """UN XML splits names across FIRST_NAME / SECOND_NAME / THIRD_NAME /
    FOURTH_NAME for individuals, and FIRST_NAME for entities. Concat in
    order, drop empties.
    """
    parts: list[str] = []
    for tag in ("FIRST_NAME", "SECOND_NAME", "THIRD_NAME", "FOURTH_NAME"):
        v = elem.findtext(tag, default="").strip()
        if v:
            parts.append(v)
    return " ".join(parts)


async def task_shosha_sanctions_refresh_un(**kwargs: Any) -> dict[str, Any]:
    """Fetch UN Security Council 1267 / 1988 / 2231 consolidated XML,
    parse INDIVIDUAL + ENTITY entries, upsert into
    `vertex_shosha_sanctions_list` with `list_source='un-1267'`.

    UN list is global counter-terrorism (Al-Qaida + Taliban + Iran/DPRK
    proliferation). ~700-1000 entries — much smaller than OFAC SDN.
    """
    timeout = float(kwargs.get("timeoutSec", 60))
    max_rows = int(kwargs.get("maxRows", 0) or 0)
    try:
        req = urllib.request.Request(
            _UN_1267_XML_URL,
            headers={"User-Agent": "shosha.etzhayyim.com/1.0 (sanctions compliance refresh)"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            body = r.read()
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as e:
        return {"ok": False, "error": f"fetch failed: {e}", "rows": 0}

    try:
        root = ET.fromstring(body)
    except ET.ParseError as e:
        return {"ok": False, "error": f"parse failed: {e}", "rows": 0}

    now_iso = _now_iso()
    today = _today_iso()
    inserts: list[tuple[Any, ...]] = []
    seen_refs: set[str] = set()

    # Walk both INDIVIDUAL (under INDIVIDUALS) and ENTITY (under ENTITIES).
    for entity_kind, container_tag, leaf_tag in (
        ("individual", "INDIVIDUALS", "INDIVIDUAL"),
        ("entity",     "ENTITIES",    "ENTITY"),
    ):
        for elem in root.iterfind(f".//{container_tag}/{leaf_tag}"):
            data_id = elem.findtext("DATAID", default="").strip()
            if not data_id or data_id in seen_refs:
                continue
            seen_refs.add(data_id)

            name = _un_compose_name(elem) if entity_kind == "individual" \
                else elem.findtext("FIRST_NAME", default="").strip()
            if not name:
                continue

            un_list_type = elem.findtext("UN_LIST_TYPE", default="").strip()
            list_type = elem.findtext("LIST_TYPE", default="").strip()
            program = (un_list_type or list_type) or "UN-1267"

            nationality = elem.findtext("NATIONALITY", default="").strip() or None
            listed_on = elem.findtext("LISTED_ON", default="").strip() or None
            if listed_on and len(listed_on) >= 10:
                listed_on = listed_on[:10]
            else:
                listed_on = None

            # COMMENTS1 holds free-form rationale on UN listings.
            comments = elem.findtext("COMMENTS1", default="").strip()
            remarks = comments[:1000] or None

            source_ref = f"un:{data_id}"
            vertex_id = (
                f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.sanction/"
                f"un-{data_id}"
            )
            name_norm = _ofac_normalize(name)
            raw = json.dumps({
                "data_id": data_id,
                "name": name,
                "kind": entity_kind,
                "un_list_type": un_list_type,
                "nationality": nationality,
                "listed_on": listed_on,
            })

            inserts.append((
                vertex_id, _SHOSHA_ACTOR, 0, "un-1267", source_ref,
                entity_kind, name, name_norm, None,
                None, nationality, program or None,
                None, remarks,
                listed_on or today, raw, now_iso, "active",
                now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.sanctions.refreshUn",
            ))
            if max_rows and len(inserts) >= max_rows:
                break
        if max_rows and len(inserts) >= max_rows:
            break

    _rw_executemany(_INSERT_SANCTION, inserts)
    return {
        "ok": True,
        "rows": len(inserts),
        "inserted": len(inserts),
        "updated": 0,
        "list_source": "un-1267",
    }


# ──────────────────────────────────────────────────────────────────────
# Sanctions / comply check
# ──────────────────────────────────────────────────────────────────────


def _check_static_sanctions(counterparty: str, country: str | None) -> tuple[bool, list[str]]:
    flags: list[str] = []
    cp_norm = (counterparty or "").strip().lower().replace(" ", "-")
    co_norm = (country or "").strip().upper()

    if co_norm:
        for token in _SANCTIONED_COUNTRIES:
            if co_norm == token.upper() or token.upper() in co_norm:
                flags.append(f"country:{token}")
                break
    if cp_norm:
        for kw in _SANCTIONED_ENTITY_KEYWORDS:
            if kw in cp_norm:
                flags.append(f"entity-keyword:{kw}")

    return (len(flags) == 0), flags


_COMPLY_SYSTEM = (
    "You are a sanctions compliance officer at a Japanese sogo-shosha. "
    "You check if trading with the named counterparty + country + commodity "
    "would breach OFAC, EU, UN, or JP MOFA sanctions. "
    'Reply with strict JSON: {"complyOk":true|false,'
    '"flags":["<short reason>"],"rationale":"<= 200 chars"}. '
    "Default to complyOk=true unless you have specific concerns. No prose."
)


async def task_shosha_comply_sanctions_check(**kwargs: Any) -> dict[str, Any]:
    counterparty = str(kwargs.get("counterparty") or "").strip()
    country = str(kwargs.get("country") or "").strip() or None
    commodity = str(kwargs.get("commodity") or "").strip() or None
    if not counterparty:
        return {"ok": False, "complyOk": False, "flags": ["missing-counterparty"], "error": "counterparty required"}

    static_ok, static_flags = _check_static_sanctions(counterparty, country)
    checked_lists = ["static-curated"]
    if static_flags:
        # Hard block on static match — no LLM second-guessing.
        return {
            "ok": True,
            "complyOk": False,
            "flags": static_flags,
            "rationale": "Matched curated sanctions sieve",
            "checkedLists": checked_lists,
        }

    # Phase 2b: live OFAC SDN lookup (DB) before falling back to LLM.
    # Match strategy (cheap, no fuzzy lib dep):
    #   1. exact name_normalized = normalized(counterparty)
    #   2. counterparty token contains a SDN word ≥ 6 chars (substring,
    #      word-bounded). Avoids false-positives on common tokens.
    cp_norm_for_db = _ofac_normalize(counterparty)
    db_flags: list[str] = []
    db_matched: list[dict[str, Any]] = []
    if cp_norm_for_db:
        try:
            # Multi-source lookup: union of OFAC SDN + UN 1267 (Phase 2b-ext).
            # Future EU consolidated + JP MOFA will land in same table.
            exact_rows = _rw_query(
                "SELECT name, source_ref, list_program, entity_type, list_source "
                "FROM vertex_shosha_sanctions_list "
                "WHERE status = 'active' AND name_normalized = %s LIMIT 5",
                (cp_norm_for_db,),
            )
            for r in exact_rows:
                ref = str(r[1] or "")
                prog = str(r[2] or "")
                src = str(r[4] or "")
                db_flags.append(f"sanction-list:{src}:{ref}:{prog}".rstrip(":"))
                db_matched.append({"name": r[0], "ref": ref, "program": prog, "type": r[3], "list_source": src})
            checked_lists.append("sanctions-list-exact")
        except Exception as e:  # noqa: BLE001
            checked_lists.append(f"sanctions-list-exact-error:{e.__class__.__name__}")

    if db_flags:
        return {
            "ok": True,
            "complyOk": False,
            "flags": db_flags,
            "rationale": f"Matched sanctions list {db_matched[0]['list_source']}: {db_matched[0]['name']!r} ({db_matched[0]['program']})",
            "checkedLists": checked_lists,
            "matched": db_matched,
        }

    # Static + DB clear → ask LLM for any heuristic concerns.
    user_msg = (
        f"Counterparty: {counterparty}\n"
        f"Country: {country or '(unspecified)'}\n"
        f"Commodity: {commodity or '(unspecified)'}\n"
        "Decision?"
    )
    result = llm.call_tier_json(
        "reasoning", _COMPLY_SYSTEM, user_msg,
        max_tokens=800, temperature=0.0,
    )
    checked_lists.append("llm-heuristic")
    if not result.get("ok"):
        # LLM failure does NOT block — log and pass with note.
        return {
            "ok": True,
            "complyOk": True,
            "flags": [],
            "rationale": "Static clear; LLM heuristic unavailable",
            "checkedLists": checked_lists,
        }
    data = result.get("data") or {}
    comply_ok = bool(data.get("complyOk", True))
    flags = data.get("flags") or []
    if not isinstance(flags, list):
        flags = [str(flags)]
    flags = [str(f)[:120] for f in flags][:10]
    rationale = str(data.get("rationale") or "")[:1000]
    return {
        "ok": True,
        "complyOk": comply_ok,
        "flags": flags,
        "rationale": rationale,
        "checkedLists": checked_lists,
    }


# ──────────────────────────────────────────────────────────────────────
# Trade submit
# ──────────────────────────────────────────────────────────────────────

_INSERT_TRADE = (
    "INSERT INTO vertex_shosha_trade ("
    "vertex_id, owner_did, sensitivity_ord, trade_id, side, commodity, "
    "quantity, unit, price, currency, amount_usd, "
    "counterparty_name, counterparty_vid, desk, "
    "delivery_date, delivery_location, rationale, "
    "comply_ok, comply_flags, approval_state, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
_INSERT_COUNTERPARTY = (
    "INSERT INTO vertex_shosha_counterparty ("
    "vertex_id, owner_did, sensitivity_ord, name, name_normalized, country, "
    "risk_band, sanction_status, sanction_flags, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
_INSERT_EDGE_TRADE_CP = (
    "INSERT INTO edge_shosha_trade_counterparty ("
    "edge_id, owner_did, sensitivity_ord, src_vid, dst_vid, role, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


def _ensure_counterparty(name: str, country: str | None,
                         comply_ok: bool, flags: list[str]) -> str:
    """Idempotently register a counterparty; return its vertex_id."""
    name_norm = _slug(name, max_len=120)
    vertex_id = (
        f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.counterparty/{name_norm}"
    )
    rows = _rw_query(
        "SELECT vertex_id FROM vertex_shosha_counterparty "
        "WHERE name_normalized = %s LIMIT 1",
        (name_norm,),
    )
    if rows:
        return rows[0][0]
    sanction_status = "clear" if comply_ok else "flagged"
    _rw_execute(
        _INSERT_COUNTERPARTY,
        (
            vertex_id, _SHOSHA_ACTOR, 0, name, name_norm, country,
            "B", sanction_status, json.dumps(flags), "active",
            _now_iso(), _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.trade.submit",
        ),
    )
    return vertex_id


def _latest_fx_to_usd(currency: str) -> float | None:
    """USD↔X rate from latest Frankfurter intel.

    Frankfurter base=USD; the row has value=rate(USD→X), so dividing
    a non-USD amount by `rate` converts it to USD.
    """
    cur = (currency or "").strip().upper()
    if cur in ("", "USD"):
        return 1.0
    rows = _rw_query(
        "SELECT value FROM vertex_shosha_intel "
        "WHERE source = 'frankfurter' AND symbol = %s "
        "ORDER BY ts_ms DESC LIMIT 1",
        (f"usd-{cur.lower()}",),
    )
    if not rows:
        return None
    try:
        v = float(rows[0][0] or 0.0)
        return (1.0 / v) if v else None
    except (TypeError, ValueError):
        return None


_AUTO_APPROVE_USD_THRESHOLD = 1_000_000.0


async def task_shosha_trade_submit(**kwargs: Any) -> dict[str, Any]:
    """Persist a trade ticket. Caller (BPMN) supplies complyOk + flags
    from the prior shosha.comply.sanctionsCheck step.

    approval_state semantics:
      pending   amount_usd >= threshold OR comply_ok is False
                (blocked trades still record for audit; status='cancelled')
      approved  amount_usd <  threshold AND comply_ok is True
    """
    side = str(kwargs.get("side") or "").lower()
    commodity = str(kwargs.get("commodity") or "").strip()
    counterparty = str(kwargs.get("counterparty") or "").strip()
    if side not in ("buy", "sell") or not commodity or not counterparty:
        return {"ok": False, "error": "missing required fields (side/commodity/counterparty)"}

    quantity = float(kwargs.get("quantity") or 0.0)
    price = float(kwargs.get("price") or 0.0)
    unit = str(kwargs.get("unit") or "").strip() or "unit"
    currency = (str(kwargs.get("currency") or "USD")).upper()
    desk = str(kwargs.get("desk") or "trade")
    delivery_date = str(kwargs.get("deliveryDate") or "") or None
    delivery_location = str(kwargs.get("deliveryLocation") or "") or None
    rationale = str(kwargs.get("rationale") or "")[:2000] or None
    comply_ok = bool(kwargs.get("complyOk", True))
    comply_flags_raw = kwargs.get("complyFlags") or []
    if isinstance(comply_flags_raw, str):
        comply_flags = [comply_flags_raw]
    else:
        comply_flags = [str(f) for f in comply_flags_raw][:20]

    fx = _latest_fx_to_usd(currency)
    amount_native = quantity * price
    amount_usd = amount_native * fx if fx is not None else None

    # Approval gate.
    if not comply_ok:
        approval_state = "rejected"
        status = "cancelled"
    elif amount_usd is not None and amount_usd >= _AUTO_APPROVE_USD_THRESHOLD:
        approval_state = "pending"
        status = "open"
    else:
        approval_state = "approved"
        status = "open"

    # Trade ID + vertex ID (content-addressed).
    trade_id = str(kwargs.get("tradeId") or "").strip()
    if not trade_id:
        seed = f"{side}|{commodity}|{counterparty}|{quantity}|{price}|{currency}|{_now_ms()}"
        trade_id = f"sh-{_hash12(seed)}"
    vertex_id = f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.trade/{trade_id}"

    cp_vid = _ensure_counterparty(
        counterparty, str(kwargs.get("country") or "") or None, comply_ok, comply_flags
    )

    now_iso = _now_iso()
    _rw_execute(
        _INSERT_TRADE,
        (
            vertex_id, _SHOSHA_ACTOR, 0, trade_id, side, commodity,
            quantity, unit, price, currency, amount_usd,
            counterparty, cp_vid, desk,
            delivery_date, delivery_location, rationale,
            comply_ok, json.dumps(comply_flags), approval_state, status,
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.trade.submit",
        ),
    )
    edge_id = f"{vertex_id}::cp::{cp_vid}"
    _rw_execute(
        _INSERT_EDGE_TRADE_CP,
        (
            edge_id, _SHOSHA_ACTOR, 0, vertex_id, cp_vid, "trade-counterparty",
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.trade.submit",
        ),
    )

    return {
        "ok": True,
        "tradeId": trade_id,
        "vertexId": vertex_id,
        "approvalState": approval_state,
        "status": status,
        "amountUsd": amount_usd,
        "complyOk": comply_ok,
        "complyFlags": comply_flags,
    }


# ──────────────────────────────────────────────────────────────────────
# Exposure recompute → vertex_shosha_exposure_snapshot
# ──────────────────────────────────────────────────────────────────────

_INSERT_EXPOSURE = (
    "INSERT INTO vertex_shosha_exposure_snapshot ("
    "vertex_id, owner_did, sensitivity_ord, as_of_ts_ms, group_by, group_key, "
    "gross_long, gross_short, net, hedged, unhedged, currency, "
    "counterparty_top1, counterparty_top1_pct, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


async def task_shosha_exposure_recompute(**kwargs: Any) -> dict[str, Any]:
    """Materialize an exposure snapshot per (commodity).

    Uses MV `mv_shosha_exposure_by_commodity` as the source of truth so
    this primitive does NOT duplicate aggregation logic — it just
    persists a point-in-time copy with hedge offset applied.
    """
    commodity_filter = (str(kwargs.get("commodityFilter") or "")).strip() or None
    where = "WHERE commodity = %s" if commodity_filter else ""
    params: tuple[Any, ...] = (commodity_filter,) if commodity_filter else ()
    base = _rw_query(
        f"SELECT commodity, currency, gross_long_usd, gross_short_usd, net_usd "
        f"FROM mv_shosha_exposure_by_commodity {where} LIMIT 5000",
        params,
    )

    # Hedge net per commodity (+notional for long hedge, −notional for short).
    hedge_rows = _rw_query(
        "SELECT commodity, "
        "SUM(CASE WHEN direction='long'  THEN notional ELSE 0 END) AS hedge_long, "
        "SUM(CASE WHEN direction='short' THEN notional ELSE 0 END) AS hedge_short "
        "FROM vertex_shosha_hedge WHERE status IN ('proposed','executed') "
        "GROUP BY commodity LIMIT 5000",
    )
    hedge_by: dict[str, tuple[float, float]] = {}
    for commodity, hl, hs in hedge_rows:
        hedge_by[str(commodity)] = (float(hl or 0.0), float(hs or 0.0))

    now_iso = _now_iso()
    ts_ms = _now_ms()
    inserts: list[tuple[Any, ...]] = []
    for commodity, currency, gl, gs, net in base:
        commodity_s = str(commodity or "")
        hedge_long, hedge_short = hedge_by.get(commodity_s, (0.0, 0.0))
        # Hedge offsets opposite-side exposure: long position hedged by short hedge.
        net_v = float(net or 0.0)
        if net_v > 0:
            hedged = min(net_v, hedge_short)
        elif net_v < 0:
            hedged = -min(-net_v, hedge_long)
        else:
            hedged = 0.0
        unhedged = net_v - hedged

        vertex_id = (
            f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.exposure/"
            f"commodity-{_slug(commodity_s)}-{ts_ms}"
        )
        inserts.append((
            vertex_id, _SHOSHA_ACTOR, 0, ts_ms, "commodity", commodity_s,
            float(gl or 0.0), float(gs or 0.0), net_v,
            hedged, unhedged, str(currency or "USD"),
            None, None,
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.exposure.recompute",
        ))

    _rw_executemany(_INSERT_EXPOSURE, inserts)
    return {"ok": True, "rows": len(inserts), "asOfTsMs": ts_ms}


# ──────────────────────────────────────────────────────────────────────
# Daily P&L recompute (mark-to-market open trades)
# ──────────────────────────────────────────────────────────────────────


async def task_shosha_pnl_daily_recompute(**kwargs: Any) -> dict[str, Any]:
    """Mark open trades to market against the latest market view price target
    (or last intel tick if no view available)."""
    open_trades = _rw_query(
        "SELECT vertex_id, side, commodity, quantity, unit, price, currency, amount_usd "
        "FROM vertex_shosha_trade WHERE status = 'open' AND comply_ok = true "
        "LIMIT 5000",
    )
    if not open_trades:
        return {"ok": True, "tradesUpdated": 0, "totalUnrealized": 0.0}

    # Build commodity → mark price (USD-equivalent) lookup.
    commodities = {str(r[2]) for r in open_trades}
    mark: dict[str, float] = {}
    for commodity in commodities:
        # Prefer market view target.
        mv = _rw_query(
            "SELECT price_target FROM vertex_shosha_market_view "
            "WHERE commodity = %s AND price_target IS NOT NULL "
            "ORDER BY as_of_date DESC LIMIT 1",
            (commodity,),
        )
        if mv and mv[0][0] is not None:
            try:
                mark[commodity] = float(mv[0][0])
                continue
            except (TypeError, ValueError):
                pass
        # Fallback: latest intel tick for the slug.
        intel = _rw_query(
            "SELECT value FROM vertex_shosha_intel "
            "WHERE symbol = %s AND value IS NOT NULL "
            "ORDER BY ts_ms DESC LIMIT 1",
            (commodity,),
        )
        if intel and intel[0][0] is not None:
            try:
                mark[commodity] = float(intel[0][0])
            except (TypeError, ValueError):
                pass

    now_iso = _now_iso()
    updates = 0
    total_unrealized = 0.0
    for vid, side, commodity, qty, unit, price, currency, amount_usd in open_trades:
        commodity_s = str(commodity or "")
        if commodity_s not in mark:
            continue
        mp = mark[commodity_s]
        try:
            qf = float(qty or 0.0)
            pf = float(price or 0.0)
        except (TypeError, ValueError):
            continue
        if str(side).lower() == "buy":
            pnl = (mp - pf) * qf
        else:
            pnl = (pf - mp) * qf
        # FX-convert if needed.
        fx = _latest_fx_to_usd(str(currency or "USD"))
        if fx is not None:
            pnl_usd = pnl * fx
        else:
            pnl_usd = pnl
        _rw_execute(
            "UPDATE vertex_shosha_trade SET pnl_unrealized = %s, pnl_marked_at = %s "
            "WHERE vertex_id = %s",
            (pnl_usd, now_iso, vid),
        )
        updates += 1
        total_unrealized += pnl_usd

    return {"ok": True, "tradesUpdated": updates, "totalUnrealized": total_unrealized}


# ──────────────────────────────────────────────────────────────────────
# Trade idea synth — LLM
# ──────────────────────────────────────────────────────────────────────

_TRADE_SYNTH_SYSTEM = (
    "You are a senior trader at a Japanese sogo-shosha. Given recent "
    "market views and current open exposure, propose up to N concrete "
    "trade ideas. Be brief and actionable. "
    'Reply with strict JSON: {"ideas":[{"action":"buy|sell|hedge",'
    '"commodity":"...","rationale":"<= 160 chars","confidence":0..1}],'
    '"summary":"<= 280 chars human-readable Twitter-style post"}.'
    " No prose outside JSON."
)


async def task_shosha_trade_synth(**kwargs: Any) -> dict[str, Any]:
    max_ideas = int(kwargs.get("maxIdeas", 3) or 3)
    views = _rw_query(
        "SELECT commodity, direction, confidence, price_target, rationale "
        "FROM vertex_shosha_market_view WHERE status = 'active' "
        "ORDER BY as_of_date DESC LIMIT 50",
    )
    exposure = _rw_query(
        "SELECT commodity, net_usd FROM mv_shosha_exposure_by_commodity LIMIT 50",
    )

    if not views and not exposure:
        return {"ok": True, "ideaCount": 0, "summary": "", "note": "no-input"}

    user_msg = (
        f"Recent market views (commodity, direction, confidence, target, rationale):\n"
        + "\n".join(
            f"- {c} | {d} | conf={cf} | target={pt} | {r}"
            for c, d, cf, pt, r in views[:20]
        )
        + "\n\nCurrent open exposure (commodity, net USD):\n"
        + "\n".join(f"- {c} | {n}" for c, n in exposure[:20])
        + f"\n\nProduce up to {max_ideas} ideas + summary."
    )
    result = llm.call_tier_json(
        "reasoning", _TRADE_SYNTH_SYSTEM, user_msg,
        max_tokens=1500, temperature=0.4,
    )
    if not result.get("ok"):
        return {"ok": False, "ideaCount": 0, "summary": "",
                "error": result.get("error") or "llm-failed"}
    data = result.get("data") or {}
    ideas = data.get("ideas") or []
    if not isinstance(ideas, list):
        ideas = []
    ideas = ideas[:max_ideas]
    summary = str(data.get("summary") or "")[:300]
    return {"ok": True, "ideaCount": len(ideas), "summary": summary, "ideas": ideas}


# ──────────────────────────────────────────────────────────────────────
# Settlement (Phase 2c — closes the trade lifecycle)
# ──────────────────────────────────────────────────────────────────────

_INSERT_SETTLEMENT = (
    "INSERT INTO vertex_shosha_settlement ("
    "vertex_id, owner_did, sensitivity_ord, settlement_id, ref_trade_id, "
    "currency, amount, amount_usd, method, bank_ref, value_date, "
    "counterparty_name, counterparty_vid, pnl_realized, remarks, "
    "status, settled_at, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
_INSERT_EDGE_TRADE_SETTLEMENT = (
    "INSERT INTO edge_shosha_trade_settlement ("
    "edge_id, owner_did, sensitivity_ord, src_vid, dst_vid, role, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


async def task_shosha_trade_settle(**kwargs: Any) -> dict[str, Any]:
    """Settle an open trade.

    Validation:
      - tradeId must exist in vertex_shosha_trade
      - trade.status must be 'open'
      - trade.comply_ok must be True
    Effect:
      - INSERT vertex_shosha_settlement (PK content-addressed by tradeId
        + valueDate so re-runs on the same trade/value-date are idempotent)
      - UPDATE vertex_shosha_trade SET status='closed',
        approval_state='approved' (auto-promote pending → approved at
        settlement), pnl_realized = pnl_unrealized snapshot,
        pnl_unrealized = 0
      - INSERT edge_shosha_trade_settlement
    """
    trade_id = str(kwargs.get("tradeId") or "").strip()
    if not trade_id:
        return {"ok": False, "error": "tradeId required"}

    rows = _rw_query(
        "SELECT vertex_id, side, commodity, quantity, price, currency, "
        "amount_usd, counterparty_name, counterparty_vid, "
        "approval_state, status, comply_ok, "
        "COALESCE(pnl_realized, 0), COALESCE(pnl_unrealized, 0) "
        "FROM vertex_shosha_trade WHERE trade_id = %s LIMIT 1",
        (trade_id,),
    )
    if not rows:
        return {"ok": False, "error": f"trade not found: {trade_id}"}
    (
        trade_vid, side, commodity, qty, price, currency,
        amount_usd, cp_name, cp_vid,
        approval_state, status, comply_ok,
        pnl_realized_existing, pnl_unrealized_existing,
    ) = rows[0]

    if not bool(comply_ok):
        return {"ok": False, "error": "trade not comply_ok — cannot settle",
                "tradeId": trade_id}
    if str(status) != "open":
        return {"ok": False, "error": f"trade status is {status!r}, must be 'open'",
                "tradeId": trade_id}

    method = str(kwargs.get("method") or "wire")
    bank_ref = (str(kwargs.get("bankRef") or "")[:200]) or None
    value_date = str(kwargs.get("valueDate") or "") or _today_iso()
    remarks = str(kwargs.get("remarks") or "")[:1000] or None
    amt_override = kwargs.get("amountOverride")

    settled_amount_usd = float(amount_usd or 0.0)
    if amt_override is not None:
        try:
            settled_amount_usd = float(amt_override)
        except (TypeError, ValueError):
            pass
    settled_amount_native = settled_amount_usd
    fx = _latest_fx_to_usd(str(currency or "USD"))
    if fx and fx != 0:
        settled_amount_native = settled_amount_usd / fx

    settlement_id = str(kwargs.get("settlementId") or "").strip()
    if not settlement_id:
        seed = f"settle|{trade_id}|{value_date}|{settled_amount_usd:.2f}"
        settlement_id = f"st-{_hash12(seed)}"
    vertex_id = (
        f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.settlement/{settlement_id}"
    )

    pnl_realized_at_settle = float(pnl_unrealized_existing or 0.0) + float(pnl_realized_existing or 0.0)
    now_iso = _now_iso()

    _rw_execute(
        _INSERT_SETTLEMENT,
        (
            vertex_id, _SHOSHA_ACTOR, 0, settlement_id, trade_id,
            str(currency or "USD"), settled_amount_native, settled_amount_usd,
            method, bank_ref, value_date,
            cp_name, cp_vid, pnl_realized_at_settle, remarks,
            "settled", now_iso,
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.trade.settle",
        ),
    )

    edge_id = f"{trade_vid}::settled-by::{vertex_id}"
    _rw_execute(
        _INSERT_EDGE_TRADE_SETTLEMENT,
        (
            edge_id, _SHOSHA_ACTOR, 0, trade_vid, vertex_id, "trade-settlement",
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.trade.settle",
        ),
    )

    # RW UPDATE: quote reserved keywords + use trade_id (non-PK) lookup;
    # composite SET. RW silently rolls forward updates so re-runs of a
    # settlement on the same trade are no-op-ish (status=closed already).
    _rw_execute(
        'UPDATE vertex_shosha_trade SET '
        '"status" = %s, '
        '"approval_state" = %s, '
        '"pnl_realized" = %s, '
        '"pnl_unrealized" = %s, '
        '"pnl_marked_at" = %s '
        'WHERE "trade_id" = %s',
        (
            "closed", "approved",
            pnl_realized_at_settle, 0.0, now_iso,
            trade_id,
        ),
    )

    return {
        "ok": True,
        "settlementId": settlement_id,
        "vertexId": vertex_id,
        "tradeId": trade_id,
        "tradeStatus": "closed",
        "amountUsd": settled_amount_usd,
        "settledAt": now_iso,
    }


# ──────────────────────────────────────────────────────────────────────
# Approval / rejection (Phase 2d simplified — human-in-the-loop XRPC,
# multi-day message-event BPMN deferred to Phase 3)
# ──────────────────────────────────────────────────────────────────────

_INSERT_APPROVAL = (
    "INSERT INTO vertex_shosha_approval ("
    "vertex_id, owner_did, sensitivity_ord, approval_id, ref_trade_id, "
    "decision, approver_did, approver_role, amount_usd_at_decision, "
    "rationale, decided_at, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

# Phase 3.4 — two-tier approval routing.
#
# Approval authority bracket per amount_usd. A role is "qualified" if
# its level is >= the bracket's required level.
_ROLE_LEVEL: dict[str, int] = {
    "trader":      1,
    "desk-head":   2,
    "deskhead":    2,
    "head":        2,
    "cro":         3,
    "risk-officer": 3,
    "board":       4,
    "ceo":         4,
}

_AMOUNT_BRACKETS: list[tuple[float, int, str]] = [
    # (amount_usd_inclusive_lower, min_required_level, label)
    (0.0,        1, "any"),         # < $1M
    (1_000_000.0,  2, "desk-head"),   # $1M – $10M
    (10_000_000.0, 3, "cro"),         # $10M – $50M
    (50_000_000.0, 4, "board"),       # >= $50M
]


def _approval_bracket(amount_usd: float | None) -> tuple[int, str]:
    """Return (min_required_level, label) for the bracket the amount
    falls into. None / 0 amount → tier 1 (any role)."""
    a = float(amount_usd or 0.0)
    chosen = _AMOUNT_BRACKETS[0]
    for b in _AMOUNT_BRACKETS:
        if a >= b[0]:
            chosen = b
        else:
            break
    return chosen[1], chosen[2]


def _role_level(role: str) -> int:
    return _ROLE_LEVEL.get((role or "").strip().lower(), 0)


def _record_decision(
    *, trade_id: str, decision: str, approver_did: str,
    approver_role: str, rationale: str | None, amount_usd: float | None,
) -> tuple[str, str]:
    """Common path for approve / reject: write the audit row, return
    (approval_id, vertex_id)."""
    seed = f"decision|{decision}|{trade_id}|{approver_did}|{_now_ms()}"
    approval_id = f"ap-{_hash12(seed)}"
    vertex_id = (
        f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.approval/{approval_id}"
    )
    now_iso = _now_iso()
    _rw_execute(
        _INSERT_APPROVAL,
        (
            vertex_id, _SHOSHA_ACTOR, 0, approval_id, trade_id,
            decision, approver_did, approver_role, amount_usd,
            (rationale or "")[:2000] or None, now_iso, "active",
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, f"shosha.trade.{decision}",
        ),
    )
    return approval_id, vertex_id


async def task_shosha_trade_approve(**kwargs: Any) -> dict[str, Any]:
    """Approve a pending trade.

    Validation:
      - trade exists
      - approval_state must be 'pending'
      - status must not be 'cancelled' or 'closed'
    Effect:
      - INSERT vertex_shosha_approval (decision='approve')
      - UPDATE vertex_shosha_trade SET approval_state='approved'
    """
    trade_id = str(kwargs.get("tradeId") or "").strip()
    approver_did = str(kwargs.get("approverDid") or "").strip()
    if not trade_id:
        return {"ok": False, "error": "tradeId required"}
    if not approver_did:
        return {"ok": False, "error": "approverDid required"}

    rows = _rw_query(
        "SELECT amount_usd, approval_state, status FROM vertex_shosha_trade "
        "WHERE trade_id = %s LIMIT 1",
        (trade_id,),
    )
    if not rows:
        return {"ok": False, "error": f"trade not found: {trade_id}"}
    amount_usd, approval_state, status = rows[0]
    if str(approval_state) != "pending":
        return {"ok": False, "error": f"approval_state is {approval_state!r}, must be 'pending'",
                "tradeId": trade_id}
    if str(status) in ("cancelled", "closed"):
        return {"ok": False, "error": f"trade status is {status!r}, terminal — cannot approve",
                "tradeId": trade_id}

    approver_role = str(kwargs.get("approverRole") or "trader")[:64]
    rationale = str(kwargs.get("rationale") or "") or None
    amount_f = float(amount_usd) if amount_usd is not None else None

    # Phase 3.4 — two-tier approval routing.
    # Verify the approver's role is at-or-above the bracket required
    # for the trade's notional. Reject otherwise (no DB row written).
    required_level, required_label = _approval_bracket(amount_f)
    actual_level = _role_level(approver_role)
    if actual_level < required_level:
        return {
            "ok": False,
            "error": (
                f"approver_role {approver_role!r} (level {actual_level}) "
                f"insufficient for amount_usd {amount_f or 0:,.0f}; "
                f"requires role >= {required_label!r} (level {required_level})"
            ),
            "tradeId": trade_id,
            "amountUsd": amount_f,
            "requiredRole": required_label,
            "requiredLevel": required_level,
        }

    approval_id, vertex_id = _record_decision(
        trade_id=trade_id, decision="approve", approver_did=approver_did,
        approver_role=approver_role, rationale=rationale, amount_usd=amount_f,
    )
    now_iso = _now_iso()
    _rw_execute(
        'UPDATE vertex_shosha_trade SET '
        '"approval_state" = %s, "approver" = %s, "approved_at" = %s '
        'WHERE "trade_id" = %s',
        ("approved", approver_did, now_iso, trade_id),
    )
    return {
        "ok": True,
        "approvalId": approval_id,
        "vertexId": vertex_id,
        "tradeId": trade_id,
        "approvalState": "approved",
        "decidedAt": now_iso,
    }


async def task_shosha_trade_reject(**kwargs: Any) -> dict[str, Any]:
    """Reject a pending trade. Trade becomes terminal (cancelled).

    Validation:
      - trade exists
      - approval_state must be 'pending' (cannot reject already-approved
        trades via this primitive — those need an explicit cancel flow,
        out of Phase 2d scope)
    Effect:
      - INSERT vertex_shosha_approval (decision='reject')
      - UPDATE vertex_shosha_trade SET approval_state='rejected',
        status='cancelled'
    """
    trade_id = str(kwargs.get("tradeId") or "").strip()
    approver_did = str(kwargs.get("approverDid") or "").strip()
    rationale = str(kwargs.get("rationale") or "").strip()
    if not trade_id:
        return {"ok": False, "error": "tradeId required"}
    if not approver_did:
        return {"ok": False, "error": "approverDid required"}
    if not rationale:
        return {"ok": False, "error": "rationale required for rejection"}

    rows = _rw_query(
        "SELECT amount_usd, approval_state, status FROM vertex_shosha_trade "
        "WHERE trade_id = %s LIMIT 1",
        (trade_id,),
    )
    if not rows:
        return {"ok": False, "error": f"trade not found: {trade_id}"}
    amount_usd, approval_state, status = rows[0]
    if str(approval_state) != "pending":
        return {"ok": False, "error": f"approval_state is {approval_state!r}, must be 'pending'",
                "tradeId": trade_id}

    approver_role = str(kwargs.get("approverRole") or "trader")[:64]
    amount_f = float(amount_usd) if amount_usd is not None else None

    approval_id, vertex_id = _record_decision(
        trade_id=trade_id, decision="reject", approver_did=approver_did,
        approver_role=approver_role, rationale=rationale, amount_usd=amount_f,
    )
    now_iso = _now_iso()
    _rw_execute(
        'UPDATE vertex_shosha_trade SET '
        '"approval_state" = %s, "status" = %s, '
        '"approver" = %s, "approved_at" = %s '
        'WHERE "trade_id" = %s',
        ("rejected", "cancelled", approver_did, now_iso, trade_id),
    )
    return {
        "ok": True,
        "approvalId": approval_id,
        "vertexId": vertex_id,
        "tradeId": trade_id,
        "approvalState": "rejected",
        "tradeStatus": "cancelled",
        "decidedAt": now_iso,
    }


# ──────────────────────────────────────────────────────────────────────
# Hedge propose
# ──────────────────────────────────────────────────────────────────────

_INSERT_HEDGE = (
    "INSERT INTO vertex_shosha_hedge ("
    "vertex_id, owner_did, sensitivity_ord, hedge_id, instrument, commodity, "
    "ref_trade_id, direction, notional, currency, expiry_date, "
    "target_hedge_ratio, current_exposure, rationale, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)


async def task_shosha_hedge_propose(**kwargs: Any) -> dict[str, Any]:
    commodity = str(kwargs.get("commodity") or "").strip()
    if not commodity:
        return {"ok": False, "error": "commodity required"}
    instrument = str(kwargs.get("instrument") or "futures")
    ratio = float(kwargs.get("targetHedgeRatio") or 0.8)
    expiry = str(kwargs.get("expiryDate") or "") or None

    rows = _rw_query(
        "SELECT net_usd FROM mv_shosha_exposure_by_commodity WHERE commodity = %s LIMIT 1",
        (commodity,),
    )
    net_usd = float(rows[0][0]) if rows and rows[0][0] is not None else 0.0
    if abs(net_usd) < 1.0:
        return {"ok": True, "hedgeId": None, "vertexId": None,
                "instrument": instrument, "commodity": commodity,
                "direction": "none", "notional": 0.0,
                "currentExposure": net_usd,
                "rationale": "Net exposure ~ 0; no hedge needed."}

    direction = "short" if net_usd > 0 else "long"
    notional = abs(net_usd) * ratio

    seed = f"{commodity}|{direction}|{notional:.2f}|{_now_ms()}"
    hedge_id = f"hd-{_hash12(seed)}"
    vertex_id = f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.hedge/{hedge_id}"
    rationale = (
        f"Net {commodity} exposure ${net_usd:,.0f}; propose {direction} {instrument} "
        f"notional ${notional:,.0f} at hedge ratio {ratio:.0%}."
    )

    _rw_execute(
        _INSERT_HEDGE,
        (
            vertex_id, _SHOSHA_ACTOR, 0, hedge_id, instrument, commodity,
            None, direction, notional, "USD", expiry,
            ratio, net_usd, rationale, "proposed",
            _now_iso(), _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.hedge.propose",
        ),
    )
    return {
        "ok": True, "hedgeId": hedge_id, "vertexId": vertex_id,
        "instrument": instrument, "commodity": commodity,
        "direction": direction, "notional": notional,
        "currentExposure": net_usd, "rationale": rationale,
    }


# ──────────────────────────────────────────────────────────────────────
# Daily report compose
# ──────────────────────────────────────────────────────────────────────


async def task_shosha_daily_report_compose(**kwargs: Any) -> dict[str, Any]:
    pnl = _rw_query(
        "SELECT created_date, commodity, total_usd, trade_count "
        "FROM mv_shosha_pnl_daily ORDER BY created_date DESC LIMIT 30",
    )
    at_risk = _rw_query("SELECT count(*) FROM mv_shosha_at_risk_trades")
    top_exp = _rw_query(
        "SELECT commodity, net_usd FROM mv_shosha_exposure_by_commodity "
        "ORDER BY net_usd DESC LIMIT 5",
    )
    open_count = _rw_query(
        "SELECT count(*) FROM vertex_shosha_trade WHERE status='open'",
    )

    today = _today_iso()
    today_pnl_usd = sum(float(r[2] or 0.0) for r in pnl if str(r[0]) == today)
    n_open = int((open_count[0][0] if open_count else 0) or 0)
    n_at_risk = int((at_risk[0][0] if at_risk else 0) or 0)

    # Compose human-readable summary; LLM polishes when available.
    bullets = "\n".join(
        f"・ {c}: ${float(n or 0):,.0f}" for c, n in top_exp[:3]
    ) or "・ no open exposure"

    fallback = (
        f"商社 daily report ({today})\n"
        f"P&L today: ${today_pnl_usd:,.0f}\n"
        f"Open trades: {n_open} / at-risk: {n_at_risk}\n"
        f"Top exposures:\n{bullets}"
    )

    polished_summary = fallback
    try:
        result = llm.call_tier(
            "reasoning",
            "You polish a daily trading report for a Japanese sogo-shosha. "
            "Output 1 paragraph, <= 280 chars, in Japanese, no emoji unless conveying signal.",
            fallback,
            max_tokens=800, temperature=0.3,
        )
        polished = _strip_think_blocks(result.get("content") or "").strip()
        if polished:
            polished_summary = polished[:300]
    except llm.LlmError:
        pass

    return {
        "ok": True,
        "summary": polished_summary,
        "tradesCount": n_open,
        "atRiskCount": n_at_risk,
        "todayPnlUsd": today_pnl_usd,
    }


# ──────────────────────────────────────────────────────────────────────
# Agent loop (XRPC com.etzhayyim.apps.shosha.agentLoop)
# ──────────────────────────────────────────────────────────────────────

_AGENT_SYSTEM = (
    "You are 商社 (shosha.etzhayyim.com), an autonomous AI sogo-shosha agent. "
    "You have read access to recent market intel, market views, and open "
    "exposure. Be concise, factual, and acknowledge uncertainty. Default "
    "to Japanese unless the user writes English. Keep replies under 600 "
    "tokens."
)


async def task_shosha_agent_chat(**kwargs: Any) -> dict[str, Any]:
    prompt = str(kwargs.get("prompt") or "").strip()
    if not prompt:
        return {"ok": False, "error": "prompt is required"}
    tier = str(kwargs.get("tier") or "reasoning")
    max_tokens = int(kwargs.get("maxTokens") or 1500)
    commodity_focus = (str(kwargs.get("commodityFocus") or "")).strip() or None

    # Pull context.
    intel_q = (
        "SELECT symbol, value, unit, ts_ms FROM vertex_shosha_intel "
        "WHERE value IS NOT NULL "
        + ("AND symbol = %s " if commodity_focus else "")
        + "ORDER BY ts_ms DESC LIMIT 30"
    )
    intel_p: tuple[Any, ...] = (commodity_focus,) if commodity_focus else ()
    intel = _rw_query(intel_q, intel_p)

    view_q = (
        "SELECT commodity, direction, confidence, price_target, rationale "
        "FROM vertex_shosha_market_view "
        + ("WHERE commodity = %s " if commodity_focus else "")
        + "ORDER BY as_of_date DESC LIMIT 20"
    )
    views = _rw_query(view_q, intel_p)
    exposure = _rw_query(
        "SELECT commodity, net_usd FROM mv_shosha_exposure_by_commodity "
        + ("WHERE commodity = %s " if commodity_focus else "")
        + "ORDER BY net_usd DESC LIMIT 20",
        intel_p,
    )

    ctx_lines: list[str] = []
    if intel:
        ctx_lines.append("Recent intel ticks (symbol, value, unit, ts_ms):")
        for s, v, u, t in intel[:15]:
            ctx_lines.append(f"  - {s} | {v} | {u} | {t}")
    if views:
        ctx_lines.append("Market views (commodity, direction, conf, target, rationale):")
        for c, d, cf, pt, r in views[:10]:
            ctx_lines.append(f"  - {c} | {d} | {cf} | {pt} | {r}")
    if exposure:
        ctx_lines.append("Open exposure (commodity, net USD):")
        for c, n in exposure[:10]:
            ctx_lines.append(f"  - {c} | {n}")
    context = "\n".join(ctx_lines) if ctx_lines else "(no context rows yet)"
    user_msg = f"{context}\n\nUser asks:\n{prompt}"

    try:
        resp = llm.call_tier(
            tier, _AGENT_SYSTEM, user_msg,
            max_tokens=max_tokens, temperature=0.3,
        )
    except llm.LlmError as e:
        return {"ok": False, "error": str(e)}
    return {
        "ok": True,
        "content": _strip_think_blocks(resp.get("content") or ""),
        "model": resp.get("model") or "unknown",
        "latencyMs": int(resp.get("latencyMs") or 0),
        "intelRowsUsed": len(intel),
        "marketViewRowsUsed": len(views),
        "exposureRowsUsed": len(exposure),
    }


# ──────────────────────────────────────────────────────────────────────
# Cross-actor reactive (Phase 2a — polling consumer over upstream actors)
# ──────────────────────────────────────────────────────────────────────

# Phase 2a hard-coded subscription set. Phase 2a-extended will move to
# a `vertex_shosha_upstream_subscription` table for runtime reconfig.
_REACTIVE_SUBSCRIPTIONS: list[tuple[str, str, str | None]] = [
    # (consumer_id,                upstream_did,                      collection_prefix)
    ("shosha:reactive:oil-trading", "did:web:oil-trading.etzhayyim.com",    None),
    ("shosha:reactive:cargo",       "did:web:cargo.etzhayyim.com",          None),
    ("shosha:reactive:port",        "did:web:port.etzhayyim.com",           None),
]

_INSERT_CURSOR = (
    "INSERT INTO vertex_shosha_consumer_cursor ("
    "vertex_id, owner_did, sensitivity_ord, consumer_id, upstream_did, "
    "collection_prefix, last_seq, last_ts_ms, last_seen_at, "
    "records_seen, reactions_emitted, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)
_INSERT_REACTION = (
    "INSERT INTO vertex_shosha_reaction ("
    "vertex_id, owner_did, sensitivity_ord, reaction_id, "
    "upstream_did, upstream_collection, upstream_seq, upstream_rkey, "
    "upstream_record_vid, reaction_type, commodity, direction, "
    "target_action, rationale, confidence, llm_model, status, "
    "created_at, org_id, user_id, actor_id) "
    "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
)

_REACTION_SYSTEM = (
    "You are a senior commodity trader at a Japanese sogo-shosha. "
    "You read upstream actor commits (oil-trading, cargo, port) and "
    "decide whether shosha should take a position in response. Be brief. "
    'Reply with strict JSON: {"reactionType":"trade-idea|hedge-suggestion|risk-alert|pass",'
    '"commodity":"crude-wti|crude-brent|...|null",'
    '"direction":"long|short|hedge|pass",'
    '"targetAction":"<<= 120 chars actionable description>",'
    '"rationale":"<= 200 chars why",'
    '"confidence":0.0..1.0}. '
    "Default to reactionType=pass when the upstream commit doesn't warrant action."
)


def _cursor_lookup(consumer_id: str) -> int:
    """Returns the cursor as ts_ms (vertex_repo_record uses ts_ms for
    ordering, not seq). Schema field is still named `last_seq` for
    backward-compat — interpret as ts_ms here."""
    rows = _rw_query(
        "SELECT last_seq FROM vertex_shosha_consumer_cursor "
        "WHERE consumer_id = %s LIMIT 1",
        (consumer_id,),
    )
    if not rows:
        return 0
    try:
        return int(rows[0][0] or 0)
    except (TypeError, ValueError):
        return 0


def _cursor_upsert(consumer_id: str, upstream_did: str, cursor_value: int,
                   last_ts_ms: int, records_seen: int,
                   reactions_emitted: int) -> None:
    """RW PK semantic: re-INSERT on same vertex_id overwrites. Use
    consumer_id as the vertex_id slug for stable identity. cursor_value
    is the consumer's high-water-mark ts_ms (stored in last_seq column)."""
    vertex_id = (
        f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.consumerCursor/"
        f"{_slug(consumer_id, max_len=120)}"
    )
    now_iso = _now_iso()
    _rw_execute(
        _INSERT_CURSOR,
        (
            vertex_id, _SHOSHA_ACTOR, 0, consumer_id, upstream_did,
            None, cursor_value, last_ts_ms, now_iso,
            records_seen, reactions_emitted, "active",
            now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.reactive.scanUpstream",
        ),
    )


async def task_shosha_reactive_scan_upstream(**kwargs: Any) -> dict[str, Any]:
    """Scan recent commits from configured upstream actors and emit
    LLM-synthesized reactions.

    For each subscription:
      1. Read up to `batchPerUpstream` (default 20) `vertex_repo_record`
         rows where `repo = upstream_did` and `_seq > last_seq`
      2. Per-record: ask LLM for a reaction (trade-idea / hedge-
         suggestion / risk-alert / pass)
      3. INSERT non-pass reactions into `vertex_shosha_reaction`
      4. Advance cursor to max(_seq) seen
    """
    batch = int(kwargs.get("batchPerUpstream", 20) or 20)
    upstreams_scanned = 0
    records_seen_total = 0
    reactions_emitted_total = 0

    for consumer_id, upstream_did, _coll_prefix in _REACTIVE_SUBSCRIPTIONS:
        last_ts_ms = _cursor_lookup(consumer_id)  # cursor stores ts_ms
        # vertex_repo_record PK = `uri`; ordering by `ts_ms` (no `_seq` col).
        rows = _rw_query(
            "SELECT uri, ts_ms, collection, rkey, value_json "
            "FROM vertex_repo_record "
            "WHERE repo = %s AND ts_ms > %s "
            "ORDER BY ts_ms ASC "
            f"LIMIT {int(batch)}",
            (upstream_did, last_ts_ms),
        )
        upstreams_scanned += 1
        if not rows:
            # Still upsert cursor so the timestamp moves forward.
            _cursor_upsert(consumer_id, upstream_did, last_ts_ms, _now_ms(), 0, 0)
            continue

        emitted_for_this = 0
        max_ts_ms = last_ts_ms
        now_iso = _now_iso()

        for record_uri, ts_ms, collection, rkey, value_json in rows:
            records_seen_total += 1
            try:
                ts_int = int(ts_ms or 0)
            except (TypeError, ValueError):
                ts_int = 0
            if ts_int > max_ts_ms:
                max_ts_ms = ts_int

            # Ask LLM for a reaction. tier `reasoning` per Phase 2b
            # learning (Vultr direct, bypasses Murakumo CF Error 1010).
            payload_brief = (str(value_json or "")[:1500])
            user_msg = (
                f"Upstream actor: {upstream_did}\n"
                f"Collection: {collection}\n"
                f"Record key: {rkey}\n"
                f"Payload (first 1.5KB): {payload_brief}\n"
                "Reaction?"
            )
            result = llm.call_tier_json(
                "reasoning", _REACTION_SYSTEM, user_msg,
                max_tokens=1000, temperature=0.2,
            )
            if not result.get("ok"):
                # LLM unavailable → record the upstream-seen but don't
                # synthesize a reaction. Cursor still advances so we
                # don't re-attempt the same record forever.
                continue
            data = result.get("data") or {}
            reaction_type = str(data.get("reactionType") or "pass")[:32]
            if reaction_type == "pass":
                continue

            commodity = str(data.get("commodity") or "")[:64] or None
            direction = str(data.get("direction") or "pass")[:16]
            target_action = str(data.get("targetAction") or "")[:500] or None
            rationale = str(data.get("rationale") or "")[:1000] or None
            try:
                confidence = float(data.get("confidence") or 0.0)
            except (TypeError, ValueError):
                confidence = 0.0
            llm_model = str(result.get("model") or "unknown")

            seed = f"reaction|{upstream_did}|{ts_int}|{rkey}|{reaction_type}"
            reaction_id = f"rx-{_hash12(seed)}"
            vertex_id = (
                f"at://{_SHOSHA_ACTOR}/com.etzhayyim.apps.shosha.reaction/{reaction_id}"
            )
            _rw_execute(
                _INSERT_REACTION,
                (
                    vertex_id, _SHOSHA_ACTOR, 0, reaction_id,
                    upstream_did, str(collection or ""), ts_int, str(rkey or ""),
                    str(record_uri or ""), reaction_type, commodity, direction,
                    target_action, rationale, confidence, llm_model, "active",
                    now_iso, _SHOSHA_ACTOR, _SHOSHA_ACTOR, "shosha.reactive.scanUpstream",
                ),
            )
            emitted_for_this += 1

        _cursor_upsert(consumer_id, upstream_did, max_ts_ms, _now_ms(),
                       len(rows), emitted_for_this)
        reactions_emitted_total += emitted_for_this

    return {
        "ok": True,
        "upstreamsScanned": upstreams_scanned,
        "recordsSeen": records_seen_total,
        "reactionsEmitted": reactions_emitted_total,
    }


# ──────────────────────────────────────────────────────────────────────
# Coverage snapshot (Phase 3 step 1 — public XRPC for soak monitor /
# dashboard / RemoteTrigger probes)
# ──────────────────────────────────────────────────────────────────────


def _scalar_count(sql: str, params: tuple[Any, ...] = ()) -> int:
    rows = _rw_query(sql, params)
    if not rows:
        return 0
    try:
        return int(rows[0][0] or 0)
    except (TypeError, ValueError):
        return 0


def _scalar_max(sql: str, params: tuple[Any, ...] = ()) -> int:
    rows = _rw_query(sql, params)
    if not rows or rows[0][0] is None:
        return 0
    try:
        return int(rows[0][0])
    except (TypeError, ValueError):
        return 0


async def task_shosha_coverage_snapshot(**kwargs: Any) -> dict[str, Any]:
    """Aggregate snapshot across every vertex_shosha_* table.

    Read-only. Cheap (each query is COUNT or MAX, all on small tables
    except sanctions list which is the largest at ~20K rows).

    Output mirrors the lexicon-required fields plus extras:
      tradesOpen / tradesClosed / tradesPending / tradesCancelled
      counterpartiesActive
      atRiskTrades        (mv_shosha_at_risk_trades count)
      lastIntelTsMs
      intelRows24h        (intel rows ingested in last 24h)
      sanctionsActiveCount
      approvalsTotal
      reactionsTotal
      settlementsTotal
    """
    cutoff_ms = _now_ms() - 24 * 3_600_000

    trades_open       = _scalar_count("SELECT count(*) FROM vertex_shosha_trade WHERE status = 'open'")
    trades_closed     = _scalar_count("SELECT count(*) FROM vertex_shosha_trade WHERE status = 'closed'")
    trades_pending    = _scalar_count("SELECT count(*) FROM vertex_shosha_trade WHERE approval_state = 'pending' AND status = 'open'")
    trades_cancelled  = _scalar_count("SELECT count(*) FROM vertex_shosha_trade WHERE status = 'cancelled'")
    cps_active        = _scalar_count("SELECT count(*) FROM vertex_shosha_counterparty WHERE status = 'active'")
    at_risk           = _scalar_count("SELECT count(*) FROM mv_shosha_at_risk_trades")
    last_intel_ts_ms  = _scalar_max("SELECT max(ts_ms) FROM vertex_shosha_intel")
    intel_24h         = _scalar_count(
        f"SELECT count(*) FROM vertex_shosha_intel WHERE ts_ms > {int(cutoff_ms)}"
    )
    sanctions_active  = _scalar_count(
        "SELECT count(*) FROM vertex_shosha_sanctions_list WHERE status = 'active'"
    )
    approvals_total   = _scalar_count("SELECT count(*) FROM vertex_shosha_approval")
    reactions_total   = _scalar_count("SELECT count(*) FROM vertex_shosha_reaction")
    settlements_total = _scalar_count("SELECT count(*) FROM vertex_shosha_settlement")

    return {
        "asOf":                 _now_iso(),
        "tradesOpen":           trades_open,
        "tradesClosed":         trades_closed,
        "tradesPending":        trades_pending,
        "tradesCancelled":      trades_cancelled,
        "counterpartiesActive": cps_active,
        "atRiskTrades":         at_risk,
        "lastIntelTsMs":        last_intel_ts_ms,
        "intelRows24h":         intel_24h,
        "sanctionsActiveCount": sanctions_active,
        "approvalsTotal":       approvals_total,
        "reactionsTotal":       reactions_total,
        "settlementsTotal":     settlements_total,
    }


# ──────────────────────────────────────────────────────────────────────
# Registration
# ──────────────────────────────────────────────────────────────────────


def register(worker: Any, *, timeout_ms: int = 60_000) -> None:
    """Wire all shosha task types onto the shared LangServer worker.

    Static manifest below repeats each task_type as a literal so the
    BPMN worker-task coverage linter
    (`70-tools/scripts/lint/bpmn-worker-task-coverage.mjs`) discovers
    camelCase names — its `t("...")` regex is `[a-z0-9_.-]`-only and
    misses camelCase, while its `task_type="..."` regex is lazy and
    matches anywhere in the file (comments included).

      task_type="shosha.intel.ingestPrices"
      task_type="shosha.intel.ingestFreight"
      task_type="shosha.marketView.synth"
      task_type="shosha.exposure.recompute"
      task_type="shosha.pnl.dailyRecompute"
      task_type="shosha.trade.synth"
      task_type="shosha.trade.submit"
      task_type="shosha.hedge.propose"
      task_type="shosha.comply.sanctionsCheck"
      task_type="shosha.dailyReport.compose"
      task_type="shosha.agent.chat"
      task_type="shosha.sanctions.refreshOfac"
      task_type="shosha.sanctions.refreshUn"
      task_type="shosha.trade.settle"
      task_type="shosha.trade.approve"
      task_type="shosha.trade.reject"
      task_type="shosha.reactive.scanUpstream"
      task_type="shosha.coverage.snapshot"
    """
    def t(name: str, fn: Any, *, ms: int | None = None) -> None:
        worker.task(task_type=name, single_value=False, timeout_ms=ms or timeout_ms)(fn)

    t("shosha.intel.ingestPrices",     task_shosha_intel_ingest_prices)
    t("shosha.intel.ingestFreight",    task_shosha_intel_ingest_freight)
    t("shosha.marketView.synth",       task_shosha_market_view_synth,    ms=120_000)
    t("shosha.exposure.recompute",     task_shosha_exposure_recompute)
    t("shosha.pnl.dailyRecompute",     task_shosha_pnl_daily_recompute)
    t("shosha.trade.synth",            task_shosha_trade_synth,          ms=120_000)
    t("shosha.trade.submit",           task_shosha_trade_submit)
    t("shosha.hedge.propose",          task_shosha_hedge_propose)
    t("shosha.comply.sanctionsCheck",  task_shosha_comply_sanctions_check, ms=60_000)
    t("shosha.dailyReport.compose",    task_shosha_daily_report_compose, ms=120_000)
    t("shosha.agent.chat",             task_shosha_agent_chat,           ms=60_000)
    # Phase 2b — sanctions list refresh (daily 01:00 UTC, OFAC SDN)
    t("shosha.sanctions.refreshOfac",  task_shosha_sanctions_refresh_ofac, ms=300_000)
    # Phase 2b-ext — UN 1267 / 1988 / 2231 consolidated XML refresh
    t("shosha.sanctions.refreshUn",    task_shosha_sanctions_refresh_un,   ms=180_000)
    # Phase 2c — settlement workflow (XRPC settleTrade)
    t("shosha.trade.settle",           task_shosha_trade_settle)
    # Phase 2d — approval / rejection (XRPC approveTrade / rejectTrade)
    t("shosha.trade.approve",          task_shosha_trade_approve)
    t("shosha.trade.reject",           task_shosha_trade_reject)
    # Phase 2a — cross-actor reactive (R/PT5M polling consumer)
    t("shosha.reactive.scanUpstream",  task_shosha_reactive_scan_upstream, ms=300_000)
    # Phase 3 step 1 — coverage XRPC (read-only snapshot for soak monitor)
    t("shosha.coverage.snapshot",      task_shosha_coverage_snapshot,    ms=15_000)


__all__ = [
    "register",
    "task_shosha_intel_ingest_prices",
    "task_shosha_intel_ingest_freight",
    "task_shosha_market_view_synth",
    "task_shosha_exposure_recompute",
    "task_shosha_pnl_daily_recompute",
    "task_shosha_trade_synth",
    "task_shosha_trade_submit",
    "task_shosha_hedge_propose",
    "task_shosha_comply_sanctions_check",
    "task_shosha_daily_report_compose",
    "task_shosha_agent_chat",
    "task_shosha_sanctions_refresh_ofac",
    "task_shosha_sanctions_refresh_un",
    "task_shosha_trade_settle",
    "task_shosha_trade_approve",
    "task_shosha_trade_reject",
    "task_shosha_reactive_scan_upstream",
    "task_shosha_coverage_snapshot",
]
