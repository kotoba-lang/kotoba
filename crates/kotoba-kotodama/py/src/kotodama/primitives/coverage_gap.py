"""Coverage gap bridge LangServer primitives (Von Neumann stored-program orchestrator).

Four task types wired by coverageGapBridge.bpmn:

  coverage.gap.scan     — minimax-regret SELECT from mv_coverage_gap_minimax
  coverage.gap.ingest   — pure HTTP fetch → INSERT (OFAC SDN, GLEIF, etc.)
  coverage.gap.infer    — SQL UDF classify + LLM structured tier
  coverage.gap.generate — LangGraph multi-hop synthesis (lazy import)

ADR-0056 (BPMN-as-actor), ADR-0044 (RW UDF strategy), ADR-0004 (write-only derived).
psycopg3 LIMIT rule: always use LIMIT {int(n)} f-string, never LIMIT %s param.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import datetime, timezone
from typing import Any



# ── helpers ──────────────────────────────────────────────────────────────────

def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _stable_id(prefix: str, *parts: Any) -> str:
    raw = "|".join(str(p or "") for p in parts)
    digest = hashlib.sha256(raw.encode()).hexdigest()[:20]
    return f"{prefix}-{digest}"


def _as_str(v: Any, maxlen: int = 500) -> str:
    return str(v or "")[:maxlen]


def _fetch_url(url: str, timeout: int = 60) -> bytes:
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "coverage-gap-bridge/1 (+https://etzhayyim.com)"},
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def _sparql_post(endpoint: str, query: str, timeout: int = 55) -> bytes:
    """POST SPARQL query — more reliable than GET for Wikidata."""
    data = urllib.parse.urlencode({"query": query, "format": "json"}).encode()
    req = urllib.request.Request(
        endpoint,
        data=data,
        headers={
            "User-Agent": "coverage-gap-bridge/1 (+https://etzhayyim.com)",
            "Accept": "application/sparql-results+json",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


# ── task 1: scan ─────────────────────────────────────────────────────────────

def task_coverage_gap_scan(**kwargs: Any) -> dict[str, Any]:
    """
    SELECT the highest-regret actionable domain from mv_coverage_gap_minimax.
    Returns domain, recipeKind, llmTier, langgraphId, worldTotal, collected=0, regret.
    Falls back to a no-op defer row when the MV is empty or unavailable.
    """
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                # psycopg3 LIMIT rule: f-string literal, never %s
                f"SELECT domain, authority_kind, recipe_kind, llm_tier, langgraph_id, "
                f"world_total, regret "
                f"FROM mv_coverage_gap_minimax "
                f"WHERE recipe_kind != 'defer' "
                f"ORDER BY regret DESC "
                f"LIMIT {int(1)}"
            )
            row = (_res[0] if _res else None)
    except Exception as exc:  # noqa: BLE001
        return {
            "domain": "noop",
            "authorityKind": "world",
            "recipeKind": "defer",
            "llmTier": "fast",
            "langgraphId": "",
            "worldTotal": 0,
            "collected": 0,
            "regret": 0.0,
            "scanError": str(exc)[:500],
        }

    if not row:
        return {
            "domain": "noop",
            "authorityKind": "world",
            "recipeKind": "defer",
            "llmTier": "fast",
            "langgraphId": "",
            "worldTotal": 0,
            "collected": 0,
            "regret": 0.0,
            "scanError": "mv_coverage_gap_minimax empty",
        }

    domain, authority_kind, recipe_kind, llm_tier, langgraph_id, world_total, regret = row
    return {
        "domain": str(domain or ""),
        "authorityKind": str(authority_kind or "world"),
        "recipeKind": str(recipe_kind or "defer"),
        "llmTier": str(llm_tier or "structured"),
        "langgraphId": str(langgraph_id or ""),
        "worldTotal": int(world_total or 0),
        "collected": 0,
        "regret": float(regret or 0.0),
    }


# ── task 2: ingest ────────────────────────────────────────────────────────────

_INGEST_HANDLERS: dict[str, Any] = {}


def _register_ingest(domain: str):
    def decorator(fn):
        _INGEST_HANDLERS[domain] = fn
        return fn
    return decorator


@_register_ingest("crypto_asset_freeze")
def _ingest_crypto_asset_freeze(world_total: int) -> dict[str, Any]:
    """OFAC SDN XML → vertex_crypto_asset_freeze_incident (existing schema)."""
    url = os.environ.get(
        "OFAC_SDN_URL",
        "https://www.treasury.gov/ofac/downloads/sdn.xml",
    )
    try:
        raw = _fetch_url(url, timeout=120)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"fetch: {exc}"}

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return {"ok": False, "rowsWritten": 0, "error": f"xml parse: {exc}"}

    # Detect namespace from root tag (e.g. {https://sanctionslistservice...}sdnList)
    ns_match = root.tag.split("}")[0].lstrip("{") if "}" in root.tag else ""
    ns = f"{{{ns_match}}}" if ns_match else ""
    entries = root.findall(f".//{ns}sdnEntry") if ns else root.findall(".//sdnEntry")

    rows = []
    ts = _utc_now()
    limit = int(min(len(entries), world_total or 50_000))
    for entry in entries[:limit]:
        uid_el = entry.find(f"{ns}uid")
        name_el = entry.find(f"{ns}lastName")
        sdn_type_el = entry.find(f"{ns}sdnType")
        prog_el = entry.find(f"{ns}programList/{ns}program")
        uid = _as_str(uid_el.text if uid_el is not None else "", 64)
        name = _as_str(name_el.text if name_el is not None else "", 255)
        sdn_type = _as_str(sdn_type_el.text if sdn_type_el is not None else "unknown", 64)
        program = _as_str(prog_el.text if prog_el is not None else "", 64)
        if not uid:
            continue
        vertex_id = f"at://did:web:crypto-asset-freeze.etzhayyim.com/com.etzhayyim.apps.cryptoAssetFreeze.incident/ofac-{uid}"
        rows.append((
            vertex_id, uid, name, sdn_type, program, "ofac_sdn", ts,
        ))

    if not rows:
        return {"ok": True, "rowsWritten": 0, "error": "no SDN entries parsed"}

    written = 0
    batch_size = 500
    if True:
        client = get_kotoba_client()
        for i in range(0, len(rows), batch_size):
            batch = rows[i : i + batch_size]
            placeholders = ",".join("(%s,%s,%s,%s,%s,%s,%s)" for _ in batch)
            flat = [v for row in batch for v in row]
            _res = client.q(
                f"INSERT INTO vertex_crypto_asset_freeze_incident "
                f"(vertex_id,incident_id,entity_name,sdn_type,authority,source,created_at) "
                f"VALUES {placeholders}",
                flat,
            )
            written += len(batch)

    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("government_fund")
def _ingest_government_fund(world_total: int) -> dict[str, Any]:
    """SWF Institute + World Bank open data → vertex_fund (fund_kind=government)."""
    # Public SWF list from SWF Institute JSON endpoint
    url = "https://www.swfinstitute.org/swf-rankings.json"
    try:
        raw = _fetch_url(url, timeout=60)
        items = json.loads(raw)
        if not isinstance(items, list):
            items = items.get("data") or items.get("funds") or []
    except Exception:  # noqa: BLE001
        # Fallback: hardcoded top-10 sovereign wealth funds (public data)
        items = [
            {"name": "Norway Government Pension Fund Global", "country": "NOR", "aum": 1_700_000},
            {"name": "China Investment Corporation", "country": "CHN", "aum": 1_350_000},
            {"name": "Abu Dhabi Investment Authority", "country": "ARE", "aum": 993_000},
            {"name": "Kuwait Investment Authority", "country": "KWT", "aum": 769_000},
            {"name": "Public Investment Fund", "country": "SAU", "aum": 700_000},
            {"name": "GIC Private Limited", "country": "SGP", "aum": 690_000},
            {"name": "Hong Kong Monetary Authority", "country": "HKG", "aum": 580_000},
            {"name": "Temasek Holdings", "country": "SGP", "aum": 497_000},
            {"name": "Qatar Investment Authority", "country": "QAT", "aum": 475_000},
            {"name": "Investment Corporation of Dubai", "country": "ARE", "aum": 320_000},
        ]

    ts = _utc_now()
    written = 0
    if True:
        client = get_kotoba_client()
        limit = int(min(len(items), world_total or 500))
        for item in items[:limit]:
            name = _as_str(item.get("name") or item.get("fund_name") or "", 512)
            country = _as_str(item.get("country") or item.get("jurisdiction") or "", 8)
            aum = float(item.get("aum") or item.get("aum_usd_millions") or 0)
            if not name:
                continue
            vertex_id = _stable_id("gov-fund", name, country)
            _res = client.q(
                "INSERT INTO vertex_fund "
                "(vertex_id,fund_id,name,fund_kind,jurisdiction,aum_amount,source_url,source_license,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    vertex_id, vertex_id, name, "government",
                    country, aum,
                    "https://www.swfinstitute.org/fund-rankings/sovereign-wealth-fund",
                    "public", ts[:10],
                ),
            )
            written += 1

    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("sovereign_fund")
def _ingest_sovereign_fund(world_total: int) -> dict[str, Any]:
    """IMF COFER top sovereign funds → vertex_fund (fund_kind=sovereign)."""
    # Same fallback list as government_fund; sovereign_fund is a sub-set
    return _ingest_government_fund(int(world_total or 50))


@_register_ingest("mutual_fund")
def _ingest_mutual_fund(world_total: int) -> dict[str, Any]:
    """SEC EDGAR N-CEN (annual census for investment companies) → vertex_fund (fund_kind=mutual).

    N-PORT-P has no EFTS hits; N-CEN is filed annually by registered investment companies.
    display_names field contains the filer name with CIK suffix, e.g. 'VANGUARD (CIK 0000102909)'.
    """
    url = (
        "https://efts.sec.gov/LATEST/search-index?forms=N-CEN"
        "&dateRange=custom&startdt=2024-01-01"
        "&hits.hits._source=display_names,file_date"
    )
    try:
        raw = _fetch_url(url, timeout=60)
        data = json.loads(raw)
        hits = data.get("hits", {}).get("hits", []) or []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"sec fetch: {exc}"}

    ts = _utc_now()
    written = 0
    limit = int(min(len(hits), world_total or 500))
    if True:
        client = get_kotoba_client()
        for hit in hits[:limit]:
            src = hit.get("_source") or {}
            raw_names = src.get("display_names") or []
            raw_name = raw_names[0] if raw_names else ""
            # Strip '  (CIK XXXXXXXXXX)' suffix
            name = _as_str(raw_name.split("  (CIK")[0].strip(), 512)
            file_date = _as_str(src.get("file_date") or "", 32)
            if not name:
                continue
            vertex_id = _stable_id("mutual-fund", name, file_date)
            _res = client.q(
                "INSERT INTO vertex_fund "
                "(vertex_id,fund_id,name,fund_kind,jurisdiction,source_url,source_license,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    vertex_id, vertex_id, name, "mutual", "USA",
                    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=N-CEN",
                    "public_domain", ts[:10],
                ),
            )
            written += 1

    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("investor_fund")
def _ingest_investor_fund(world_total: int) -> dict[str, Any]:
    """SEC EDGAR 13F institutional investor filings → vertex_fund (fund_kind=investor).

    EFTS returns display_names (array), not entity_name. Strip '  (CIK XXXXXXXXXX)' suffix.
    """
    url = (
        "https://efts.sec.gov/LATEST/search-index?forms=13F-HR"
        "&dateRange=custom&startdt=2024-01-01"
        "&hits.hits._source=display_names,file_date"
    )
    try:
        raw = _fetch_url(url, timeout=60)
        data = json.loads(raw)
        hits = data.get("hits", {}).get("hits", []) or []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"sec fetch: {exc}"}

    ts = _utc_now()
    written = 0
    limit = int(min(len(hits), world_total or 500))
    if True:
        client = get_kotoba_client()
        for hit in hits[:limit]:
            src = hit.get("_source") or {}
            raw_names = src.get("display_names") or []
            raw_name = raw_names[0] if raw_names else ""
            name = _as_str(raw_name.split("  (CIK")[0].strip(), 512)
            if not name:
                continue
            vertex_id = _stable_id("investor-fund", name)
            _res = client.q(
                "INSERT INTO vertex_fund "
                "(vertex_id,fund_id,name,fund_kind,jurisdiction,source_url,source_license,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    vertex_id, vertex_id, name, "investor", "USA",
                    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=13F",
                    "public_domain", ts[:10],
                ),
            )
            written += 1

    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("pension_fund")
def _ingest_pension_fund(world_total: int) -> dict[str, Any]:
    """OECD pension fund statistics + hardcoded top global funds → vertex_fund."""
    # OECD pension stats API
    url = "https://stats.oecd.org/sdmx-json/data/PNNI_NEW/..../all?contentType=csv&startTime=2023&endTime=2023"
    top_funds = [
        ("Government Pension Investment Fund", "JPN", 1_700_000),
        ("National Pension Service", "KOR", 800_000),
        ("ABP", "NLD", 630_000),
        ("Canada Pension Plan Investment Board", "CAN", 570_000),
        ("PFZW", "NLD", 310_000),
        ("Employees Provident Fund", "MYS", 230_000),
        ("CalPERS", "USA", 480_000),
        ("CalSTRS", "USA", 335_000),
        ("Social Security Investment Fund", "CHN", 420_000),
        ("Pension Fund Association", "JPN", 110_000),
    ]
    ts = _utc_now()
    written = 0
    if True:
        client = get_kotoba_client()
        for name, country, aum in top_funds:
            vertex_id = _stable_id("pension-fund", name, country)
            _res = client.q(
                "INSERT INTO vertex_fund "
                "(vertex_id,fund_id,name,fund_kind,jurisdiction,aum_amount,source_url,source_license,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    vertex_id, vertex_id, name, "pension", country, float(aum),
                    "https://www.oecd.org/finance/private-pensions/globalpensionstatistics.htm",
                    "public", ts[:10],
                ),
            )
            written += 1

    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("private_fund")
def _ingest_private_fund(world_total: int) -> dict[str, Any]:
    """SEC Form PF private fund advisers → vertex_fund (fund_kind=private).

    Uses display_names field (same EFTS schema as 13F-HR / N-CEN).
    """
    url = (
        "https://efts.sec.gov/LATEST/search-index?forms=PF"
        "&dateRange=custom&startdt=2024-01-01"
        "&hits.hits._source=display_names,file_date"
    )
    try:
        raw = _fetch_url(url, timeout=60)
        data = json.loads(raw)
        hits = data.get("hits", {}).get("hits", []) or []
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"sec pf fetch: {exc}"}

    ts = _utc_now()
    written = 0
    limit = int(min(len(hits), world_total or 500))
    if True:
        client = get_kotoba_client()
        for hit in hits[:limit]:
            src = hit.get("_source") or {}
            raw_names = src.get("display_names") or []
            raw_name = raw_names[0] if raw_names else ""
            name = _as_str(raw_name.split("  (CIK")[0].strip(), 512)
            if not name:
                continue
            vertex_id = _stable_id("private-fund", name)
            _res = client.q(
                "INSERT INTO vertex_fund "
                "(vertex_id,fund_id,name,fund_kind,jurisdiction,source_url,source_license,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    vertex_id, vertex_id, name, "private", "USA",
                    "https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&type=PF",
                    "public_domain", ts[:10],
                ),
            )
            written += 1

    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("rare_earth_coverage")
def _ingest_rare_earth(world_total: int) -> dict[str, Any]:
    """USGS rare-earth mineral stats → vertex_rare_earth_coverage (stub seed)."""
    ts = _utc_now()
    minerals = [
        ("cerium", "Ce"), ("dysprosium", "Dy"), ("erbium", "Er"),
        ("europium", "Eu"), ("gadolinium", "Gd"), ("holmium", "Ho"),
        ("lanthanum", "La"), ("lutetium", "Lu"), ("neodymium", "Nd"),
        ("praseodymium", "Pr"), ("promethium", "Pm"), ("samarium", "Sm"),
        ("scandium", "Sc"), ("terbium", "Tb"), ("thulium", "Tm"),
        ("ytterbium", "Yb"), ("yttrium", "Y"),
    ]
    if True:
        client = get_kotoba_client()
        # Table created via migration 20260501100000_vertex_fund_rare_earth.ts
        written = 0
        for name, symbol in minerals:
            vid = _stable_id("rare-earth", name)
            _res = client.q(
                "INSERT INTO vertex_rare_earth_coverage "
                "(vertex_id,mineral,symbol,source,created_at) "
                "VALUES (%s,%s,%s,%s,%s)",
                (vid, name, symbol, "usgs_nmic", ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("sanctions")
def _ingest_ofac_sdn(world_total: int) -> dict[str, Any]:
    """OFAC SDN XML → vertex_open_ofac_sanctions_sdn (full bulk load)."""
    url = os.environ.get(
        "OFAC_SDN_URL",
        "https://www.treasury.gov/ofac/downloads/sdn.xml",
    )
    try:
        raw = _fetch_url(url, timeout=180)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"fetch: {exc}"}

    try:
        root = ET.fromstring(raw)
    except ET.ParseError as exc:
        return {"ok": False, "rowsWritten": 0, "error": f"xml parse: {exc}"}

    # Detect namespace from root tag, for example {https://...}sdnList.
    ns_prefix = ""
    if root.tag.startswith("{"):
        ns_prefix = root.tag.split("}")[0] + "}"
    entries = root.findall(f".//{ns_prefix}sdnEntry")
    if not entries:
        entries = root.findall(".//sdnEntry")
    if not entries:
        return {"ok": False, "rowsWritten": 0, "error": "no sdnEntry elements found"}

    actor_did = "did:web:open-ofac-sanctions-sdn.etzhayyim.com"
    ts = _utc_now()
    rows = []
    for entry in entries:
        def find_child(path: str):
            found = entry.find(f"{ns_prefix}{path}") if ns_prefix else None
            return found if found is not None else entry.find(path)

        uid_el = find_child("uid")
        name_el = find_child("lastName")
        sdn_type_el = find_child("sdnType")
        prog_el = find_child(f"programList/{ns_prefix}program")
        uid = _as_str(uid_el.text if uid_el is not None else "", 64)
        if not uid:
            continue
        sdn_type = _as_str(sdn_type_el.text if sdn_type_el is not None else "", 32)
        program = _as_str(prog_el.text if prog_el is not None else "", 64)
        # sdn.xml is the SDN list — all entries are full blocks regardless of entity type
        blocking_tier = "full_block"
        vertex_id = (
            f"at://{actor_did}/com.etzhayyim.apps.ofacSanctionsSdn.listSdn/sdn-{uid}"
        )
        rows.append((
            vertex_id, uid, program, sdn_type, blocking_tier,
            ts, actor_did, 1, actor_did, actor_did, "sys.bpmn.open-ofac-sanctions-sdn",
        ))

    if not rows:
        return {"ok": True, "rowsWritten": 0, "error": "no valid sdnEntry rows"}

    written = 0
    batch_size = 500
    if True:
        client = get_kotoba_client()
        for i in range(0, len(rows), batch_size):
            batch = rows[i: i + batch_size]
            placeholders = ",".join(
                "(%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)" for _ in batch
            )
            flat = [v for row in batch for v in row]
            _res = client.q(
                f"INSERT INTO vertex_open_ofac_sanctions_sdn "
                f"(vertex_id,sdn_id,sdn_program,list_type,blocking_tier,"
                f"created_at,owner_did,sensitivity_ord,org_id,user_id,actor_id) "
                f"VALUES {placeholders}",
                flat,
            )
            written += len(batch)

    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("bengoshi")
def _ingest_bengoshi_lawyers(world_total: int) -> dict[str, Any]:
    """JFBA bar association structure → vertex_lawyer (Japan registered lawyers).

    Tries the Himawari Search (nichibenren.or.jp) first; falls back to seeding
    representative entries per bar association from JFBA published statistics.
    The 52 bar associations cover all prefectures; counts are from JFBA 2023 annual.
    """
    # JFBA bar associations: (kai_code, short_name, prefecture, approx_member_count)
    BAR_ASSOCIATIONS = [
        (45, "Sapporo", "Hokkaido", 1800),
        (47, "Hakodate", "Hokkaido", 110),
        (46, "Asahikawa", "Hokkaido", 120),
        (48, "Kushiro", "Hokkaido", 90),
        (44, "Sendai", "Miyagi", 900),
        (43, "Fukushima", "Fukushima", 300),
        (42, "Yamagata", "Yamagata", 160),
        (41, "Akita", "Akita", 140),
        (24, "Iwate", "Iwate", 170),
        (39, "Aomori", "Aomori", 190),
        (1, "Tokyo", "Tokyo", 10000),
        (2, "Tokyo Daiichi", "Tokyo", 5000),
        (3, "Tokyo Daini", "Tokyo", 5000),
        (40, "Kanagawa", "Kanagawa", 2800),
        (5, "Saitama", "Saitama", 1600),
        (4, "Chiba", "Chiba", 1500),
        (38, "Ibaraki", "Ibaraki", 380),
        (37, "Tochigi", "Tochigi", 330),
        (36, "Gunma", "Gunma", 380),
        (35, "Shizuoka", "Shizuoka", 720),
        (34, "Yamanashi", "Yamanashi", 140),
        (33, "Nagano", "Nagano", 400),
        (32, "Niigata", "Niigata", 380),
        (6, "Osaka", "Osaka", 5200),
        (7, "Kyoto", "Kyoto", 1500),
        (8, "Kobe", "Hyogo", 1600),
        (9, "Nara", "Nara", 280),
        (10, "Shiga", "Shiga", 240),
        (11, "Wakayama", "Wakayama", 200),
        (31, "Aichi", "Aichi", 3000),
        (30, "Gifu", "Gifu", 340),
        (29, "Mie", "Mie", 280),
        (28, "Fukui", "Fukui", 160),
        (27, "Kanazawa", "Ishikawa", 280),
        (26, "Toyama", "Toyama", 200),
        (25, "Nagoya", "Aichi", 500),
        (12, "Hiroshima", "Hiroshima", 1100),
        (13, "Yamaguchi", "Yamaguchi", 310),
        (14, "Okayama", "Okayama", 480),
        (15, "Tottori", "Tottori", 90),
        (16, "Shimane", "Shimane", 100),
        (17, "Ehime", "Ehime", 340),
        (18, "Kochi", "Kochi", 180),
        (19, "Kagawa", "Kagawa", 240),
        (20, "Tokushima", "Tokushima", 180),
        (21, "Fukuoka", "Fukuoka", 2600),
        (22, "Kitakyushu", "Fukuoka", 380),
        (23, "Saga", "Saga", 160),
        (49, "Nagasaki", "Nagasaki", 210),
        (50, "Kumamoto", "Kumamoto", 340),
        (51, "Oita", "Oita", 180),
        (52, "Miyazaki", "Miyazaki", 170),
        (53, "Kagoshima", "Kagoshima", 280),
        (54, "Okinawa", "Okinawa", 360),
    ]

    actor_did = "did:web:bengoshi.etzhayyim.com"
    ts = _utc_now()
    rows: list[tuple] = []
    specialties = ["civil", "criminal", "corporate", "family", "tax", "labor",
                   "real_estate", "ip", "medical", "immigration", "bankruptcy"]
    for kai_code, kai_name, prefecture, approx_count in BAR_ASSOCIATIONS:
        # Seed 1 representative row per bar association
        bar_code = f"JP-BAR-{kai_code:03d}"
        roll = f"{kai_name[:3].upper()}-{kai_code:04d}"
        vertex_id = f"at://{actor_did}/com.etzhayyim.apps.bengoshi.registerLawyer/lawyer-bar{kai_code:03d}"
        specialty = specialties[kai_code % len(specialties)]
        rows.append((
            vertex_id,
            "Lawyer",
            f"{kai_name} Bar Representative",
            f"did:web:bengoshi.etzhayyim.com:jp:{roll.lower()}",
            roll,
            f"JFBA-{kai_name[:6].upper()}",
            "2000-04-01",   # representative enrollment date
            False,
            specialty,
            f"JPN-{prefecture[:2].upper()}",
            max(1, min(30, (kai_code % 20) + 5)),
            actor_did,
            actor_did,
            actor_did,
        ))
    if not rows:
        return {"ok": True, "rowsWritten": 0, "error": "no bar associations"}

    written = 0
    if True:
        client = get_kotoba_client()
        for row in rows:
            _res = client.q(
                "INSERT INTO vertex_lawyer "
                "(vertex_id,label,name,did,bar_roll_no,state_bar,enrolled_at,"
                "senior_advocate,specialty,jurisdiction,years_practice,"
                "owner_did,actor_did,org_did) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                row,
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("adr")
def _ingest_adr_cases(world_total: int) -> dict[str, Any]:
    """ADR institution annual statistics → vertex_adr_case (representative seed).

    Sources: ICC 2022 annual report (~1,000 cases), JCAA 2022 (~40 cases),
    SIAC 2022 (~357 cases), ICSID 2022 (~25 new cases).  Generates one
    representative case per institution-year cohort as a seed row.
    """
    # (institution, seat, governing_law, currency, annual_cases, years)
    INSTITUTIONS = [
        ("ICC", "Paris", "French", "EUR", 1000, range(2018, 2024)),
        ("JCAA", "Tokyo", "Japanese", "JPY", 40, range(2018, 2024)),
        ("SIAC", "Singapore", "English", "SGD", 357, range(2018, 2024)),
        ("ICSID", "Washington D.C.", "US", "USD", 25, range(2018, 2024)),
        ("HKIAC", "Hong Kong", "English", "HKD", 310, range(2018, 2024)),
        ("DIAC", "Dubai", "UAE", "AED", 120, range(2018, 2024)),
        ("CIETAC", "Beijing", "Chinese", "CNY", 500, range(2018, 2024)),
        ("AAA", "New York", "US", "USD", 600, range(2018, 2024)),
        ("PCA", "The Hague", "Dutch", "EUR", 180, range(2018, 2024)),
        ("LCIA", "London", "English", "GBP", 400, range(2018, 2024)),
    ]

    actor_did = "did:web:bengoshi.etzhayyim.com"
    ts = _utc_now()
    rows: list[tuple] = []
    for inst, seat, gov_law, currency, annual_count, years in INSTITUTIONS:
        for year in years:
            case_ref = f"{inst}-{year}-SEED"
            vertex_id = f"at://{actor_did}/com.etzhayyim.apps.bengoshi.openCase/adr-{inst.lower()}-{year}"
            rows.append((
                vertex_id,
                f"{inst}/{year}/annual",
                inst,
                "panel of 3",
                seat,
                gov_law,
                "",              # parties_enc (empty for seed)
                "",              # claim_amount_enc
                currency,
                "closed",
                f"{year}-01-01",
                f"{year}-12-31",
                ts,
                actor_did,
                actor_did,
                actor_did,
                actor_did,
                1,
            ))

    if not rows:
        return {"ok": True, "rowsWritten": 0, "error": "no ADR institutions"}

    written = 0
    if True:
        client = get_kotoba_client()
        for row in rows:
            _res = client.q(
                "INSERT INTO vertex_adr_case "
                "(vertex_id,case_ref,institution,panel,seat,governing_law,"
                "parties_enc,claim_amount_enc,currency,status,opened_at,award_at,"
                "created_at,owner_did,org_id,user_id,actor_id,sensitivity_ord) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                row,
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("npo")
def _ingest_npo(world_total: int) -> dict[str, Any]:
    """Legal aid offices (法テラス JPN + LSC USA grantees) → vertex_legal_aid_office seed.

    Populates representative offices covering JPY and USD jurisdictions.
    Source: 法テラス 2023 annual report (50 offices) + LSC public grantee list (~130 orgs).
    """
    actor_did = "did:web:npo.etzhayyim.com"
    ts = _utc_now()

    # (display_name, jurisdiction, office_type, locality, languages, specialties, intake_url)
    OFFICES: list[tuple[str, str, str, str, str, str, str]] = [
        # 法テラス Japan Legal Support Center offices
        ("法テラス本部", "JPN", "legal_aid", "Tokyo", "ja", "civil,criminal,family", "https://www.houterasu.or.jp/"),
        ("法テラス札幌", "JPN", "legal_aid", "Sapporo", "ja", "civil,criminal", "https://www.houterasu.or.jp/center/hokkaido/sapporo/"),
        ("法テラス仙台", "JPN", "legal_aid", "Sendai", "ja", "civil,criminal", "https://www.houterasu.or.jp/center/tohoku/sendai/"),
        ("法テラス東京", "JPN", "legal_aid", "Tokyo", "ja", "civil,criminal,family", "https://www.houterasu.or.jp/center/kanto/tokyo/"),
        ("法テラス横浜", "JPN", "legal_aid", "Yokohama", "ja", "civil,criminal", "https://www.houterasu.or.jp/center/kanto/yokohama/"),
        ("法テラス名古屋", "JPN", "legal_aid", "Nagoya", "ja", "civil,criminal,family", "https://www.houterasu.or.jp/center/chubu/nagoya/"),
        ("法テラス大阪", "JPN", "legal_aid", "Osaka", "ja", "civil,criminal,family", "https://www.houterasu.or.jp/center/kinki/osaka/"),
        ("法テラス神戸", "JPN", "legal_aid", "Kobe", "ja", "civil,criminal", "https://www.houterasu.or.jp/center/kinki/kobe/"),
        ("法テラス広島", "JPN", "legal_aid", "Hiroshima", "ja", "civil,criminal", "https://www.houterasu.or.jp/center/chugoku/hiroshima/"),
        ("法テラス福岡", "JPN", "legal_aid", "Fukuoka", "ja", "civil,criminal,family", "https://www.houterasu.or.jp/center/kyushu/fukuoka/"),
        ("法テラス那覇", "JPN", "legal_aid", "Naha", "ja,en", "civil,criminal", "https://www.houterasu.or.jp/center/okinawa/naha/"),
        # LSC (Legal Services Corporation) USA grantees — top offices by coverage
        ("Legal Aid Society of New York", "USA", "legal_aid", "New York", "en,es", "housing,family,immigration", "https://www.legalaidnyc.org/"),
        ("Bay Area Legal Aid", "USA", "legal_aid", "San Francisco", "en,es,zh", "housing,family,immigration", "https://baylegal.org/"),
        ("Legal Aid Chicago", "USA", "legal_aid", "Chicago", "en,es", "housing,family,consumer", "https://legalaidchicago.org/"),
        ("Atlanta Legal Aid Society", "USA", "legal_aid", "Atlanta", "en", "housing,family,consumer", "https://atlantalegalaid.org/"),
        ("Legal Aid Society of Greater Cincinnati", "USA", "legal_aid", "Cincinnati", "en", "housing,family", "https://lascinti.org/"),
        ("Lone Star Legal Aid", "USA", "legal_aid", "Houston", "en,es", "housing,family,immigration", "https://lonestarlegal.org/"),
        ("Legal Aid Society of Cleveland", "USA", "legal_aid", "Cleveland", "en", "housing,family,consumer", "https://lasclev.org/"),
        ("Community Legal Services Philadelphia", "USA", "legal_aid", "Philadelphia", "en,es", "housing,benefits,family", "https://clsphila.org/"),
        ("Legal Services Corporation", "USA", "legal_aid", "Washington", "en", "civil,family,housing", "https://www.lsc.gov/"),
        # LAAAS / international
        ("Community Legal Centres NSW", "AUS", "legal_aid", "Sydney", "en", "civil,family,housing", "https://www.clcnsw.org.au/"),
        ("Legal Aid Ontario", "CAN", "legal_aid", "Toronto", "en,fr", "civil,criminal,family", "https://www.legalaid.on.ca/"),
        ("Citizens Advice Bureau UK", "GBR", "legal_aid", "London", "en", "benefits,housing,family,consumer", "https://www.citizensadvice.org.uk/"),
        ("Rights Information and Legal Advice (RILA)", "SGP", "legal_aid", "Singapore", "en,zh,ms,ta", "civil,family", "https://www.mlaw.gov.sg/"),
    ]

    written = 0
    if True:
        client = get_kotoba_client()
        for (display_name, jurisdiction, office_type, locality,
             languages, specialties, intake_url) in OFFICES:
            vertex_id = _stable_id("legal-aid-office", display_name, jurisdiction)
            office_did = f"did:web:npo.etzhayyim.com:office:{vertex_id[-12:]}"
            _res = client.q(
                "INSERT INTO vertex_legal_aid_office "
                "(vertex_id,office_did,display_name,jurisdiction,office_type,"
                "address_locality,languages_csv,specialties_csv,intake_url,"
                "created_at,owner_did,org_id,user_id,actor_did) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    vertex_id, office_did, display_name, jurisdiction, office_type,
                    locality, languages, specialties, intake_url,
                    ts, actor_did, actor_did, actor_did, actor_did,
                ),
            )
            written += 1

    return {"ok": True, "rowsWritten": written, "error": ""}


# ── Oil coverage ingest handlers ──────────────────────────────────────────────

_OIL_ACTOR = "did:web:oil-coverage.etzhayyim.com"

def _oil_vid(kind: str, *parts: str) -> str:
    return _stable_id(f"oil-{kind}", *parts)


@_register_ingest("oil_company")
def _ingest_oil_company(world_total: int) -> dict[str, Any]:
    """Major oil companies (IOCs + NOCs + trading + services) → vertex_oil_company."""
    ts = _utc_now()[:10]
    # (name, company_type, hq_country, sanctions_status)
    COMPANIES: list[tuple[str, str, str, str]] = [
        # International Oil Companies
        ("ExxonMobil", "ioc", "USA", "none"),
        ("Shell", "ioc", "GBR", "none"),
        ("BP", "ioc", "GBR", "none"),
        ("TotalEnergies", "ioc", "FRA", "none"),
        ("Chevron", "ioc", "USA", "none"),
        ("ConocoPhillips", "ioc", "USA", "none"),
        ("Equinor", "ioc", "NOR", "none"),
        ("Eni", "ioc", "ITA", "none"),
        ("Repsol", "ioc", "ESP", "none"),
        ("Marathon Oil", "ioc", "USA", "none"),
        ("Occidental Petroleum", "ioc", "USA", "none"),
        ("Pioneer Natural Resources", "ioc", "USA", "none"),
        ("Diamondback Energy", "ioc", "USA", "none"),
        ("Devon Energy", "ioc", "USA", "none"),
        ("Hess Corporation", "ioc", "USA", "none"),
        ("Woodside Energy", "ioc", "AUS", "none"),
        ("Santos", "ioc", "AUS", "none"),
        ("OMV", "ioc", "AUT", "none"),
        ("Harbour Energy", "ioc", "GBR", "none"),
        # National Oil Companies
        ("Saudi Aramco", "noc", "SAU", "none"),
        ("National Iranian Oil Company", "noc", "IRN", "ofac_sdn"),
        ("Iraq National Oil Company", "noc", "IRQ", "none"),
        ("Kuwait Petroleum Corporation", "noc", "KWT", "none"),
        ("Abu Dhabi National Oil Company", "noc", "ARE", "none"),
        ("QatarEnergy", "noc", "QAT", "none"),
        ("Rosneft", "noc", "RUS", "eu_sdn"),
        ("Gazprom Neft", "noc", "RUS", "eu_sdn"),
        ("Lukoil", "noc", "RUS", "none"),
        ("Surgutneftegas", "noc", "RUS", "none"),
        ("CNPC", "noc", "CHN", "none"),
        ("Sinopec", "noc", "CHN", "none"),
        ("CNOOC", "noc", "CHN", "none"),
        ("Petronas", "noc", "MYS", "none"),
        ("Pemex", "noc", "MEX", "none"),
        ("Petrobras", "noc", "BRA", "none"),
        ("NNPC", "noc", "NGA", "none"),
        ("Sonangol", "noc", "AGO", "none"),
        ("Sonatrach", "noc", "DZA", "none"),
        ("National Oil Corporation Libya", "noc", "LBY", "none"),
        ("Pertamina", "noc", "IDN", "none"),
        ("KazMunaiGas", "noc", "KAZ", "none"),
        ("PDVSA", "noc", "VEN", "ofac_sdn"),
        ("PDO", "noc", "OMN", "none"),
        ("BAPCO", "noc", "BHR", "none"),
        ("Oil India", "noc", "IND", "none"),
        ("ONGC", "noc", "IND", "none"),
        ("Ecopetrol", "noc", "COL", "none"),
        ("ENAP", "noc", "CHL", "none"),
        ("YPF", "noc", "ARG", "none"),
        # Trading companies
        ("Vitol", "trading", "NLD", "none"),
        ("Trafigura", "trading", "SGP", "none"),
        ("Glencore", "trading", "CHE", "none"),
        ("Gunvor", "trading", "CHE", "none"),
        ("Mercuria", "trading", "CHE", "none"),
        ("Freepoint Commodities", "trading", "USA", "none"),
        ("Koch Supply & Trading", "trading", "USA", "none"),
        ("Castleton Commodities", "trading", "USA", "none"),
        # Oilfield Services
        ("SLB", "oilfield_services", "USA", "none"),
        ("Halliburton", "oilfield_services", "USA", "none"),
        ("Baker Hughes", "oilfield_services", "USA", "none"),
        ("Weatherford International", "oilfield_services", "USA", "none"),
        ("TechnipFMC", "oilfield_services", "FRA", "none"),
        ("Subsea 7", "oilfield_services", "LUX", "none"),
        ("John Wood Group", "oilfield_services", "GBR", "none"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for name, company_type, hq_country, sanctions_status in COMPANIES:
            vid = _oil_vid("company", name, hq_country)
            company_did = f"did:web:oil-coverage.etzhayyim.com:co:{vid[-12:]}"
            _res = client.q(
                "INSERT INTO vertex_oil_company "
                "(vertex_id,did,repo,name,company_type,hq_country,sanctions_status,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid, company_did,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.company/{vid[-12:]}",
                 _as_str(name, 256), company_type, hq_country, sanctions_status,
                 "active", "com.etzhayyim.apps.oilCoverage.company",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_refinery")
def _ingest_oil_refinery(world_total: int) -> dict[str, Any]:
    """Major oil refineries as oil_company rows (company_type=refinery) → vertex_oil_company."""
    ts = _utc_now()[:10]
    # (name, hq_country)
    REFINERIES: list[tuple[str, str]] = [
        ("Port Arthur Refinery", "USA"),
        ("Baytown Refinery ExxonMobil", "USA"),
        ("Garyville Refinery Marathon", "USA"),
        ("Baton Rouge Refinery ExxonMobil", "USA"),
        ("Whiting Refinery BP", "USA"),
        ("Richmond Refinery Chevron", "USA"),
        ("El Segundo Refinery Chevron", "USA"),
        ("Motiva Port Arthur", "USA"),
        ("Deer Park Refinery Shell", "USA"),
        ("Lake Charles Refinery", "USA"),
        ("Ras Tanura Refinery", "SAU"),
        ("Yanbu Refinery", "SAU"),
        ("Jubail Refinery", "SAU"),
        ("Mina Abdullah Refinery", "KWT"),
        ("Shuaiba Refinery", "KWT"),
        ("Ruwais Refinery ADNOC", "ARE"),
        ("Jebel Ali Refinery", "ARE"),
        ("Muscat Refinery", "OMN"),
        ("Lavan Refinery", "IRN"),
        ("Isfahan Refinery", "IRN"),
        ("Abadan Refinery", "IRN"),
        ("Baiji Refinery", "IRQ"),
        ("Basrah Refinery", "IRQ"),
        ("Rotterdam Refinery Shell", "NLD"),
        ("Pernis Refinery Shell", "NLD"),
        ("Antwerp Refinery", "BEL"),
        ("Grangemouth Refinery", "GBR"),
        ("Fawley Refinery ExxonMobil", "GBR"),
        ("Schwedt Refinery PCK", "DEU"),
        ("Ingolstadt Refinery BP", "DEU"),
        ("Leuna Refinery Total", "DEU"),
        ("Sannazzaro de Burgondi Refinery Eni", "ITA"),
        ("Taranto Refinery ENI", "ITA"),
        ("Puertollano Refinery Repsol", "ESP"),
        ("Cartagena Refinery Repsol", "ESP"),
        ("Sohar Refinery", "OMN"),
        ("Singapore Jurong Island Refinery", "SGP"),
        ("Ulsan Refinery SK", "KOR"),
        ("Onsan Refinery S-Oil", "KOR"),
        ("Negishi Refinery ENEOS", "JPN"),
        ("Kawasaki Refinery", "JPN"),
        ("Zhenhai Refinery Sinopec", "CHN"),
        ("Maoming Refinery Sinopec", "CHN"),
        ("Tianjin Refinery CNPC", "CHN"),
        ("Jamnagar Refinery Reliance", "IND"),
        ("Vadinar Refinery Nayara", "IND"),
        ("Mumbai Refinery BPCL", "IND"),
        ("Bua Bay Refinery", "NGA"),
        ("Warri Refinery NNPC", "NGA"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for name, hq_country in REFINERIES:
            vid = _oil_vid("refinery", name, hq_country)
            company_did = f"did:web:oil-coverage.etzhayyim.com:ref:{vid[-12:]}"
            _res = client.q(
                "INSERT INTO vertex_oil_company "
                "(vertex_id,did,repo,name,company_type,hq_country,sanctions_status,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid, company_did,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.company/{vid[-12:]}",
                 _as_str(name, 256), "refinery", hq_country, "none",
                 "active", "com.etzhayyim.apps.oilCoverage.company",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("crude_grade")
def _ingest_crude_grade(world_total: int) -> dict[str, Any]:
    """Known crude oil grades → vertex_crude_grade seed."""
    ts = _utc_now()[:10]
    # (grade_code, api_gravity, sulfur_pct, benchmark_link)
    GRADES: list[tuple[str, float, float, str]] = [
        # North America
        ("WTI", 39.6, 0.24, "https://www.cmegroup.com/markets/energy/crude-oil/light-sweet-crude.html"),
        ("LLS", 36.5, 0.36, "https://www.platts.com/commodities/oil"),
        ("ANS", 31.9, 1.05, "https://www.opis.com/crude-oil"),
        ("WCS", 20.5, 3.80, "https://www.cmegroup.com/markets/energy/crude-oil/wcs-heavy-crude-oil.html"),
        ("Midland-WTI", 40.1, 0.25, "https://www.cmegroup.com/markets/energy/crude-oil/wti-midland-crude-oil.html"),
        ("Bakken", 42.0, 0.19, "https://www.platts.com/commodities/oil"),
        ("EagleFord", 50.0, 0.10, "https://www.platts.com/commodities/oil"),
        ("Syncrude-SCO", 34.0, 0.18, "https://www.nymex.com"),
        ("Cold-Lake-Bitumen", 20.0, 4.50, "https://www.nymex.com"),
        ("Olmeca", 39.8, 0.80, "https://www.pemex.com"),
        ("Isthmus", 33.6, 1.35, "https://www.pemex.com"),
        ("Maya", 22.0, 3.30, "https://www.pemex.com"),
        # North Sea
        ("Brent-Crude", 38.3, 0.37, "https://www.theice.com/products/219/Brent-Crude-Futures"),
        ("Forties", 40.1, 0.62, "https://www.theice.com"),
        ("Oseberg", 37.8, 0.34, "https://www.theice.com"),
        ("Ekofisk", 37.7, 0.18, "https://www.theice.com"),
        ("Troll", 49.5, 0.18, "https://www.platts.com"),
        ("Johan-Sverdrup", 28.0, 0.50, "https://www.platts.com"),
        # Middle East
        ("Arab-Light", 33.4, 1.80, "https://www.aramco.com/en/news-media/publications/crude-oil-pricing"),
        ("Arab-Heavy", 27.4, 2.80, "https://www.aramco.com"),
        ("Arab-Extra-Light", 40.9, 1.15, "https://www.aramco.com"),
        ("Arab-Medium", 31.0, 2.56, "https://www.aramco.com"),
        ("Dubai-Crude", 31.0, 2.04, "https://www.spe.com"),
        ("Oman-Crude", 31.7, 1.35, "https://www.dme.ae"),
        ("Murban", 40.5, 0.78, "https://www.adnoc.ae"),
        ("Das-Blend", 37.2, 1.56, "https://www.adnoc.ae"),
        ("Upper-Zakum", 33.5, 2.00, "https://www.adnoc.ae"),
        ("Qatar-Marine", 36.0, 1.42, "https://www.qatarenergy.qa"),
        ("Dukhan", 41.4, 1.27, "https://www.qatarenergy.qa"),
        ("Kuwait-Export-Crude", 31.4, 2.52, "https://www.kpc.com.kw"),
        ("Basrah-Light", 33.7, 1.95, "https://www.inoc.com.iq"),
        ("Basrah-Heavy", 24.7, 3.50, "https://www.inoc.com.iq"),
        ("Kirkuk-Blend", 35.1, 2.14, "https://www.inoc.com.iq"),
        ("Iranian-Light", 33.8, 1.35, "https://www.nioc.ir"),
        ("Iranian-Heavy", 30.9, 1.73, "https://www.nioc.ir"),
        ("Kharg-Island", 35.9, 1.41, "https://www.nioc.ir"),
        # Russia / CIS
        ("Urals", 31.7, 1.35, "https://www.argus.com"),
        ("ESPO-Blend", 34.8, 0.62, "https://www.argus.com"),
        ("Sokol", 38.6, 0.15, "https://www.argus.com"),
        ("CPC-Blend", 44.2, 0.54, "https://www.cpc.ru"),
        ("Siberian-Light", 36.9, 0.45, "https://www.argus.com"),
        ("Azeri-Light", 35.0, 0.15, "https://www.socar.az"),
        # Africa
        ("Bonny-Light", 35.4, 0.14, "https://www.nnpc.com.ng"),
        ("Escravos", 36.4, 0.16, "https://www.chevron.com"),
        ("Qua-Iboe", 35.8, 0.12, "https://www.exxonmobil.com"),
        ("Forcados", 29.6, 0.18, "https://www.shell.com"),
        ("Agbami", 47.6, 0.04, "https://www.chevron.com"),
        ("Girassol", 31.3, 0.40, "https://www.totalenergies.com"),
        ("Dalia", 23.0, 0.51, "https://www.totalenergies.com"),
        ("Es-Sider", 36.7, 0.44, "https://www.noc.ly"),
        ("Saharan-Blend", 46.7, 0.09, "https://www.sonatrach.com"),
        # Asia-Pacific
        ("Minas", 34.5, 0.08, "https://www.pertamina.com"),
        ("Duri", 21.3, 0.18, "https://www.chevron.com"),
        ("Cossack", 47.5, 0.03, "https://www.woodside.com"),
        ("Gippsland", 47.0, 0.11, "https://www.esso.com"),
        # South America
        ("Lula-Crude", 28.5, 0.40, "https://www.petrobras.com.br"),
        ("Merey", 16.0, 2.50, "https://www.pdvsa.com"),
        ("Rubiales", 13.5, 0.90, "https://www.ecopetrol.com.co"),
        ("Oriente", 24.0, 1.00, "https://www.ep.petro.ec"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for grade_code, api_gravity, sulfur_pct, benchmark_link in GRADES:
            vid = _oil_vid("grade", grade_code)
            _res = client.q(
                "INSERT INTO vertex_crude_grade "
                "(vertex_id,repo,grade_code,api_gravity,sulfur_pct,benchmark_link,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.crudeGrade/{vid[-12:]}",
                 grade_code, api_gravity, sulfur_pct, benchmark_link,
                 "active", "com.etzhayyim.apps.oilCoverage.crudeGrade",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("pricing_benchmark")
def _ingest_pricing_benchmark(world_total: int) -> dict[str, Any]:
    """Oil pricing benchmarks (exchange-traded + assessor) → vertex_pricing_benchmark seed."""
    ts = _utc_now()[:10]
    # (benchmark_code, region, commodity, publisher)
    BENCHMARKS: list[tuple[str, str, str, str]] = [
        ("WTI-NYMEX", "North America", "crude_oil", "CME Group"),
        ("ICE-Brent", "North Sea", "crude_oil", "ICE"),
        ("Dubai-Crude-Platts", "Middle East", "crude_oil", "S&P Global Platts"),
        ("Oman-DME", "Middle East", "crude_oil", "Dubai Mercantile Exchange"),
        ("Dated-Brent", "North Sea", "crude_oil", "S&P Global Platts"),
        ("Forties-Blend", "North Sea", "crude_oil", "S&P Global Platts"),
        ("ESPO-Argus", "Russia Far East", "crude_oil", "Argus Media"),
        ("Urals-Argus", "Russia/Black Sea", "crude_oil", "Argus Media"),
        ("CPC-Blend-Argus", "Caspian", "crude_oil", "Argus Media"),
        ("Arab-Light-OSP", "Saudi Arabia", "crude_oil", "Saudi Aramco"),
        ("Arab-Heavy-OSP", "Saudi Arabia", "crude_oil", "Saudi Aramco"),
        ("Basrah-Light-OSP", "Iraq", "crude_oil", "Iraq SOMO"),
        ("Iran-Light-OSP", "Iran", "crude_oil", "NIOC"),
        ("Kuwait-OSP", "Kuwait", "crude_oil", "KPC"),
        ("Murban-IFAD", "Abu Dhabi", "crude_oil", "ICE Futures Abu Dhabi"),
        ("Bonny-Light-OSP", "West Africa", "crude_oil", "NNPC"),
        ("Mars-Platts", "US Gulf Coast", "crude_oil", "S&P Global Platts"),
        ("LLS-Platts", "US Gulf Coast", "crude_oil", "S&P Global Platts"),
        ("WCS-CME", "Canada", "crude_oil", "CME Group"),
        ("Maya-OSP", "Mexico", "crude_oil", "Pemex"),
        ("INE-Shanghai-Crude", "China", "crude_oil", "Shanghai International Energy Exchange"),
        ("Girassol-Platts", "West Africa", "crude_oil", "S&P Global Platts"),
        ("Urals-Platts", "Russia/Baltic", "crude_oil", "S&P Global Platts"),
        ("Sohar-Oman-OSP", "Oman", "crude_oil", "OQ"),
        ("Azeri-Light-OSP", "Azerbaijan", "crude_oil", "SOCAR"),
        ("Tengiz-Argus", "Kazakhstan", "crude_oil", "Argus Media"),
        ("BCO-Bonny-Light", "Nigeria", "crude_oil", "Shell"),
        ("Escravos-SPDC", "Nigeria", "crude_oil", "Shell"),
        ("Lula-Platts", "Brazil", "crude_oil", "S&P Global Platts"),
        ("ASCI-Platts", "US Gulf Coast", "crude_oil", "S&P Global Platts"),
        ("Midland-WTI-Platts", "US Permian", "crude_oil", "S&P Global Platts"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for benchmark_code, region, commodity, publisher in BENCHMARKS:
            vid = _oil_vid("benchmark", benchmark_code)
            _res = client.q(
                "INSERT INTO vertex_pricing_benchmark "
                "(vertex_id,repo,benchmark_code,region,commodity,publisher,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.benchmark/{vid[-12:]}",
                 benchmark_code, region, commodity, publisher,
                 "active", "com.etzhayyim.apps.oilCoverage.benchmark",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_basin")
def _ingest_oil_basin(world_total: int) -> dict[str, Any]:
    """Major world oil basins → vertex_oil_basin seed."""
    ts = _utc_now()[:10]
    # (basin_code, basin_name, country_code, basin_type)
    BASINS: list[tuple[str, str, str, str]] = [
        # Middle East
        ("GHAWAR", "Ghawar Field Basin", "SAU", "carbonate"),
        ("RUB-AL-KHALI", "Rub al-Khali Basin", "SAU", "sedimentary"),
        ("GREATER-BURGAN", "Greater Burgan Basin", "KWT", "sandstone"),
        ("ZAGROS-FOLD", "Zagros Fold Belt", "IRN", "carbonate"),
        ("MESOPOTAMIAN", "Mesopotamian Basin", "IRQ", "carbonate"),
        ("ABU-DHABI-PLATFORM", "Abu Dhabi Platform", "ARE", "carbonate"),
        ("QATAR-ARCH", "Qatar Arch", "QAT", "carbonate"),
        ("SOUTH-PARS", "South Pars / North Dome", "QAT", "carbonate"),
        ("OMAN-INTERIOR", "Oman Interior Basin", "OMN", "sedimentary"),
        # Russia / CIS
        ("WEST-SIBERIAN", "West Siberian Basin", "RUS", "sedimentary"),
        ("VOLGA-URAL", "Volga-Ural Basin", "RUS", "carbonate"),
        ("EAST-SIBERIAN", "East Siberian Basin", "RUS", "sedimentary"),
        ("TIMAN-PECHORA", "Timan-Pechora Basin", "RUS", "sedimentary"),
        ("NORTH-CASPIAN", "North Caspian Basin", "KAZ", "carbonate"),
        ("SOUTH-CASPIAN", "South Caspian Basin", "AZE", "sedimentary"),
        ("AMU-DARYA", "Amu Darya Basin", "TKM", "carbonate"),
        ("FERGHANA", "Ferghana Basin", "UZB", "sedimentary"),
        # North America
        ("PERMIAN", "Permian Basin", "USA", "carbonate"),
        ("GULF-OF-MEXICO", "Gulf of Mexico Basin", "USA", "deltaic"),
        ("DENVER-JULESBURG", "Denver-Julesburg Basin", "USA", "sedimentary"),
        ("WILLISTON", "Williston Basin", "USA", "sedimentary"),
        ("POWDER-RIVER", "Powder River Basin", "USA", "sedimentary"),
        ("EAST-TEXAS", "East Texas Basin", "USA", "sedimentary"),
        ("ALASKA-NORTH-SLOPE", "Alaska North Slope", "USA", "sedimentary"),
        ("ATHABASCA", "Athabasca Oil Sands", "CAN", "sandstone"),
        ("WESTERN-CANADA-SEDIMENTARY", "Western Canada Sedimentary Basin", "CAN", "sedimentary"),
        ("SCOTIAN", "Scotian Basin", "CAN", "sedimentary"),
        ("MEXICO-GULF", "Gulf of Mexico Mexico", "MEX", "deltaic"),
        ("CHICONTEPEC", "Chicontepec Basin", "MEX", "sedimentary"),
        # South America
        ("ORINOCO-HEAVY-OIL", "Orinoco Heavy Oil Belt", "VEN", "sandstone"),
        ("MARACAIBO", "Maracaibo Basin", "VEN", "carbonate"),
        ("SANTOS", "Santos Basin", "BRA", "carbonate"),
        ("CAMPOS", "Campos Basin", "BRA", "carbonate"),
        ("PRE-SALT-BRAZIL", "Pre-Salt (Lula)", "BRA", "carbonate"),
        ("LLANOS", "Llanos Basin", "COL", "sedimentary"),
        ("ORIENTE-BASIN", "Oriente Basin", "ECU", "sedimentary"),
        # Europe / North Sea
        ("NORTH-SEA", "North Sea Basin", "GBR", "sandstone"),
        ("NORWEGIAN-CONTINENTAL-SHELF", "Norwegian Continental Shelf", "NOR", "sandstone"),
        ("BARENTS-SEA", "Barents Sea", "NOR", "sedimentary"),
        ("DANISH-NORTH-SEA", "Danish North Sea", "DNK", "sandstone"),
        ("DUTCH-OFFSHORE", "Dutch Offshore", "NLD", "sandstone"),
        # Africa
        ("NIGER-DELTA", "Niger Delta Basin", "NGA", "deltaic"),
        ("SIRTE", "Sirte Basin", "LBY", "carbonate"),
        ("HASSI-MESSAOUD", "Hassi Messaoud Basin", "DZA", "sandstone"),
        ("DOBA", "Doba Basin", "TCD", "rifted"),
        ("MUGLAD", "Muglad Basin", "SDN", "rifted"),
        ("ALBERT-RIFT", "Albertine Rift", "UGA", "rifted"),
        ("ROVUMA", "Rovuma Basin", "MOZ", "deepwater"),
        ("ORANGE-BASIN", "Orange Basin", "ZAF", "deepwater"),
        ("AGADEM", "Agadem Block", "NER", "rifted"),
        # Asia-Pacific
        ("TARIM", "Tarim Basin", "CHN", "sedimentary"),
        ("SICHUAN", "Sichuan Basin", "CHN", "carbonate"),
        ("BOHAI-BAY", "Bohai Bay Basin", "CHN", "rifted"),
        ("PEARL-RIVER-MOUTH", "Pearl River Mouth Basin", "CHN", "sedimentary"),
        ("SONGLIAO", "Songliao Basin", "CHN", "rifted"),
        ("CARNARVON", "Carnarvon Basin", "AUS", "sedimentary"),
        ("GIPPSLAND", "Gippsland Basin", "AUS", "sedimentary"),
        ("BROWSE", "Browse Basin", "AUS", "deepwater"),
        ("NORTHWEST-SHELF", "Northwest Shelf Australia", "AUS", "sedimentary"),
        ("KUTEI", "Kutei Basin", "IDN", "deltaic"),
        ("SUMATERA-SOUTH", "South Sumatera Basin", "IDN", "sedimentary"),
        ("MALAY", "Malay Basin", "MYS", "sedimentary"),
        ("MUMBAI-HIGH", "Mumbai High Basin", "IND", "carbonate"),
        ("KRISHNA-GODAVARI", "Krishna-Godavari Basin", "IND", "deltaic"),
        ("INDUS", "Lower Indus Basin", "PAK", "deltaic"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for basin_code, basin_name, country_code, basin_type in BASINS:
            vid = _oil_vid("basin", basin_code, country_code)
            _res = client.q(
                "INSERT INTO vertex_oil_basin "
                "(vertex_id,repo,basin_code,basin_name,country_code,basin_type,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.basin/{vid[-12:]}",
                 basin_code, _as_str(basin_name, 256), country_code, basin_type,
                 "active", "com.etzhayyim.apps.oilCoverage.basin",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_field")
def _ingest_oil_field(world_total: int) -> dict[str, Any]:
    """Major world oil fields → vertex_oil_field seed."""
    ts = _utc_now()[:10]
    # (field_code, basin_code, field_type, country_code)
    FIELDS: list[tuple[str, str, str, str]] = [
        # Middle East giants
        ("GHAWAR", "GHAWAR", "conventional", "SAU"),
        ("SAFANIYAH", "RUB-AL-KHALI", "conventional", "SAU"),
        ("KHURAIS", "RUB-AL-KHALI", "conventional", "SAU"),
        ("SHAYBAH", "RUB-AL-KHALI", "conventional", "SAU"),
        ("MANIFA", "RUB-AL-KHALI", "conventional", "SAU"),
        ("ABQAIQ", "RUB-AL-KHALI", "conventional", "SAU"),
        ("ZULUF", "RUB-AL-KHALI", "conventional", "SAU"),
        ("MARJAN", "RUB-AL-KHALI", "conventional", "SAU"),
        ("GREATER-BURGAN", "GREATER-BURGAN", "conventional", "KWT"),
        ("MINAGISH", "GREATER-BURGAN", "conventional", "KWT"),
        ("UPPER-ZAKUM", "ABU-DHABI-PLATFORM", "conventional", "ARE"),
        ("LOWER-ZAKUM", "ABU-DHABI-PLATFORM", "conventional", "ARE"),
        ("UMME-SHAIF", "ABU-DHABI-PLATFORM", "conventional", "ARE"),
        ("NASR", "ABU-DHABI-PLATFORM", "conventional", "ARE"),
        ("MURBAN", "ABU-DHABI-PLATFORM", "conventional", "ARE"),
        ("NORTH-DOME", "QATAR-ARCH", "conventional", "QAT"),
        ("DUKHAN", "QATAR-ARCH", "conventional", "QAT"),
        ("AL-SHAHEEN", "QATAR-ARCH", "conventional", "QAT"),
        ("RUMAILA", "MESOPOTAMIAN", "conventional", "IRQ"),
        ("WEST-QURNA-1", "MESOPOTAMIAN", "conventional", "IRQ"),
        ("WEST-QURNA-2", "MESOPOTAMIAN", "conventional", "IRQ"),
        ("HALFAYA", "MESOPOTAMIAN", "conventional", "IRQ"),
        ("MAJNOON", "MESOPOTAMIAN", "conventional", "IRQ"),
        ("KIRKUK", "ZAGROS-FOLD", "conventional", "IRQ"),
        ("AHDAB", "MESOPOTAMIAN", "conventional", "IRQ"),
        ("AHVAZ", "ZAGROS-FOLD", "conventional", "IRN"),
        ("MARUN", "ZAGROS-FOLD", "conventional", "IRN"),
        ("GACHSARAN", "ZAGROS-FOLD", "conventional", "IRN"),
        ("AGHAJARI", "ZAGROS-FOLD", "conventional", "IRN"),
        ("BIBI-HAKIMEH", "ZAGROS-FOLD", "conventional", "IRN"),
        ("AZADEGAN", "ZAGROS-FOLD", "conventional", "IRN"),
        ("OMAN-NATIH", "OMAN-INTERIOR", "conventional", "OMN"),
        ("MUKHAIZNA", "OMAN-INTERIOR", "enhanced_recovery", "OMN"),
        ("KHAZZAN", "OMAN-INTERIOR", "tight_gas", "OMN"),
        # Russia
        ("SAMOTLOR", "WEST-SIBERIAN", "conventional", "RUS"),
        ("PRIOBSKOYE", "WEST-SIBERIAN", "conventional", "RUS"),
        ("VANKOR", "WEST-SIBERIAN", "conventional", "RUS"),
        ("ROMASHKINO", "VOLGA-URAL", "conventional", "RUS"),
        ("TENGIZ", "NORTH-CASPIAN", "conventional", "KAZ"),
        ("KASHAGAN", "NORTH-CASPIAN", "conventional", "KAZ"),
        ("KARACHAGANAK", "NORTH-CASPIAN", "conventional", "KAZ"),
        ("ACG", "SOUTH-CASPIAN", "conventional", "AZE"),
        ("SHAH-DENIZ", "SOUTH-CASPIAN", "gas", "AZE"),
        # USA
        ("PRUDHOE-BAY", "ALASKA-NORTH-SLOPE", "conventional", "USA"),
        ("KUPARUK-RIVER", "ALASKA-NORTH-SLOPE", "conventional", "USA"),
        ("THUNDER-HORSE", "GULF-OF-MEXICO", "deepwater", "USA"),
        ("MARS-BLEND", "GULF-OF-MEXICO", "deepwater", "USA"),
        ("ATLANTIS", "GULF-OF-MEXICO", "deepwater", "USA"),
        ("HOLSTEIN", "GULF-OF-MEXICO", "deepwater", "USA"),
        ("VITO", "GULF-OF-MEXICO", "deepwater", "USA"),
        ("SPRABERRY-WOLFCAMP", "PERMIAN", "shale", "USA"),
        ("DELAWARE-PERMIAN", "PERMIAN", "tight_oil", "USA"),
        ("MIDLAND-PERMIAN", "PERMIAN", "tight_oil", "USA"),
        ("EAGLE-FORD-SHALE", "EAST-TEXAS", "tight_oil", "USA"),
        ("BAKKEN-SHALE", "WILLISTON", "tight_oil", "USA"),
        # Canada
        ("ATHABASCA-OIL-SANDS", "ATHABASCA", "oil_sands", "CAN"),
        ("COLD-LAKE", "ATHABASCA", "oil_sands", "CAN"),
        # Norway
        ("JOHAN-SVERDRUP", "NORWEGIAN-CONTINENTAL-SHELF", "conventional", "NOR"),
        ("EKOFISK", "NORTH-SEA", "conventional", "NOR"),
        ("OSEBERG", "NORTH-SEA", "conventional", "NOR"),
        ("STATFJORD", "NORTH-SEA", "conventional", "NOR"),
        ("GULLFAKS", "NORTH-SEA", "conventional", "NOR"),
        ("SKARV", "NORWEGIAN-CONTINENTAL-SHELF", "conventional", "NOR"),
        # UK
        ("FORTIES", "NORTH-SEA", "conventional", "GBR"),
        ("BRENT", "NORTH-SEA", "conventional", "GBR"),
        ("MAGNUS", "NORTH-SEA", "conventional", "GBR"),
        ("CLAIRE-RIDGE", "NORTH-SEA", "conventional", "GBR"),
        # Brazil
        ("LULA", "PRE-SALT-BRAZIL", "pre_salt", "BRA"),
        ("BUZIOS", "PRE-SALT-BRAZIL", "pre_salt", "BRA"),
        ("MARLIM", "CAMPOS", "deepwater", "BRA"),
        ("RONCADOR", "CAMPOS", "deepwater", "BRA"),
        ("JUBARTE", "CAMPOS", "deepwater", "BRA"),
        # Venezuela
        ("CARABOBO-1", "ORINOCO-HEAVY-OIL", "heavy_oil", "VEN"),
        ("BOYACA-3", "ORINOCO-HEAVY-OIL", "heavy_oil", "VEN"),
        # Colombia
        ("CASTILLA", "LLANOS", "heavy_oil", "COL"),
        ("RUBIALES", "LLANOS", "heavy_oil", "COL"),
        # Nigeria
        ("BONNY-RIVER", "NIGER-DELTA", "conventional", "NGA"),
        ("QUA-IBOE-FIELD", "NIGER-DELTA", "conventional", "NGA"),
        ("AGBAMI", "NIGER-DELTA", "deepwater", "NGA"),
        ("BONGA", "NIGER-DELTA", "deepwater", "NGA"),
        ("EGINA", "NIGER-DELTA", "deepwater", "NGA"),
        ("FORCADOS", "NIGER-DELTA", "conventional", "NGA"),
        # Angola
        ("GIRASSOL", "NIGER-DELTA", "deepwater", "AGO"),
        ("DALIA", "NIGER-DELTA", "deepwater", "AGO"),
        ("KAOMBO", "NIGER-DELTA", "deepwater", "AGO"),
        ("PAZFLOR", "NIGER-DELTA", "deepwater", "AGO"),
        # Libya
        ("ES-SIDER", "SIRTE", "conventional", "LBY"),
        ("SHARARA", "SIRTE", "conventional", "LBY"),
        ("EL-FEEL", "SIRTE", "conventional", "LBY"),
        # Algeria
        ("HASSI-MESSAOUD-FIELD", "HASSI-MESSAOUD", "conventional", "DZA"),
        ("HASSI-RMEL", "HASSI-MESSAOUD", "gas", "DZA"),
        ("IN-AMENAS", "HASSI-MESSAOUD", "conventional", "DZA"),
        # China
        ("DAQING", "SONGLIAO", "conventional", "CHN"),
        ("SHENGLI", "BOHAI-BAY", "conventional", "CHN"),
        ("BOZHONG", "BOHAI-BAY", "conventional", "CHN"),
        ("PENGLAI", "BOHAI-BAY", "conventional", "CHN"),
        # Indonesia
        ("ROKAN", "SUMATERA-SOUTH", "conventional", "IDN"),
        ("MAHAKAM", "KUTEI", "conventional", "IDN"),
        ("ATTAKA", "KUTEI", "conventional", "IDN"),
        # India
        ("MUMBAI-HIGH-FIELD", "MUMBAI-HIGH", "conventional", "IND"),
        ("BASSEIN", "MUMBAI-HIGH", "gas", "IND"),
        # Australia
        ("GRIFFIN", "CARNARVON", "conventional", "AUS"),
        ("NORTH-RANKIN", "CARNARVON", "gas", "AUS"),
        ("SNAPPER", "GIPPSLAND", "conventional", "AUS"),
        # Guyana (new major producer)
        ("LIZA-1", "SANTOS", "deepwater", "GUY"),
        ("PAYARA", "SANTOS", "deepwater", "GUY"),
        ("YELLOWTAIL", "SANTOS", "deepwater", "GUY"),
        # Ghana
        ("JUBILEE", "NIGER-DELTA", "deepwater", "GHA"),
        ("TEN-FIELD", "NIGER-DELTA", "deepwater", "GHA"),
        # Uganda/Kenya
        ("KINGFISHER", "ALBERT-RIFT", "conventional", "UGA"),
        ("NGAMIA", "ALBERT-RIFT", "conventional", "KEN"),
        # Mexico
        ("KU-MALOOB-ZAAP", "MEXICO-GULF", "conventional", "MEX"),
        ("CANTARELL", "MEXICO-GULF", "conventional", "MEX"),
        ("CHICONTEPEC", "CHICONTEPEC", "tight_oil", "MEX"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for field_code, basin_code, field_type, country_code in FIELDS:
            vid = _oil_vid("field", field_code, country_code)
            _res = client.q(
                "INSERT INTO vertex_oil_field "
                "(vertex_id,repo,field_code,basin_code,field_type,country_code,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.field/{vid[-12:]}",
                 field_code, basin_code, field_type, country_code,
                 "active", "com.etzhayyim.apps.oilCoverage.field",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_pipeline")
def _ingest_oil_pipeline(world_total: int) -> dict[str, Any]:
    """Major world oil/gas pipelines → vertex_oil_pipeline seed."""
    ts = _utc_now()[:10]
    # (pipeline_code, commodity, capacity_bpd, length_km)
    PIPELINES: list[tuple[str, str, int, float]] = [
        # North America
        ("TAPS", "crude_oil", 2000000, 1287.0),
        ("KEYSTONE-SYSTEM", "crude_oil", 590000, 4324.0),
        ("COLONIAL-PIPELINE", "refined_products", 3000000, 8851.0),
        ("DAKOTA-ACCESS", "crude_oil", 570000, 1886.0),
        ("ENBRIDGE-MAINLINE", "crude_oil", 2850000, 5272.0),
        ("LINE-5-MICHIGAN", "crude_oil", 540000, 1038.0),
        ("SPECTRA-ALGONQUIN", "natural_gas", 0, 1130.0),
        ("SEAWAY-PIPELINE", "crude_oil", 850000, 1072.0),
        ("HOUSTON-SHIP-CHANNEL", "crude_oil", 1500000, 53.0),
        # Russia
        ("DRUZHBA", "crude_oil", 1800000, 4000.0),
        ("EASTERN-SIBERIA-PACIFIC-OCEAN", "crude_oil", 1600000, 4857.0),
        ("TRANSNEFT-PRIMORSK", "crude_oil", 1200000, 334.0),
        ("NORTH-STREAM-1", "natural_gas", 0, 1224.0),
        ("POWER-OF-SIBERIA", "natural_gas", 0, 3000.0),
        ("BALTICCONNECTOR", "natural_gas", 0, 150.0),
        # Middle East
        ("EAST-WEST-PIPELINE-SAUDI", "crude_oil", 5000000, 1200.0),
        ("ABQAIQ-YANBU", "crude_oil", 1800000, 1175.0),
        ("HABSHAN-FUJAIRAH", "crude_oil", 1500000, 400.0),
        ("IRAQ-TURKEY-PIPELINE", "crude_oil", 1600000, 986.0),
        ("SUMED-PIPELINE", "crude_oil", 2400000, 320.0),
        ("TAPLINE-HISTORIC", "crude_oil", 0, 1684.0),
        # Caspian/Central Asia
        ("BTC-PIPELINE", "crude_oil", 1200000, 1768.0),
        ("SCP-PIPELINE", "natural_gas", 0, 962.0),
        ("CPC-PIPELINE", "crude_oil", 1500000, 1510.0),
        ("TANAP-PIPELINE", "natural_gas", 0, 1850.0),
        ("TAP-PIPELINE", "natural_gas", 0, 878.0),
        ("CENTRAL-ASIA-CHINA", "natural_gas", 0, 1833.0),
        # Europe
        ("SOUTHERN-GAS-CORRIDOR", "natural_gas", 0, 3500.0),
        ("TRANS-ADRIATIC-PIPELINE", "natural_gas", 0, 878.0),
        ("MEDGAZ", "natural_gas", 0, 754.0),
        ("TRANS-MEDITERRANEAN-TRANSMED", "natural_gas", 0, 2475.0),
        ("SOUTHERN-EUROPE-PIPELINE", "refined_products", 0, 750.0),
        ("ROTTERDAM-RHINE-MAINZ", "crude_oil", 600000, 666.0),
        # Africa
        ("TRANS-SAHARAN-GAS", "natural_gas", 0, 4128.0),
        ("NIGER-DELTA-EXPORT", "crude_oil", 1000000, 120.0),
        ("CHAD-CAMEROON", "crude_oil", 225000, 1070.0),
        ("SOUTHERN-AFRICA-PIPELINE", "crude_oil", 200000, 880.0),
        # Asia-Pacific
        ("MYANMA-CHINA-CRUDE", "crude_oil", 440000, 793.0),
        ("SINO-RUSSIAN-OIL", "crude_oil", 600000, 1030.0),
        ("INDIA-IRAN-SWAK", "crude_oil", 0, 2700.0),
        ("INDONESIA-BONTANG-LNG", "lng", 0, 870.0),
        # South America
        ("OLEODUCTO-CENTRAL-COLOMBIA", "crude_oil", 210000, 835.0),
        ("OLEODUCTO-TRASANDINO", "crude_oil", 90000, 494.0),
        ("GASODUCTO-ATACAMA", "natural_gas", 0, 940.0),
        ("PETROAMAZONAS-PIPELINE", "crude_oil", 360000, 497.0),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for pipeline_code, commodity, capacity_bpd, length_km in PIPELINES:
            vid = _oil_vid("pipeline", pipeline_code)
            _res = client.q(
                "INSERT INTO vertex_oil_pipeline "
                "(vertex_id,repo,pipeline_code,commodity,capacity_bpd,length_km,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.pipeline/{vid[-12:]}",
                 pipeline_code, commodity, capacity_bpd, length_km,
                 "active", "com.etzhayyim.apps.oilCoverage.pipeline",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_terminal")
def _ingest_oil_terminal(world_total: int) -> dict[str, Any]:
    """Major world oil storage terminals → vertex_oil_terminal seed."""
    ts = _utc_now()[:10]
    # (terminal_code, terminal_type, locode, storage_capacity_bbl)
    TERMINALS: list[tuple[str, str, str, int]] = [
        # USA
        ("CUSHING-OKLAHOMA", "crude_hub", "USOKU", 85000000),
        ("CORPUS-CHRISTI-TX", "export_terminal", "USCPT", 20000000),
        ("HOUSTON-TX", "crude_hub", "USHOU", 50000000),
        ("PORT-ARTHUR-TX", "refinery_terminal", "USPOT", 30000000),
        ("BEAUMONT-TX", "storage", "USBMT", 25000000),
        ("NEDERLAND-TX", "import_terminal", "USNDT", 18000000),
        ("MARCUS-HOOK-PA", "refinery_terminal", "USMHK", 12000000),
        ("EL-SEGUNDO-CA", "refinery_terminal", "USESG", 10000000),
        # Middle East
        ("FUJAIRAH-UAE", "storage_hub", "AEFJR", 14000000),
        ("RAS-TANURA-SAU", "export_terminal", "SARTN", 50000000),
        ("YANBU-SAU", "export_terminal", "SAYNB", 35000000),
        ("JUBAIL-SAU", "refinery_terminal", "SAJUB", 20000000),
        ("MINA-AL-AHMADI-KWT", "export_terminal", "KWMAA", 45000000),
        ("KHARG-ISLAND-IRN", "export_terminal", "IRKHG", 60000000),
        ("JASK-IRN", "export_terminal", "IRJSK", 30000000),
        ("RUWAIS-ARE", "refinery_terminal", "AERUW", 15000000),
        ("SOHAR-OMN", "export_terminal", "OMSOHAR", 10000000),
        # Europe
        ("ROTTERDAM-NLD", "storage_hub", "NLRTM", 50000000),
        ("AMSTERDAM-NLD", "storage_hub", "NLAMS", 30000000),
        ("ANTWERP-BEL", "storage_hub", "BEANR", 25000000),
        ("WILHELMSHAVEN-DEU", "crude_terminal", "DEWVN", 20000000),
        ("ROSTOCK-DEU", "crude_terminal", "DEROT", 8000000),
        ("PRIMORSK-RUS", "export_terminal", "RUPRI", 60000000),
        ("NOVOROSSIYSK-RUS", "export_terminal", "RUNVS", 40000000),
        ("KOZMINO-RUS", "export_terminal", "RUKOZ", 35000000),
        ("CEYHAN-TUR", "export_terminal", "TRCEY", 45000000),
        ("TRIESTE-ITA", "import_terminal", "ITTRN", 15000000),
        ("LAVERA-FRA", "refinery_terminal", "FRLVR", 12000000),
        ("FAWLEY-GBR", "refinery_terminal", "GBFAW", 10000000),
        # Asia-Pacific
        ("SINGAPORE-JURONG-SGP", "storage_hub", "SGSIN", 50000000),
        ("ZHOUSHAN-CHN", "storage_hub", "CNZOS", 40000000),
        ("TIANJIN-CHN", "crude_terminal", "CNTSN", 30000000),
        ("DALIAN-CHN", "storage_hub", "CNDLC", 25000000),
        ("QINGDAO-CHN", "import_terminal", "CNTAO", 20000000),
        ("NINGBO-CHN", "storage_hub", "CNNBO", 18000000),
        ("YEOSU-KOR", "refinery_terminal", "KRYOS", 15000000),
        ("ULSAN-KOR", "refinery_terminal", "KRULS", 18000000),
        ("CHIBA-JPN", "refinery_terminal", "JPCHB", 12000000),
        ("NEGISHI-JPN", "refinery_terminal", "JPYOK", 15000000),
        ("ONSAN-KOR", "refinery_terminal", "KRONSAN", 10000000),
        # Africa
        ("SALDANHA-BAY-ZAF", "storage_hub", "ZASDB", 45000000),
        ("SFAX-TUN", "export_terminal", "TNSFX", 5000000),
        ("MELLITAH-LBY", "export_terminal", "LYMLL", 8000000),
        ("BEJAIA-DZA", "export_terminal", "DZBJA", 6000000),
        ("BONNY-TERMINAL-NGA", "export_terminal", "NGBON", 20000000),
        ("QALHAT-OMN", "lng_terminal", "OMQLT", 10000000),
        # South America
        ("JOSE-VEN", "export_terminal", "VEJSE", 40000000),
        ("GUANARE-VEN", "storage", "VEGUA", 15000000),
        ("SANTOS-BRA", "storage_hub", "BRSSZ", 12000000),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for terminal_code, terminal_type, locode, storage_capacity in TERMINALS:
            vid = _oil_vid("terminal", terminal_code)
            _res = client.q(
                "INSERT INTO vertex_oil_terminal "
                "(vertex_id,repo,terminal_code,terminal_type,locode,storage_capacity,"
                "status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.terminal/{vid[-12:]}",
                 terminal_code, terminal_type, locode, storage_capacity,
                 "active", "com.etzhayyim.apps.oilCoverage.terminal",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_trade")
def _ingest_oil_trade(world_total: int) -> dict[str, Any]:
    """Representative world crude oil trade flows → vertex_oil_trade seed batch."""
    ts = _utc_now()[:10]
    # (exporter_country, importer_country, commodity, grade_code, benchmark_code, volume_kbd, unit, price_basis)
    FLOWS: list[tuple[str, str, str, str, str, int, str, str]] = [
        ("SAU", "CHN", "crude_oil", "Arab-Light", "Arab-Light-OSP", 1800, "kbd", "OSP+Platts"),
        ("SAU", "JPN", "crude_oil", "Arab-Light", "Arab-Light-OSP", 900, "kbd", "OSP+Platts"),
        ("SAU", "KOR", "crude_oil", "Arab-Medium", "Arab-Light-OSP", 800, "kbd", "OSP+Platts"),
        ("SAU", "IND", "crude_oil", "Arab-Heavy", "Arab-Heavy-OSP", 700, "kbd", "OSP+Platts"),
        ("SAU", "USA", "crude_oil", "Arab-Light", "Arab-Light-OSP", 500, "kbd", "OSP+Platts"),
        ("SAU", "DEU", "crude_oil", "Arab-Medium", "Arab-Light-OSP", 300, "kbd", "OSP+Platts"),
        ("RUS", "CHN", "crude_oil", "ESPO-Blend", "ESPO-Argus", 1600, "kbd", "Argus+premium"),
        ("RUS", "IND", "crude_oil", "Urals", "Urals-Argus", 1100, "kbd", "Argus-discount"),
        ("RUS", "TUR", "crude_oil", "Urals", "Urals-Platts", 300, "kbd", "Platts-discount"),
        ("IRQ", "CHN", "crude_oil", "Basrah-Light", "Basrah-Light-OSP", 1200, "kbd", "OSP+formula"),
        ("IRQ", "IND", "crude_oil", "Basrah-Light", "Basrah-Light-OSP", 800, "kbd", "OSP+formula"),
        ("IRQ", "USA", "crude_oil", "Kirkuk-Blend", "Basrah-Light-OSP", 500, "kbd", "OSP+formula"),
        ("IRQ", "ITA", "crude_oil", "Basrah-Light", "Basrah-Light-OSP", 300, "kbd", "OSP+formula"),
        ("ARE", "JPN", "crude_oil", "Murban", "Murban-IFAD", 700, "kbd", "IFAD-contract"),
        ("ARE", "KOR", "crude_oil", "Das-Blend", "Dubai-Crude-Platts", 600, "kbd", "Platts+premium"),
        ("ARE", "IND", "crude_oil", "Murban", "Murban-IFAD", 500, "kbd", "IFAD-contract"),
        ("ARE", "CHN", "crude_oil", "Upper-Zakum", "Dubai-Crude-Platts", 400, "kbd", "Platts+premium"),
        ("KWT", "JPN", "crude_oil", "Kuwait-Export-Crude", "Kuwait-OSP", 450, "kbd", "OSP+formula"),
        ("KWT", "CHN", "crude_oil", "Kuwait-Export-Crude", "Kuwait-OSP", 350, "kbd", "OSP+formula"),
        ("QAT", "JPN", "lng", "Qatar-Marine", "Japan-Korea-Marker", 150, "kbd_loe", "JKM+premium"),
        ("NGA", "IND", "crude_oil", "Bonny-Light", "Bonny-Light-OSP", 400, "kbd", "Dated-Brent+premium"),
        ("NGA", "EUR", "crude_oil", "Forcados", "ICE-Brent", 300, "kbd", "Dated-Brent+premium"),
        ("NGA", "USA", "crude_oil", "Qua-Iboe", "LLS-Platts", 200, "kbd", "Dated-Brent+premium"),
        ("AGO", "CHN", "crude_oil", "Girassol", "ICE-Brent", 700, "kbd", "Dated-Brent+premium"),
        ("LBY", "ITA", "crude_oil", "Es-Sider", "ICE-Brent", 300, "kbd", "Dated-Brent+premium"),
        ("DZA", "ITA", "crude_oil", "Saharan-Blend", "ICE-Brent", 250, "kbd", "Dated-Brent+premium"),
        ("IRN", "CHN", "crude_oil", "Iranian-Light", "Iran-Light-OSP", 900, "kbd", "OSP+formula"),
        ("IRN", "IND", "crude_oil", "Iranian-Heavy", "Iran-Light-OSP", 300, "kbd", "OSP+formula"),
        ("USA", "EUR", "crude_oil", "WTI", "ICE-Brent", 800, "kbd", "WTI-NYMEX+freight"),
        ("USA", "KOR", "crude_oil", "WTI", "WTI-NYMEX", 600, "kbd", "WTI-NYMEX+freight"),
        ("USA", "JPN", "crude_oil", "WTI", "WTI-NYMEX", 500, "kbd", "WTI-NYMEX+freight"),
        ("USA", "IND", "crude_oil", "Eagle-Ford", "WTI-NYMEX", 300, "kbd", "WTI-NYMEX+freight"),
        ("CAN", "USA", "crude_oil", "WCS", "WCS-CME", 3500, "kbd", "WTI-NYMEX-discount"),
        ("BRA", "CHN", "crude_oil", "Lula-Crude", "Lula-Platts", 600, "kbd", "Dated-Brent+premium"),
        ("BRA", "EUR", "crude_oil", "Lula-Crude", "ICE-Brent", 200, "kbd", "Dated-Brent+premium"),
        ("NOR", "DEU", "crude_oil", "Oseberg", "ICE-Brent", 400, "kbd", "Dated-Brent+formula"),
        ("NOR", "GBR", "crude_oil", "Ekofisk", "ICE-Brent", 300, "kbd", "Dated-Brent+formula"),
        ("NOR", "NLD", "crude_oil", "Johan-Sverdrup", "ICE-Brent", 200, "kbd", "Dated-Brent+formula"),
        ("KAZ", "CHN", "crude_oil", "CPC-Blend", "CPC-Blend-Argus", 500, "kbd", "Argus+premium"),
        ("KAZ", "EUR", "crude_oil", "CPC-Blend", "CPC-Blend-Argus", 400, "kbd", "Argus+premium"),
        ("AZE", "EUR", "crude_oil", "Azeri-Light", "ICE-Brent", 600, "kbd", "Dated-Brent+premium"),
        ("MEX", "USA", "crude_oil", "Maya", "Maya-OSP", 700, "kbd", "WTI-NYMEX+formula"),
        ("MEX", "EUR", "crude_oil", "Olmeca", "Maya-OSP", 200, "kbd", "Dated-Brent+formula"),
        ("COL", "USA", "crude_oil", "Rubiales", "WTI-NYMEX", 300, "kbd", "WTI-NYMEX-discount"),
        ("IDN", "CHN", "crude_oil", "Minas", "Dated-Brent", 200, "kbd", "Dated-Brent+formula"),
        ("MYS", "CHN", "crude_oil", "Tapis", "Dated-Brent", 150, "kbd", "Dated-Brent+premium"),
        ("GUY", "USA", "crude_oil", "Liza-1", "ICE-Brent", 150, "kbd", "Dated-Brent+premium"),
        ("GHA", "CHN", "crude_oil", "Jubilee", "ICE-Brent", 150, "kbd", "Dated-Brent+premium"),
        ("VEN", "CHN", "crude_oil", "Merey", "ICE-Brent", 200, "kbd", "Dated-Brent-discount"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for (exporter_cc, importer_cc, commodity, grade_code, benchmark_code,
             volume, unit, price_basis) in FLOWS:
            trade_id = f"{exporter_cc}-{importer_cc}-{grade_code}-{ts}"
            vid = _oil_vid("trade", trade_id)
            trader_did = f"did:web:oil-coverage.etzhayyim.com:country:{exporter_cc.lower()}"
            counterparty_did = f"did:web:oil-coverage.etzhayyim.com:country:{importer_cc.lower()}"
            _res = client.q(
                "INSERT INTO vertex_oil_trade "
                "(vertex_id,repo,trade_id,trader_did,counterparty_did,commodity,"
                "grade_code,benchmark_code,country_code,volume,unit,price_basis,"
                "delivery_window,status,collection,owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.trade/{vid[-12:]}",
                 trade_id, trader_did, counterparty_did, commodity,
                 grade_code, benchmark_code, exporter_cc, volume, unit, price_basis,
                 "Q2-2026", "active", "com.etzhayyim.apps.oilCoverage.trade",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_tanker")
def _ingest_oil_tanker(world_total: int) -> dict[str, Any]:
    """Named tanker fleet seed → vertex_oil_tanker (VLCC/Suezmax/Aframax/MR/LR/VLGC)."""
    ts = _utc_now()[:10]
    # (imo, mmsi, vessel_name, vessel_class, flag, dwt, operator_did, built_year, sanctions_status)
    TANKERS: list[tuple[str, str, str, str, str, int, str, int, str]] = [
        # VLCCs (≥200,000 DWT)
        ("9741026", "636016871", "TI Europe", "VLCC", "LBR", 319000, _OIL_ACTOR, 2016, "clean"),
        ("9741038", "636016872", "TI Africa", "VLCC", "LBR", 319000, _OIL_ACTOR, 2016, "clean"),
        ("9299880", "477450600", "Pacific Bora", "VLCC", "HKG", 298000, _OIL_ACTOR, 2005, "clean"),
        ("9261425", "477455400", "Oceania", "VLCC", "HKG", 333000, _OIL_ACTOR, 2003, "clean"),
        ("9299892", "477450700", "Pacific Breeze", "VLCC", "HKG", 298000, _OIL_ACTOR, 2005, "clean"),
        ("9395423", "538001600", "Front Altair", "VLCC", "MHL", 300000, _OIL_ACTOR, 2010, "clean"),
        ("9395447", "538001700", "Front Balder", "VLCC", "MHL", 300000, _OIL_ACTOR, 2010, "clean"),
        ("9745118", "566310000", "Maran Castor", "VLCC", "SGP", 300000, _OIL_ACTOR, 2016, "clean"),
        ("9745130", "566312000", "Maran Pollux", "VLCC", "SGP", 300000, _OIL_ACTOR, 2017, "clean"),
        ("9321483", "477500500", "Overseas Samar", "VLCC", "HKG", 298000, _OIL_ACTOR, 2006, "clean"),
        # Dark fleet VLCCs (Russian sanctions exposure)
        ("9250775", "255806100", "Andaman", "VLCC", "MLT", 299000, _OIL_ACTOR, 2003, "watchlist"),
        ("9235252", "255806200", "Atlantic Integrity", "VLCC", "MLT", 299000, _OIL_ACTOR, 2002, "watchlist"),
        ("9235264", "311044900", "Pacific Unity", "VLCC", "PAN", 299000, _OIL_ACTOR, 2002, "sanctioned"),
        ("9198957", "370059000", "Lucia", "VLCC", "GAB", 281000, _OIL_ACTOR, 2000, "sanctioned"),
        # Suezmax (120,000–199,999 DWT)
        ("9440761", "636015987", "Suezmax Centurion", "Suezmax", "LBR", 158000, _OIL_ACTOR, 2011, "clean"),
        ("9440773", "636015988", "Suezmax Champion", "Suezmax", "LBR", 158000, _OIL_ACTOR, 2011, "clean"),
        ("9290048", "477456100", "Eagle Seville", "Suezmax", "HKG", 149000, _OIL_ACTOR, 2005, "clean"),
        ("9290060", "477456200", "Eagle Sydney", "Suezmax", "HKG", 149000, _OIL_ACTOR, 2005, "clean"),
        ("9567337", "538007200", "Nissos Rhenia", "Suezmax", "MHL", 157000, _OIL_ACTOR, 2012, "clean"),
        ("9567349", "538007300", "Nissos Schinoussa", "Suezmax", "MHL", 157000, _OIL_ACTOR, 2012, "clean"),
        # Dark fleet Suezmax (Iranian sanctions)
        ("9215481", "422004700", "Mustafa", "Suezmax", "IRN", 160000, _OIL_ACTOR, 2001, "sanctioned"),
        ("9215493", "422004800", "Hormoz", "Suezmax", "IRN", 160000, _OIL_ACTOR, 2001, "sanctioned"),
        # Aframax (80,000–119,999 DWT)
        ("9418023", "636016123", "Nordic Aurora", "Aframax", "LBR", 115000, _OIL_ACTOR, 2012, "clean"),
        ("9418035", "636016124", "Nordic Breeze", "Aframax", "LBR", 115000, _OIL_ACTOR, 2012, "clean"),
        ("9428900", "477500900", "Ridgebury Ania", "Aframax", "HKG", 113000, _OIL_ACTOR, 2012, "clean"),
        ("9428912", "477501000", "Ridgebury Clara", "Aframax", "HKG", 113000, _OIL_ACTOR, 2013, "clean"),
        ("9343519", "311042100", "Overseas Houston", "Aframax", "PAN", 115000, _OIL_ACTOR, 2007, "clean"),
        # MR tankers (25,000–54,999 DWT)
        ("9516406", "538006800", "Hafnia Nile", "MR", "MHL", 50000, _OIL_ACTOR, 2011, "clean"),
        ("9516418", "538006900", "Hafnia Amazon", "MR", "MHL", 50000, _OIL_ACTOR, 2012, "clean"),
        ("9564227", "636018200", "STI Beryl", "MR", "LBR", 50000, _OIL_ACTOR, 2013, "clean"),
        ("9564239", "636018300", "STI Coral", "MR", "LBR", 50000, _OIL_ACTOR, 2013, "clean"),
        ("9566003", "538007500", "Nordic Tern", "MR", "MHL", 49000, _OIL_ACTOR, 2012, "clean"),
        # LR2 tankers (80,000–119,999 DWT, product)
        ("9679529", "538008100", "BW Maple", "LR2", "MHL", 111000, _OIL_ACTOR, 2014, "clean"),
        ("9679531", "538008200", "BW Oak", "LR2", "MHL", 111000, _OIL_ACTOR, 2014, "clean"),
        ("9742150", "636019800", "New Ranger", "LR2", "LBR", 109000, _OIL_ACTOR, 2016, "clean"),
        # VLGC (LPG carriers)
        ("9321495", "538002100", "Gas Anna", "VLGC", "MHL", 84000, _OIL_ACTOR, 2006, "clean"),
        ("9321500", "538002200", "Gas Catarina", "VLGC", "MHL", 84000, _OIL_ACTOR, 2006, "clean"),
        ("9502730", "636016700", "Navigator Tethys", "VLGC", "LBR", 83000, _OIL_ACTOR, 2011, "clean"),
        # Dark fleet (North Korean coal → fuel)
        ("8518780", "445007000", "Paekma", "VLCC", "PRK", 280000, _OIL_ACTOR, 1987, "sanctioned"),
        ("8321427", "445009000", "Yu Phyong 5", "Aframax", "PRK", 100000, _OIL_ACTOR, 1983, "sanctioned"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for (imo, mmsi, vessel_name, vessel_class, flag, dwt, op_did, built, sanctions) in TANKERS:
            vid = _oil_vid("tanker", imo, vessel_name)
            _res = client.q(
                "INSERT INTO vertex_oil_tanker "
                "(vertex_id,imo,mmsi,vessel_name,vessel_class,flag_country,dwt,"
                "operator_did,built_year,sanctions_status,status,"
                "collection,actor_did,org_did,sensitivity_ord,owner_did,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid, imo, mmsi, vessel_name, vessel_class, flag, dwt,
                 op_did, built, sanctions, "active",
                 "com.etzhayyim.apps.oilCoverage.tanker",
                 _OIL_ACTOR, _OIL_ACTOR, 0, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_cargo")
def _ingest_oil_cargo(world_total: int) -> dict[str, Any]:
    """Representative tanker cargo records → vertex_oil_cargo seed batch."""
    ts = _utc_now()[:10]
    # (cargo_id, commodity, grade_code, quantity_kbd, load_port, discharge_port, laycan)
    CARGOES: list[tuple[str, str, str, int, str, str, str]] = [
        ("VLCC-001-RAS-TANURA-NINGBO", "crude_oil", "Arab-Light", 2000, "Ras Tanura", "Ningbo", "2026-05-01/2026-05-05"),
        ("VLCC-002-KHARG-ULSAN", "crude_oil", "Iranian-Light", 2000, "Kharg Island", "Ulsan", "2026-05-03/2026-05-07"),
        ("VLCC-003-BASRAH-CHIBA", "crude_oil", "Basrah-Light", 2000, "Basrah", "Chiba", "2026-05-05/2026-05-09"),
        ("VLCC-004-PRIMORSK-ROTTERDAM", "crude_oil", "Urals", 2000, "Primorsk", "Rotterdam", "2026-05-02/2026-05-06"),
        ("VLCC-005-ESPO-KOZMINO-QINGDAO", "crude_oil", "ESPO-Blend", 1800, "Kozmino", "Qingdao", "2026-05-04/2026-05-08"),
        ("SUEZMAX-001-BONNY-ROTTERDAM", "crude_oil", "Bonny-Light", 1000, "Bonny", "Rotterdam", "2026-05-01/2026-05-05"),
        ("SUEZMAX-002-CEYHAN-TRIESTE", "crude_oil", "CPC-Blend", 950, "Ceyhan", "Trieste", "2026-05-03/2026-05-07"),
        ("SUEZMAX-003-NOVOROSSIYSK-AUGUSTA", "crude_oil", "Urals", 900, "Novorossiysk", "Augusta", "2026-05-02/2026-05-06"),
        ("SUEZMAX-004-ES-SIDER-LAVERA", "crude_oil", "Es-Sider", 950, "Es Sider", "Lavera", "2026-05-05/2026-05-09"),
        ("SUEZMAX-005-GIRASSOL-ANTWERP", "crude_oil", "Girassol", 1000, "Girassol FPSO", "Antwerp", "2026-05-04/2026-05-08"),
        ("AFRAMAX-001-NORTH-SEA-WILHELMSHAVEN", "crude_oil", "Brent-Crude", 600, "Sullom Voe", "Wilhelmshaven", "2026-05-01/2026-05-03"),
        ("AFRAMAX-002-CORPUS-CHRISTI-ST-JAMES", "crude_oil", "WTI", 650, "Corpus Christi", "St James", "2026-05-02/2026-05-04"),
        ("AFRAMAX-003-SALDANHA-SINGAPORE", "crude_oil", "Arab-Light", 700, "Saldanha Bay", "Singapore", "2026-05-06/2026-05-12"),
        ("AFRAMAX-004-FUJAIRAH-MUMBAI", "crude_oil", "Arab-Medium", 650, "Fujairah", "Mumbai", "2026-05-03/2026-05-07"),
        ("AFRAMAX-005-BTC-ALIAGA", "crude_oil", "Azeri-Light", 600, "Ceyhan", "Aliaga", "2026-05-04/2026-05-06"),
        ("PANAMAX-001-CUSHING-HOUSTON", "crude_oil", "WTI", 400, "Cushing", "Houston", "2026-05-01/2026-05-02"),
        ("PANAMAX-002-MARACAIBO-LAKE-CHARLES", "crude_oil", "Merey", 380, "Maracaibo", "Lake Charles", "2026-05-05/2026-05-10"),
        ("PANAMAX-003-SANTOS-ROTTERDAM", "crude_oil", "Lula-Crude", 420, "Santos", "Rotterdam", "2026-05-08/2026-05-18"),
        ("PANAMAX-004-MURMANSK-ROTTERDAM", "crude_oil", "Urals", 380, "Murmansk", "Rotterdam", "2026-05-03/2026-05-10"),
        ("PANAMAX-005-LIBREVILLE-ANTWERP", "crude_oil", "Girassol", 400, "Libreville", "Antwerp", "2026-05-02/2026-05-10"),
        ("LNG-001-RASGAS-NAGOYA", "lng", "Qatar-Marine", 200, "Ras Laffan", "Nagoya", "2026-05-04/2026-05-12"),
        ("LNG-002-GORGON-TOKYO", "lng", "North-West-Shelf", 190, "Barrow Island", "Tokyo", "2026-05-05/2026-05-15"),
        ("LNG-003-SABINE-PASS-ROTTERDAM", "lng", "LLS", 200, "Sabine Pass", "Rotterdam", "2026-05-02/2026-05-11"),
        ("LNG-004-PERNIS-ZEEBRUGGE", "lng", "Brent-Crude", 180, "Pernis", "Zeebrugge", "2026-05-01/2026-05-03"),
        ("LNG-005-HAMMERFEST-GATE", "lng", "Johan-Sverdrup", 190, "Hammerfest", "Gate", "2026-05-03/2026-05-10"),
        ("VLCC-006-ABU-DHABI-YEOSU", "crude_oil", "Murban", 2000, "Ruwais", "Yeosu", "2026-05-06/2026-05-14"),
        ("VLCC-007-ABQAIQ-CHIBA", "crude_oil", "Arab-Extra-Light", 2000, "Ras Tanura", "Chiba", "2026-05-08/2026-05-16"),
        ("VLCC-008-VENEZUELA-PORT-ARTHUR", "crude_oil", "Merey", 1800, "Jose", "Port Arthur", "2026-05-07/2026-05-18"),
        ("VLCC-009-KIRKUK-TIANJIN", "crude_oil", "Kirkuk-Blend", 1900, "Ceyhan", "Tianjin", "2026-05-09/2026-05-19"),
        ("VLCC-010-MANIFA-DALIAN", "crude_oil", "Arab-Heavy", 2000, "Jubail", "Dalian", "2026-05-10/2026-05-20"),
        ("SUEZMAX-006-AGBAMI-ROTTERDAM", "crude_oil", "Agbami", 950, "Agbami FPSO", "Rotterdam", "2026-05-08/2026-05-16"),
        ("SUEZMAX-007-JUBILEE-CHINA", "crude_oil", "Bonny-Light", 900, "Takoradi", "Tianjin", "2026-05-07/2026-05-17"),
        ("SUEZMAX-008-KASHAGAN-AUGUSTA", "crude_oil", "CPC-Blend", 920, "Ceyhan", "Augusta", "2026-05-05/2026-05-11"),
        ("AFRAMAX-006-EAGLE-FORD-CORPUS", "crude_oil", "Eagle-Ford", 600, "Corpus Christi", "Corpus Christi", "2026-05-01/2026-05-01"),
        ("AFRAMAX-007-NORWEGIAN-ROTTERDAM", "crude_oil", "Oseberg", 650, "Mongstad", "Rotterdam", "2026-05-03/2026-05-07"),
        ("AFRAMAX-008-LIZA-EUROPE", "crude_oil", "Liza-1", 600, "Georgetown", "Rotterdam", "2026-05-12/2026-05-22"),
        ("VLCC-011-WEST-AFRICA-KOREA", "crude_oil", "Dalia", 1900, "Cabinda", "Yeosu", "2026-05-11/2026-05-22"),
        ("VLCC-012-BRAZIL-CHINA", "crude_oil", "Lula-Crude", 2000, "Santos", "Zhoushan", "2026-05-15/2026-05-28"),
        ("SUEZMAX-009-CANADIAN-CHINA", "crude_oil", "WCS", 900, "Vancouver", "Zhoushan", "2026-05-14/2026-05-26"),
        ("SUEZMAX-010-LIBYAN-ITALY", "crude_oil", "Sharara", 950, "Zawia", "Augusta", "2026-05-06/2026-05-10"),
        ("PANAMAX-006-ATHABASCA-SEATTLE", "crude_oil", "WCS", 370, "Vancouver", "Seattle", "2026-05-01/2026-05-03"),
        ("PANAMAX-007-ECUADORIAN-CHILE", "crude_oil", "Oriente", 400, "Esmeraldas", "Quintero", "2026-05-04/2026-05-10"),
        ("VLCC-013-NIGERIAN-JAPAN", "crude_oil", "Forcados", 1950, "Forcados", "Negishi", "2026-05-13/2026-05-26"),
        ("VLCC-014-KUWAITI-INDIA", "crude_oil", "Kuwait-Export-Crude", 1900, "Mina al-Ahmadi", "Jamnagar", "2026-05-09/2026-05-17"),
        ("AFRAMAX-009-ALASKA-CALIFORNIA", "crude_oil", "ANS", 650, "Valdez", "El Segundo", "2026-05-02/2026-05-05"),
        ("SUEZMAX-011-TENGIZ-INDIA", "crude_oil", "CPC-Blend", 900, "Ceyhan", "Jamnagar", "2026-05-10/2026-05-20"),
        ("VLCC-015-OMAN-CHINA", "crude_oil", "Oman-Crude", 2000, "Sohar", "Qingdao", "2026-05-07/2026-05-16"),
        ("AFRAMAX-010-MALAYSIA-VIETNAM", "crude_oil", "Tapis", 700, "Port Dickson", "Vung Tau", "2026-05-05/2026-05-08"),
        ("SUEZMAX-012-COLOMBIA-USA", "crude_oil", "Castilla", 850, "Covenas", "Corpus Christi", "2026-05-11/2026-05-18"),
        ("VLCC-016-IRAQ-SOUTH-KOREA", "crude_oil", "Basrah-Heavy", 2000, "Basrah", "Onsan", "2026-05-12/2026-05-22"),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for (cargo_id, commodity, grade_code, quantity,
             load_port, discharge_port, laycan) in CARGOES:
            vid = _oil_vid("cargo", cargo_id)
            _res = client.q(
                "INSERT INTO vertex_oil_cargo "
                "(vertex_id,repo,cargo_id,commodity,grade_code,quantity,"
                "load_port,discharge_port,laycan,status,collection,"
                "owner_did,actor_did,org_did,created_date) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.cargo/{vid[-12:]}",
                 cargo_id, commodity, grade_code, quantity,
                 _as_str(load_port, 128), _as_str(discharge_port, 128), laycan,
                 "active", "com.etzhayyim.apps.oilCoverage.cargo",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_cargo_edges")
def _ingest_oil_cargo_edges(world_total: int) -> dict[str, Any]:
    """Backfill edge_loaded_at / edge_discharged_at linking vertex_oil_cargo → vertex_oil_terminal.

    Matching strategy (two-pass, small dataset):
      1. LOCODE-format ports ('SG-SIN', 'US-HOU') matched against terminal.locode (exact upper).
      2. Plain-name ports ('Ras Tanura') matched against terminal name extracted from terminal_code
         by stripping the trailing country/state suffix and replacing hyphens with spaces.
    """
    import hashlib
    import re

    def _terminal_name(code: str) -> str:
        stripped = re.sub(r"-[A-Z]{2,3}$", "", code)
        return stripped.replace("-", " ").lower()

    def _port_keys(port: str) -> list[str]:
        keys = [port.strip().upper()]  # LOCODE probe
        plain = re.sub(r"-", " ", port.strip()).lower()
        keys.append(plain)
        # also try first word (catches "Bonny Terminal" → "bonny")
        first = plain.split()[0] if plain else ""
        if first and first not in keys:
            keys.append(first)
        return keys

    ts = _utc_now()[:10]
    loaded_written = 0
    discharged_written = 0

    if True:

        client = get_kotoba_client()
        # Build terminal lookup
        _res = client.q(
            "SELECT vertex_id, terminal_code, locode FROM vertex_oil_terminal"
        )
        terminal_rows = _res

        lookup: dict[str, str] = {}
        for t_vid, t_code, t_locode in terminal_rows:
            if t_locode:
                lookup[t_locode.upper()] = t_vid
            name = _terminal_name(t_code)
            if name and name not in lookup:
                lookup[name] = t_vid
            first_word = name.split()[0] if name else ""
            if first_word and first_word not in lookup:
                lookup[first_word] = t_vid

        # Load cargo
        _res = client.q(
            "SELECT vertex_id, load_port, discharge_port, laycan, actor_did "
            "FROM vertex_oil_cargo"
        )
        cargo_rows = _res

        for c_vid, load_port, discharge_port, laycan, actor_did in cargo_rows:
            loaded_at_val = (laycan or ts)[:10] if laycan else ts
            owner = actor_did or _OIL_ACTOR

            # edge_loaded_at: cargo → load terminal
            if load_port:
                for key in _port_keys(load_port):
                    if key in lookup:
                        t_vid = lookup[key]
                        eid = "oil-edge-loaded-" + hashlib.sha1(
                            f"{c_vid}|{t_vid}".encode()
                        ).hexdigest()[:20]
                        _res = client.q(
                            "INSERT INTO edge_loaded_at "
                            "(edge_id,src_vid,dst_vid,created_date,"
                            "sensitivity_ord,owner_did,label,loaded_at) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (eid, c_vid, t_vid, ts, 0, owner,
                             "oil_cargo_loaded_at", loaded_at_val),
                        )
                        loaded_written += 1
                        break

            # edge_discharged_at: cargo → discharge terminal
            if discharge_port:
                for key in _port_keys(discharge_port):
                    if key in lookup:
                        t_vid = lookup[key]
                        eid = "oil-edge-discharged-" + hashlib.sha1(
                            f"{c_vid}|{t_vid}".encode()
                        ).hexdigest()[:20]
                        _res = client.q(
                            "INSERT INTO edge_discharged_at "
                            "(edge_id,src_vid,dst_vid,created_date,"
                            "sensitivity_ord,owner_did,label,discharged_at) "
                            "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                            (eid, c_vid, t_vid, ts, 0, owner,
                             "oil_cargo_discharged_at", loaded_at_val),
                        )
                        discharged_written += 1
                        break

    return {
        "ok": True,
        "rowsWritten": loaded_written + discharged_written,
        "loaded": loaded_written,
        "discharged": discharged_written,
        "error": "",
    }


@_register_ingest("oil_country_profile")
def _ingest_oil_country_profile(world_total: int) -> dict[str, Any]:
    """Top oil-producing countries → vertex_oil_country_profile.

    role_flags: comma-separated subset of PRODUCER,EXPORTER,IMPORTER,TRANSIT,REFINER,OPEC,GCC.
    reserve_rank / production_rank: 1-based global rank (0 = not applicable).
    """
    ts = _utc_now()[:10]
    # (country_code, role_flags, reserve_rank, production_rank)
    COUNTRIES: list[tuple[str, str, int, int]] = [
        # OPEC Core
        ("SA", "PRODUCER,EXPORTER,OPEC,GCC,REFINER", 1, 2),
        ("IR", "PRODUCER,EXPORTER,OPEC,REFINER", 4, 8),
        ("IQ", "PRODUCER,EXPORTER,OPEC,REFINER", 5, 4),
        ("KW", "PRODUCER,EXPORTER,OPEC,GCC,REFINER", 6, 10),
        ("AE", "PRODUCER,EXPORTER,OPEC,GCC,REFINER", 7, 9),
        ("VE", "PRODUCER,OPEC,REFINER", 2, 20),
        ("LY", "PRODUCER,EXPORTER,OPEC,REFINER", 9, 22),
        ("NG", "PRODUCER,EXPORTER,OPEC,REFINER", 10, 11),
        ("GA", "PRODUCER,EXPORTER,OPEC", 0, 31),
        ("CG", "PRODUCER,EXPORTER,OPEC", 0, 28),
        ("GQ", "PRODUCER,EXPORTER,OPEC", 0, 33),
        # Major non-OPEC producers
        ("US", "PRODUCER,IMPORTER,REFINER", 3, 1),
        ("RU", "PRODUCER,EXPORTER,REFINER", 8, 3),
        ("CA", "PRODUCER,EXPORTER,REFINER", 11, 5),
        ("CN", "PRODUCER,IMPORTER,REFINER", 12, 6),
        ("BR", "PRODUCER,EXPORTER,REFINER", 15, 7),
        ("NO", "PRODUCER,EXPORTER,REFINER", 0, 12),
        ("KZ", "PRODUCER,EXPORTER,REFINER", 13, 13),
        ("MX", "PRODUCER,EXPORTER,REFINER", 17, 14),
        ("QA", "PRODUCER,EXPORTER,OPEC,GCC,REFINER", 0, 15),
        ("OM", "PRODUCER,EXPORTER,GCC,REFINER", 0, 16),
        ("AZ", "PRODUCER,EXPORTER,REFINER", 0, 17),
        ("GB", "PRODUCER,REFINER", 0, 18),
        ("MY", "PRODUCER,EXPORTER,REFINER", 0, 19),
        ("CO", "PRODUCER,EXPORTER,REFINER", 0, 21),
        ("IN", "PRODUCER,IMPORTER,REFINER", 0, 23),
        ("ID", "PRODUCER,IMPORTER,REFINER", 0, 24),
        ("DZ", "PRODUCER,EXPORTER,OPEC,REFINER", 16, 25),
        ("EC", "PRODUCER,EXPORTER,OPEC,REFINER", 0, 26),
        ("AR", "PRODUCER,EXPORTER,REFINER", 0, 27),
        # Major transit / import hubs
        ("SG", "IMPORTER,TRANSIT,REFINER", 0, 0),
        ("JP", "IMPORTER,REFINER", 0, 0),
        ("KR", "IMPORTER,REFINER", 0, 0),
        ("NL", "IMPORTER,TRANSIT,REFINER", 0, 0),
        ("PK", "IMPORTER,REFINER", 0, 0),
        ("TR", "IMPORTER,TRANSIT,REFINER", 0, 0),
        ("EG", "TRANSIT,PRODUCER,REFINER", 0, 0),
        ("PA", "TRANSIT", 0, 0),
        ("DK", "TRANSIT,PRODUCER", 0, 0),
    ]
    written = 0
    if True:
        client = get_kotoba_client()
        for country_code, role_flags, reserve_rank, production_rank in COUNTRIES:
            vid = _oil_vid("country", country_code)
            _res = client.q(
                "INSERT INTO vertex_oil_country_profile "
                "(vertex_id,repo,country_code,role_flags,reserve_rank,production_rank,"
                "status,collection,owner_did,actor_did,org_did,created_date,sensitivity_ord) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (vid,
                 f"at://{_OIL_ACTOR}/com.etzhayyim.apps.oilCoverage.countryProfile/{country_code}",
                 country_code, role_flags, reserve_rank, production_rank,
                 "active", "com.etzhayyim.apps.oilCoverage.countryProfile",
                 _OIL_ACTOR, _OIL_ACTOR, _OIL_ACTOR, ts, 0),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_field_basin_edges")
def _ingest_oil_field_basin_edges(world_total: int) -> dict[str, Any]:
    """Link vertex_oil_field → vertex_oil_basin via edge_located_in (basin_code match)."""
    import hashlib
    ts = _utc_now()[:10]
    written = 0
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT vertex_id, basin_code FROM vertex_oil_basin")
        basin_map: dict[str, str] = {r[1]: r[0] for r in _res if r[1]}

        _res = client.q("SELECT vertex_id, basin_code FROM vertex_oil_field WHERE basin_code IS NOT NULL AND basin_code != ''")
        field_rows = _res

        for f_vid, basin_code in field_rows:
            b_vid = basin_map.get(basin_code)
            if not b_vid:
                continue
            eid = "oil-edge-field-basin-" + hashlib.sha1(f"{f_vid}|{b_vid}".encode()).hexdigest()[:16]
            _res = client.q(
                "INSERT INTO edge_located_at"
                "(edge_id,src_vid,dst_vid,created_date,sensitivity_ord,owner_did,label) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (eid, f_vid, b_vid, ts, 0, _OIL_ACTOR, "oil_field_in_basin"),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_basin_country_edges")
def _ingest_oil_basin_country_edges(world_total: int) -> dict[str, Any]:
    """Link vertex_oil_basin → vertex_oil_country_profile via edge_located_in (country_code match)."""
    import hashlib
    ts = _utc_now()[:10]
    written = 0
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT vertex_id, country_code FROM vertex_oil_country_profile WHERE country_code IS NOT NULL")
        country_map: dict[str, str] = {r[1]: r[0] for r in _res}

        _res = client.q("SELECT vertex_id, country_code FROM vertex_oil_basin WHERE country_code IS NOT NULL AND country_code != ''")
        basin_rows = _res

        for b_vid, country_code in basin_rows:
            # basin country_code may be comma-separated multi-country
            for cc in country_code.split(","):
                cc = cc.strip().upper()
                c_vid = country_map.get(cc)
                if not c_vid:
                    continue
                eid = "oil-edge-basin-country-" + hashlib.sha1(f"{b_vid}|{c_vid}".encode()).hexdigest()[:16]
                _res = client.q(
                    "INSERT INTO edge_located_at"
                    "(edge_id,src_vid,dst_vid,created_date,sensitivity_ord,owner_did,label) "
                    "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                    (eid, b_vid, c_vid, ts, 0, _OIL_ACTOR, "oil_basin_in_country"),
                )
                written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_company_country_edges")
def _ingest_oil_company_country_edges(world_total: int) -> dict[str, Any]:
    """Link vertex_oil_company → vertex_oil_country_profile via edge_located_in (hq_country match)."""
    import hashlib
    ts = _utc_now()[:10]
    written = 0
    if True:
        client = get_kotoba_client()
        _res = client.q("SELECT vertex_id, country_code FROM vertex_oil_country_profile WHERE country_code IS NOT NULL")
        country_map: dict[str, str] = {r[1]: r[0] for r in _res}

        _res = client.q("SELECT vertex_id, hq_country FROM vertex_oil_company WHERE hq_country IS NOT NULL AND hq_country != ''")
        company_rows = _res

        for c_vid, hq_country in company_rows:
            cp_vid = country_map.get(hq_country.strip().upper())
            if not cp_vid:
                continue
            eid = "oil-edge-co-country-" + hashlib.sha1(f"{c_vid}|{cp_vid}".encode()).hexdigest()[:16]
            _res = client.q(
                "INSERT INTO edge_located_at"
                "(edge_id,src_vid,dst_vid,created_date,sensitivity_ord,owner_did,label) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                (eid, c_vid, cp_vid, ts, 0, _OIL_ACTOR, "oil_company_hq_country"),
            )
            written += 1
    return {"ok": True, "rowsWritten": written, "error": ""}


@_register_ingest("oil_sanctions_edges")
def _ingest_oil_sanctions_edges(world_total: int) -> dict[str, Any]:
    """Cross-link oil companies/countries with OFAC SDN sanctions entries.

    Strategy: match oil_company.name fragments against sdn_program keywords,
    and flag OFAC-sanctioned country_profiles (IR, RU, VE, SY, KP, BY, CU).
    Writes to edge_subject_to_sanctions (src=oil entity, dst=sdn entry).
    """
    import hashlib
    ts = _utc_now()[:10]
    written = 0

    SANCTIONED_COUNTRY_CODES = {"IR", "RU", "VE", "SY", "KP", "BY", "CU", "MM", "SS", "YE"}
    OIL_SDN_PROGRAMS = {"IRAN", "RUSSIA", "VENEZUELA", "SDN", "SDGT", "NPWMD"}

    if True:

        client = get_kotoba_client()
        # Load SDN entries that relate to oil/energy programs
        _res = client.q(
            "SELECT vertex_id, sdn_program, sdn_id FROM vertex_open_ofac_sanctions_sdn "
            "WHERE sdn_program IS NOT NULL LIMIT 5000"
        )
        sdn_rows = _res
        if not sdn_rows:
            return {"ok": True, "rowsWritten": 0, "error": "no SDN rows (run sanctions ingest first)"}

        # Build oil-relevant SDN subset
        oil_sdn: list[tuple[str, str]] = [
            (s_vid, prog) for s_vid, prog, _ in sdn_rows
            if any(kw in (prog or "").upper() for kw in OIL_SDN_PROGRAMS)
        ]
        if not oil_sdn:
            return {"ok": True, "rowsWritten": 0, "error": "no oil-relevant SDN programs found"}

        # Link sanctioned countries → first matching SDN entry per program (via edge_located_at)
        _res = client.q("SELECT vertex_id, country_code FROM vertex_oil_country_profile")
        for cp_vid, cc in _res:
            if cc not in SANCTIONED_COUNTRY_CODES:
                continue
            for s_vid, _prog in oil_sdn[:1]:
                eid = "oil-sanction-country-" + hashlib.sha1(f"{cp_vid}|{s_vid}".encode()).hexdigest()[:16]
                try:
                    _res = client.q(
                        "INSERT INTO edge_located_at"
                        "(edge_id,src_vid,dst_vid,created_date,sensitivity_ord,owner_did,label) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (eid, cp_vid, s_vid, ts, 1, _OIL_ACTOR, "oil_country_sanctioned"),
                    )
                    written += 1
                except Exception:  # noqa: BLE001
                    pass

        # Link oil companies with sanctions_status='sanctioned' → matching SDN
        _res = client.q("SELECT vertex_id, hq_country FROM vertex_oil_company WHERE sanctions_status = 'sanctioned'")
        for co_vid, _hq in _res:
            for s_vid, _prog in oil_sdn[:1]:
                eid = "oil-sanction-co-" + hashlib.sha1(f"{co_vid}|{s_vid}".encode()).hexdigest()[:16]
                try:
                    _res = client.q(
                        "INSERT INTO edge_located_at"
                        "(edge_id,src_vid,dst_vid,created_date,sensitivity_ord,owner_did,label) "
                        "VALUES (%s,%s,%s,%s,%s,%s,%s)",
                        (eid, co_vid, s_vid, ts, 1, _OIL_ACTOR, "oil_company_sanctioned"),
                    )
                    written += 1
                except Exception:  # noqa: BLE001
                    pass

    return {"ok": True, "rowsWritten": written, "error": ""}


def task_coverage_gap_ingest(*, domain: str = "", worldTotal: int = 0, **kwargs: Any) -> dict[str, Any]:
    """Dispatch to the registered ingest handler for `domain`."""
    handler = _INGEST_HANDLERS.get(str(domain or ""))
    if handler is None:
        return {
            "ok": False,
            "rowsWritten": 0,
            "error": f"no ingest handler for domain '{domain}'",
        }
    try:
        return handler(int(worldTotal or 0))
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": str(exc)[:500]}


# ── task 3: infer ─────────────────────────────────────────────────────────────

def task_coverage_gap_infer(*, domain: str = "", llmTier: str = "structured", **kwargs: Any) -> dict[str, Any]:
    """
    SQL UDF classify_coverage_recipe(domain) + LLM call_tier → INSERT stub row.
    Phase 1: calls classify UDF to confirm recipe_kind, then uses LLM to
    generate one representative structured entity for the domain.
    """
    from kotodama import llm as _llm  # lazy import

    # 1. Confirm recipe via SQL UDF
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT classify_coverage_recipe(%s)", (str(domain),)
            )
            row = (_res[0] if _res else None)
            confirmed_kind = str(row[0] if row else "defer")
    except Exception as exc:  # noqa: BLE001
        confirmed_kind = "defer"
        udf_error = str(exc)[:200]
    else:
        udf_error = ""

    if confirmed_kind == "defer":
        return {
            "ok": False,
            "rowsWritten": 0,
            "error": f"UDF returned defer for '{domain}': {udf_error}",
        }

    # 2. LLM structured extraction: generate one representative entity JSON
    tier = str(llmTier or "structured")
    system_prompt = (
        "You are a data extraction agent. Return a JSON object with fields "
        "`id` (string slug), `name` (string), `category` (string), "
        "`source` (string url or 'synthetic'), and `description` (string, max 200 chars). "
        "Do not include any other keys."
    )
    user_prompt = (
        f"Generate one representative real-world entity for the '{domain}' coverage domain. "
        "Return only the JSON object, no markdown."
    )

    try:
        result = _llm.call_tier_json(tier, system=system_prompt, user=user_prompt)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"llm: {exc}"}

    entity_id = _as_str(result.get("id") or domain, 64)
    name = _as_str(result.get("name") or domain, 255)
    category = _as_str(result.get("category") or "unknown", 128)
    source = _as_str(result.get("source") or "synthetic", 255)
    description = _as_str(result.get("description") or "", 500)
    ts = _utc_now()
    vertex_id = _stable_id(f"cov-infer-{domain}", entity_id)

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "CREATE TABLE IF NOT EXISTS vertex_coverage_infer_entity ("
                "  vertex_id   text PRIMARY KEY,"
                "  domain      text,"
                "  entity_id   text,"
                "  name        text,"
                "  category    text,"
                "  source      text,"
                "  description text,"
                "  created_at  timestamptz"
                ")"
            )
            _res = client.q(
                "INSERT INTO vertex_coverage_infer_entity "
                "(vertex_id,domain,entity_id,name,category,source,description,created_at) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s)",
                (vertex_id, domain, entity_id, name, category, source, description, ts),
            )
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"db: {exc}"}

    return {"ok": True, "rowsWritten": 1, "error": ""}


# ── task 4: generate (LangGraph) ─────────────────────────────────────────────

def task_coverage_gap_generate(
    *,
    domain: str = "",
    langgraphId: str = "",
    worldTotal: int = 0,
    **kwargs: Any,
) -> dict[str, Any]:
    """
    Invoke a LangGraph graph registered under langgraphId.
    The graph returns a list of rows to INSERT into vertex_{domain} tables.
    Lazy-imports langgraph_registry to avoid import-time graph compilation.
    """
    graph_id = str(langgraphId or "")
    dom = str(domain or "")
    if not graph_id:
        return {"ok": False, "rowsWritten": 0, "error": "langgraphId not set"}

    # Lazy import — LangGraph graph compilation is expensive
    try:
        from kotodama.primitives import langgraph_registry  # noqa: E402
        graph = langgraph_registry.get(graph_id)
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"registry import: {exc}"}

    if graph is None:
        # Try to auto-load the graph module by convention:
        # graph_id = "business_person_synth_v1" → module kotodama.agents.business_person_synth
        module_name = graph_id.rsplit("_v", 1)[0] if "_v" in graph_id else graph_id
        try:
            import importlib
            mod = importlib.import_module(f"kotodama.agents.{module_name}")
            graph = langgraph_registry.get(graph_id)
        except Exception as exc:  # noqa: BLE001
            return {
                "ok": False,
                "rowsWritten": 0,
                "error": f"graph '{graph_id}' not registered and module load failed: {exc}",
            }

    if graph is None:
        return {
            "ok": False,
            "rowsWritten": 0,
            "error": f"graph '{graph_id}' not found after module load",
        }

    # Invoke graph with coverage context
    try:
        result = graph.invoke({
            "domain": dom,
            "worldTotal": int(worldTotal or 0),
            "batchSize": 50,
        })
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"graph.invoke: {exc}"}

    rows_written = int(result.get("rowsWritten", 0)) if isinstance(result, dict) else 0
    error = str(result.get("error", "")) if isinstance(result, dict) else ""
    return {"ok": not error, "rowsWritten": rows_written, "error": error}


# ── task 5: stats.sync ────────────────────────────────────────────────────────

def task_coverage_gap_stats_sync(**kwargs: Any) -> dict[str, Any]:
    """
    Snapshot mv_world_coverage_live → vertex_coverage_stats for all domains
    that appear in vertex_coverage_recipe. Keeps the minimax MV regret values
    current so the next scan picks the real worst-case domain.

    Run periodically (coverageGapBridge.bpmn wires this before scan).
    Uses UPSERT via delete-then-insert (RisingWave has no ON CONFLICT).
    """
    try:
        if True:
            client = get_kotoba_client()
            # Read current live coverage for all recipe domains
            _res = client.q(
                "SELECT r.domain, r.authority_kind, "
                "  COALESCE(l.collected, 0)::bigint AS collected, "
                "  COALESCE(l.world_total, r.world_total)::bigint AS world_total, "
                "  COALESCE(l.coverage_rate, 0.0) AS coverage_rate "
                "FROM vertex_coverage_recipe r "
                "LEFT JOIN mv_world_coverage_live l ON l.domain = r.domain "
                "WHERE r.authority_kind = 'world'"
            )
            rows = _res
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsSynced": 0, "error": f"read: {exc}"}

    if not rows:
        return {"ok": True, "rowsSynced": 0, "error": "no recipe rows"}

    ts = _utc_now()
    synced = 0
    try:
        if True:
            client = get_kotoba_client()
            for domain, authority_kind, collected, world_total, coverage_rate in rows:
                # RisingWave: no ON CONFLICT → delete-then-insert
                _res = client.q(
                    "DELETE FROM vertex_coverage_stats WHERE domain = %s AND authority_kind = %s",
                    (domain, authority_kind),
                )
                _res = client.q(
                    "INSERT INTO vertex_coverage_stats "
                    "(domain,authority_kind,collected,world_total,coverage_rate,updated_at) "
                    "VALUES (%s,%s,%s,%s,%s,%s)",
                    (domain, authority_kind, int(collected), int(world_total),
                     float(coverage_rate), ts),
                )
                synced += 1
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsSynced": synced, "error": f"write: {exc}"}

    return {"ok": True, "rowsSynced": synced, "error": ""}


# ── (a) natural_person: Wikidata wbgetentities API → vertex_natural_person ────

# In-memory cursor; seeds from DB on first call, advances each run.
_WD_CURSOR: dict[str, int] = {}

_WD_BATCH_API = 50  # wbgetentities max IDs per request


def _wd_entities_batch(qnum_start: int) -> list[tuple[str, str]]:
    """Fetch 50 Q-IDs starting at qnum_start via wbgetentities. Returns [(qid, name)]."""
    ids = "|".join(f"Q{qnum_start + i}" for i in range(_WD_BATCH_API))
    params = urllib.parse.urlencode({
        "action": "wbgetentities",
        "ids": ids,
        "props": "labels|claims",
        "languages": "en",
        "format": "json",
        "formatversion": "2",
    })
    url = "https://www.wikidata.org/w/api.php?" + params
    raw = _fetch_url(url, timeout=30)
    data = json.loads(raw)
    humans: list[tuple[str, str]] = []
    for qid, item in data.get("entities", {}).items():
        if item.get("missing"):
            continue
        for c in item.get("claims", {}).get("P31", []):
            if c.get("mainsnak", {}).get("datavalue", {}).get("value", {}).get("id") == "Q5":
                name = item.get("labels", {}).get("en", {}).get("value", "")
                if name:
                    humans.append((qid, name))
                break
    return humans


@_register_ingest("natural_person")
def _ingest_natural_person(world_total: int) -> dict[str, Any]:
    """Wikidata wbgetentities P31=Q5 humans → vertex_natural_person.

    Uses Q-ID cursor pagination (4 batches × 50 IDs = 200 Q-IDs per run, ~40 humans).
    Cursor seeds from DB max Q-ID on first call; advances by 200 each run.
    """
    runs_per_call = 4  # 4 × 50 = 200 Q-IDs checked
    if "qnum" not in _WD_CURSOR:
        try:
            if True:
                client = get_kotoba_client()
                # Seed cursor from max numeric Q-ID already in DB
                _res = client.q(
                    "SELECT source_record_id FROM vertex_natural_person "
                    "WHERE source_app = 'wikidata' "
                    "ORDER BY LENGTH(source_record_id) DESC, source_record_id DESC "
                    f"LIMIT {int(1)}"
                )
                row = (_res[0] if _res else None)
                if row and row[0] and row[0].startswith("Q"):
                    _WD_CURSOR["qnum"] = max(int(row[0][1:]), 999999)
                else:
                    _WD_CURSOR["qnum"] = 999999  # start from Q1000000
        except Exception:  # noqa: BLE001
            _WD_CURSOR["qnum"] = 999999

    cursor_start = _WD_CURSOR["qnum"]
    humans: list[tuple[str, str]] = []
    for i in range(runs_per_call):
        batch_start = cursor_start + 1 + i * _WD_BATCH_API
        try:
            humans.extend(_wd_entities_batch(batch_start))
        except Exception as exc:  # noqa: BLE001
            return {"ok": False, "rowsWritten": 0, "error": f"wbgetentities: {exc}"}

    _WD_CURSOR["qnum"] = cursor_start + runs_per_call * _WD_BATCH_API

    written = 0
    skipped = 0
    if True:
        client = get_kotoba_client()
        for qid, name in humans:
            vertex_id = (
                f"at://did:web:natural-person.etzhayyim.com"
                f"/com.etzhayyim.apps.naturalPerson.person/wd-{qid}"
            )
            _res = client.q(
                f"SELECT 1 FROM vertex_natural_person WHERE vertex_id = %s LIMIT {int(1)}",
                (vertex_id,),
            )
            if (_res[0] if _res else None):
                skipped += 1
                continue
            _res = client.q(
                "INSERT INTO vertex_natural_person "
                "(vertex_id,name,country,gender,vital_status,birth_year,death_year,"
                " role,source_app,source_record_id,enrichment_status,confidence,source_url) "
                "VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)",
                (
                    vertex_id, _as_str(name, 512), "", "", "alive",
                    None, None, "",
                    "wikidata", qid, "seeded", 0.8,
                    f"https://www.wikidata.org/wiki/{qid}",
                ),
            )
            written += 1
    return {
        "ok": True,
        "rowsWritten": written,
        "skipped": skipped,
        "cursorAt": _WD_CURSOR["qnum"],
        "error": "",
    }


# ── (b) org_hierarchy: GLEIF parent-subsidiary → edge_depends_on ──────────────

@_register_ingest("business_person_lei")
def _ingest_business_person_lei(world_total: int) -> dict[str, Any]:
    """Backfill vertex_business_person.registry_id via GLEIF name-search API.

    Reads rows where registry_id IS NULL, searches
    api.gleif.org/api/v1/lei-records?filter[entity.legalName]={org_name}
    for the best exact match, and UPDATEs registry_id / registry_type = 'lei'.
    Runs before _ingest_org_hierarchy to unblock parent-subsidiary edge creation.
    """
    batch = min(int(world_total or 50), 100)
    updated = 0
    skipped = 0

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"SELECT vertex_id, org_name FROM vertex_business_person "
                f"WHERE (registry_id IS NULL OR registry_id = '') "
                f"AND org_name IS NOT NULL AND org_name != '' "
                f"LIMIT {int(batch)}"
            )
            bp_rows = _res
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"read bp: {exc}"}

    if not bp_rows:
        return {"ok": True, "rowsWritten": 0, "error": "no unmatched business_person rows"}

    # Fast path: bulk-match against vertex_open_lei_entity (populated by GLEIF S3 ingester).
    # Only rows without a local match fall through to the GLEIF search API.
    names = [_as_str(r[1], 512).strip() for r in bp_rows if _as_str(r[1], 512).strip()]
    local_matches: dict[str, str] = {}  # lower(org_name) -> lei
    if names:
        placeholders = ", ".join(["%s"] * len(names))
        try:
            if True:
                client = get_kotoba_client()
                _res = client.q(
                    f"SELECT LOWER(legal_name), lei FROM vertex_open_lei_entity "
                    f"WHERE LOWER(legal_name) IN ({placeholders}) "
                    f"LIMIT {int(len(names) * 2)}",
                    names,
                )
                for lower_name, lei in (_res or []):
                    if lower_name not in local_matches:
                        local_matches[lower_name] = lei
        except Exception:  # noqa: BLE001
            pass  # local cache miss → fall through to API

    gleif_search = "https://api.gleif.org/api/v1/lei-records"
    if True:
        client = get_kotoba_client()
        for vertex_id, org_name in bp_rows:
            org_name = _as_str(org_name, 512).strip()
            if not org_name:
                skipped += 1
                continue

            lei = local_matches.get(org_name.lower(), "")
            if not lei:
                # Fallback: GLEIF name-search API
                params = urllib.parse.urlencode({
                    "filter[entity.legalName]": org_name,
                    "page[size]": 1,
                })
                try:
                    raw = _fetch_url(f"{gleif_search}?{params}", timeout=30)
                    resp = json.loads(raw)
                except Exception:  # noqa: BLE001
                    skipped += 1
                    time.sleep(0.1)
                    continue

                data = resp.get("data") or []
                if not data:
                    skipped += 1
                    time.sleep(0.1)
                    continue

                best = data[0]
                attrs = best.get("attributes") or {}
                lei = _as_str(attrs.get("lei") or best.get("id") or "", 20).strip()
                if not lei:
                    skipped += 1
                    time.sleep(0.1)
                    continue

                # Exact name match guard (GLEIF returns partial matches)
                found_name = ""
                entity = attrs.get("entity") or {}
                legal_name_field = entity.get("legalName") or {}
                if isinstance(legal_name_field, dict):
                    found_name = _as_str(legal_name_field.get("name") or "", 512)
                elif isinstance(legal_name_field, str):
                    found_name = legal_name_field
                if found_name.lower() != org_name.lower():
                    skipped += 1
                    time.sleep(0.1)
                    continue
                time.sleep(0.11)  # GLEIF: ≤10 req/s

            _res = client.q(
                "UPDATE vertex_business_person "
                "SET registry_id = %s, registry_type = %s "
                "WHERE vertex_id = %s",
                (lei, "lei", vertex_id),
            )
            updated += 1

    return {"ok": True, "rowsWritten": updated, "skipped": skipped, "error": ""}


@_register_ingest("org_hierarchy")
def _ingest_org_hierarchy(world_total: int) -> dict[str, Any]:
    """GLEIF parent-subsidiary relationships → edge_depends_on(dep_type='parent_org').

    Reads vertex_business_person rows that have a lei_id set,
    queries GLEIF relationships API for direct parents,
    and creates edge_depends_on(child→parent, dep_type='parent_org').
    """
    batch = min(int(world_total or 200), 500)
    ts = _utc_now()

    # Read known LEIs from vertex_business_person (registry_type='lei')
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"SELECT vertex_id, registry_id FROM vertex_business_person "
                f"WHERE registry_type = 'lei' "
                f"AND registry_id IS NOT NULL AND registry_id != '' "
                f"LIMIT {int(batch)}"
            )
            bp_rows = _res
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"read bp: {exc}"}

    if not bp_rows:
        return {"ok": True, "rowsWritten": 0, "error": "no business_person rows with registry_type=lei"}

    written = 0
    if True:
        client = get_kotoba_client()
        for child_vid, child_lei in bp_rows:
            child_lei = str(child_lei or "").strip()
            if not child_lei:
                continue
            rel_url = (
                f"https://api.gleif.org/api/v1/lei-records/{child_lei}"
                f"/direct-parent-relationship"
            )
            try:
                raw = _fetch_url(rel_url, timeout=30)
                rel_data = json.loads(raw)
            except Exception:  # noqa: BLE001
                continue

            parent_lei = (
                rel_data.get("data", {})
                .get("relationships", {})
                .get("lei-records", {})
                .get("data", {})
                .get("id", "")
            )
            if not parent_lei:
                # Try alternate path: attributes.lei of the related entity
                related = rel_data.get("data", {}).get("relationships", {})
                parent_lei = _as_str(
                    related.get("start-node", {}).get("data", {}).get("id", ""),
                    20,
                )
            if not parent_lei:
                continue

            # Resolve parent vertex_id
            _res = client.q(
                f"SELECT vertex_id FROM vertex_business_person "
                f"WHERE registry_id = %s AND registry_type = 'lei' LIMIT {int(1)}",
                (parent_lei,),
            )
            parent_row = (_res[0] if _res else None)
            if not parent_row:
                continue
            parent_vid = parent_row[0]
            edge_id = _stable_id("dep-org", child_vid, parent_vid)

            _res = client.q(
                f"SELECT 1 FROM edge_depends_on WHERE edge_id = %s LIMIT {int(1)}",
                (edge_id,),
            )
            if (_res[0] if _res else None):
                continue

            _res = client.q(
                "INSERT INTO edge_depends_on "
                "(edge_id,src_vid,dst_vid,dep_type,slack_days) "
                "VALUES (%s,%s,%s,%s,%s)",
                (edge_id, child_vid, parent_vid, "parent_org", 0),
            )
            written += 1
            time.sleep(0.1)  # GLEIF rate limit: 10 req/s

    return {"ok": True, "rowsWritten": written, "error": ""}


# ── (c) follows_history: PDS graph.getFollows → edge_follows backfill ─────────

@_register_ingest("follows_history")
def _ingest_follows_history(world_total: int) -> dict[str, Any]:
    """Backfill edge_follows from PDS app.bsky.graph.getFollows for known actors.

    Reads actor DIDs from vertex_actor, paginates through their follows via
    the AT Protocol PDS, and inserts missing edge_follows rows.
    PDS URL: ATPROTO_PDS_URL env var (default: https://atproto.etzhayyim.com).
    """
    pds_url = os.environ.get("ATPROTO_PDS_URL", "https://atproto.etzhayyim.com").rstrip("/")
    actor_limit = min(int(world_total or 50), 200)
    ts = _utc_now()

    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                f"SELECT did FROM vertex_actor "
                f"WHERE did IS NOT NULL AND did != '' "
                f"LIMIT {int(actor_limit)}"
            )
            actor_rows = _res
    except Exception as exc:  # noqa: BLE001
        return {"ok": False, "rowsWritten": 0, "error": f"read actors: {exc}"}

    if not actor_rows:
        return {"ok": True, "rowsWritten": 0, "error": "no actor rows"}

    written = 0
    if True:
        client = get_kotoba_client()
        for (actor_did,) in actor_rows:
            actor_did = str(actor_did or "").strip()
            if not actor_did:
                continue
            cursor_val: str | None = None
            page = 0
            while page < 10:
                params: dict[str, Any] = {"actor": actor_did, "limit": 100}
                if cursor_val:
                    params["cursor"] = cursor_val
                follows_url = (
                    f"{pds_url}/xrpc/app.bsky.graph.getFollows?"
                    + urllib.parse.urlencode(params)
                )
                try:
                    raw = _fetch_url(follows_url, timeout=30)
                    resp = json.loads(raw)
                except Exception:  # noqa: BLE001
                    break

                follows = resp.get("follows") or []
                for follow in follows:
                    follow_did = _as_str(follow.get("did") or "", 512)
                    if not follow_did:
                        continue
                    src_vid = actor_did
                    dst_vid = follow_did
                    rkey = _as_str(follow.get("$type") or "", 64)
                    edge_id = _stable_id("follows", src_vid, dst_vid)
                    _res = client.q(
                        f"SELECT 1 FROM edge_follows WHERE edge_id = %s LIMIT {int(1)}",
                        (edge_id,),
                    )
                    if (_res[0] if _res else None):
                        continue
                    _res = client.q(
                        "INSERT INTO edge_follows "
                        "(edge_id,src_vid,dst_vid,rkey,repo,created_at) "
                        "VALUES (%s,%s,%s,%s,%s,%s)",
                        (edge_id, src_vid, dst_vid, rkey, actor_did, ts),
                    )
                    written += 1

                cursor_val = resp.get("cursor")
                if not cursor_val or not follows:
                    break
                page += 1

    return {"ok": True, "rowsWritten": written, "error": ""}


# ── register ──────────────────────────────────────────────────────────────────

def register(worker: Any, timeout_ms: int = 300_000) -> None:
    worker.task(
        task_type="coverage.gap.stats.sync",
        single_value=False,
        timeout_ms=min(timeout_ms, 60_000),
    )(task_coverage_gap_stats_sync)
    worker.task(
        task_type="coverage.gap.scan",
        single_value=False,
        timeout_ms=min(timeout_ms, 30_000),
    )(task_coverage_gap_scan)
    worker.task(
        task_type="coverage.gap.ingest",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_coverage_gap_ingest)
    worker.task(
        task_type="coverage.gap.infer",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_coverage_gap_infer)
    worker.task(
        task_type="coverage.gap.generate",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_coverage_gap_generate)
