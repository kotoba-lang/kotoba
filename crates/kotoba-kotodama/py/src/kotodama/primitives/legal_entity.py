"""Legal-entity registry primitives for ADR-0056 BPMN-as-actor.

These handlers replace the former Cloudflare Worker-local registry logic with
LangServer task subscribers. GLEIF, EDGAR, and supported country registries perform
bounded HTTP collection and commit rows to the existing graph tables.
"""

from __future__ import annotations
from kotodama.kotoba_datomic import get_kotoba_client

import hashlib
import base64
import csv
import json
import os
import re
import time
from io import StringIO
from typing import Any
from urllib.parse import urlencode

import aiohttp



_OWNER_DID = "did:web:legal-entity.etzhayyim.com"
_COL_ENTITY = "com.etzhayyim.apps.legalEntity.legalEntity"
_COL_FILING = "com.etzhayyim.apps.legalEntity.filing"
_GLEIF_URL = "https://api.gleif.org/api/v1/lei-records"
_EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_EDGAR_UA = os.environ.get("SEC_USER_AGENT", "legal-entity.etzhayyim.com/1.0 contact@etzhayyim.com")

_REGISTRY_TASKS: dict[str, dict[str, str]] = {
    "Jpn": {"country": "JP", "label": "Japan registry", "source": "jpn-registry"},
    "Gbr": {"country": "GB", "label": "UK Companies House", "source": "gbr-companies-house"},
    "Fra": {"country": "FR", "label": "France INPI/SIRENE", "source": "fra-registry"},
    "Nor": {"country": "NO", "label": "Norway Bronnoysund", "source": "nor-registry"},
    "Dnk": {"country": "DK", "label": "Denmark CVR", "source": "dnk-cvr"},
    "Fin": {"country": "FI", "label": "Finland PRH", "source": "fin-prh"},
    "Est": {"country": "EE", "label": "Estonia e-Business Register", "source": "est-registry"},
    "Cze": {"country": "CZ", "label": "Czech ARES", "source": "cze-ares"},
    "Nzl": {"country": "NZ", "label": "New Zealand Companies Register", "source": "nzl-registry"},
    "Che": {"country": "CH", "label": "Switzerland Zefix", "source": "che-zefix"},
    "Nld": {"country": "NL", "label": "Netherlands KVK", "source": "nld-kvk"},
    "Isr": {"country": "IL", "label": "Israel Companies Register", "source": "isr-registry"},
}

_REQUIRED_ENV: dict[str, tuple[str, ...]] = {
    "Jpn": ("NTA_APPLICATION_ID",),
    "Gbr": ("COMPANIES_HOUSE_API_KEY",),
    "Fra": ("INSEE_API_TOKEN",),
    "Dnk": ("CVR_API_ENABLED",),
    "Est": ("EST_ARIREGISTER_DATA_URL",),
    "Nzl": ("NZBN_API_KEY",),
    "Che": ("ZEFIX_USERNAME", "ZEFIX_PASSWORD"),
    "Nld": ("KVK_API_KEY",),
}

_REQUIRED_QUERY: dict[str, tuple[str, ...]] = {
    "Cze": ("obchodniJmeno", "query", "prefix"),
    "Dnk": ("search", "vat", "name", "phone"),
    "Nld": ("kvkNummer", "handelsnaam", "query"),
}

_COLUMN_CACHE: dict[str, set[str]] = {}
_IDENT_RE = re.compile(r"^[a-zA-Z_][a-zA-Z0-9_]*$")


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _date_today() -> str:
    return time.strftime("%Y-%m-%d", time.gmtime())


def _slug(value: Any, *, max_len: int = 64) -> str:
    raw = str(value or "").strip().lower()
    out = re.sub(r"[^a-z0-9._-]+", "-", raw).strip("-")
    if not out:
        out = hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]
    return out[:max_len]


def _entity_vid(rkey: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_ENTITY}/{rkey}"


def _filing_vid(rkey: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_FILING}/{rkey}"


def _json(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def _is_dup_error(e: Exception) -> bool:
    s = str(e).lower()
    return "already exists" in s or "duplicate" in s or "unique" in s or "primary key" in s


def _table_columns(table: str) -> set[str]:
    cached = _COLUMN_CACHE.get(table)
    if cached is not None:
        return cached
    if True:
        client = get_kotoba_client()
        _res = client.q(
            "SELECT column_name FROM information_schema.columns WHERE table_name = %s",
            (table,),
        )
        rows = _res
    cols = {str(row[0]) for row in rows}
    _COLUMN_CACHE[table] = cols
    return cols


def _insert_row(table: str, row: dict[str, Any]) -> bool:
    if not _IDENT_RE.match(table):
        raise ValueError(f"unsafe table name: {table}")
    cols = [col for col in row if _IDENT_RE.match(col) and col in _table_columns(table)]
    if not cols:
        return False
    placeholders = ",".join(["%s"] * len(cols))
    quoted_cols = ",".join(f'"{col}"' for col in cols)
    values = tuple(row[col] for col in cols)
    if True:
        client = get_kotoba_client()
        _res = client.q(f'INSERT INTO "{table}" ({quoted_cols}) VALUES ({placeholders})', values)
    return True


def _legal_name_from_gleif(record: dict[str, Any]) -> str:
    attrs = record.get("attributes") if isinstance(record.get("attributes"), dict) else {}
    entity = attrs.get("entity") if isinstance(attrs.get("entity"), dict) else {}
    legal_name = entity.get("legalName")
    if isinstance(legal_name, dict):
        return str(legal_name.get("name") or "")
    return str(legal_name or attrs.get("legalName") or "")


def _gleif_entity_row(record: dict[str, Any], *, page: int) -> dict[str, Any]:
    attrs = record.get("attributes") if isinstance(record.get("attributes"), dict) else {}
    entity = attrs.get("entity") if isinstance(attrs.get("entity"), dict) else {}
    registration = attrs.get("registration") if isinstance(attrs.get("registration"), dict) else {}
    legal_addr = entity.get("legalAddress") if isinstance(entity.get("legalAddress"), dict) else {}
    headquarters_addr = entity.get("headquartersAddress") if isinstance(entity.get("headquartersAddress"), dict) else {}
    lei = str(attrs.get("lei") or record.get("id") or "").strip()
    rkey = _slug(lei or hashlib.sha256(_json(record).encode("utf-8")).hexdigest()[:20])
    status = str(registration.get("status") or attrs.get("registrationStatus") or entity.get("status") or "UNKNOWN")
    name = _legal_name_from_gleif(record)
    country = str(legal_addr.get("country") or headquarters_addr.get("country") or "")
    now = _utc_now()
    return {
        "vertex_id": _entity_vid(rkey),
        "rkey": rkey,
        "repo": _OWNER_DID,
        "label": name[:256],
        "did": f"{_OWNER_DID}:{rkey}",
        "collection": _COL_ENTITY,
        "name": name,
        "display_name": name,
        "description": f"GLEIF LEI {lei}".strip(),
        "entity_type": "legal_entity",
        "registration_number": entity.get("registeredAs") or lei,
        "jurisdiction": entity.get("jurisdiction") or entity.get("legalJurisdiction"),
        "country": country,
        "address": _json(legal_addr) if legal_addr else "",
        "incorporation_date": entity.get("creationDate"),
        "status": "active" if status == "ISSUED" else status.lower(),
        "source_did": f"{_OWNER_DID}:source:gleif",
        "lei": lei,
        "created_date": _date_today(),
        "sensitivity_ord": 1,
        "owner_did": _OWNER_DID,
        "source": "gleif",
        "source_record_id": lei,
        "actor_did": _OWNER_DID,
        "org_did": "anon",
        "props": _json({"sourcePage": page, "gleif": record}),
    }


async def task_gleif_fetch_pages(
    pages: int = 1,
    pageSize: int = 100,
    startPage: int = 1,
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    page_count = max(1, min(int(pages or 1), int(os.environ.get("LEGAL_ENTITY_MAX_GLEIF_PAGES", "5"))))
    page_size = max(1, min(int(pageSize or 100), 200))
    start_page = max(1, int(startPage or 1))

    fetched = 0
    inserted = 0
    skipped = 0
    errors = 0
    pages_done: list[int] = []

    async with aiohttp.ClientSession() as session:
        for page in range(start_page, start_page + page_count):
            url = f"{_GLEIF_URL}?{urlencode({'page[number]': page, 'page[size]': page_size})}"
            async with session.get(
                url,
                headers={"Accept": "application/vnd.api+json, application/json", "User-Agent": "etzhayyim-legal-entity-zeebe/0.1"},
                timeout=aiohttp.ClientTimeout(total=45),
            ) as resp:
                if resp.status != 200:
                    errors += 1
                    continue
                payload = await resp.json(content_type=None)
            records = payload.get("data") if isinstance(payload, dict) else []
            if not isinstance(records, list):
                records = []
            fetched += len(records)
            pages_done.append(page)
            if dryRun:
                continue
            for record in records:
                if not isinstance(record, dict):
                    continue
                try:
                    if _insert_row("vertex_legal_entity", _gleif_entity_row(record, page=page)):
                        inserted += 1
                except Exception as e:  # noqa: BLE001
                    if _is_dup_error(e):
                        skipped += 1
                    else:
                        errors += 1

    return {
        "result": {
            "ok": errors == 0,
            "source": "gleif",
            "pages": pages_done,
            "pageSize": page_size,
            "fetched": fetched,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "nextPage": start_page + page_count,
            "dryRun": bool(dryRun),
        }
    }


def task_gleif_register_dids(limit: int = 500, **_: Any) -> dict[str, Any]:
    bounded = max(1, min(int(limit or 500), 5000))
    candidates = 0
    try:
        if True:
            client = get_kotoba_client()
            _res = client.q(
                "SELECT vertex_id FROM vertex_legal_entity "
                f"WHERE vertex_id IS NOT NULL AND source = %s LIMIT {bounded}",
                ("gleif",),
            )
            candidates = len(_res)
    except Exception as e:  # noqa: BLE001
        return {"result": {"ok": False, "error": f"GLEIF DID candidate scan failed: {e}", "registered": 0}}
    return {
        "result": {
            "ok": True,
            "registered": 0,
            "candidates": candidates,
            "mode": "already-addressed-by-at-uri",
            "note": "vertex_id and did are deterministic at:// / did:web identifiers; no separate DID registry writer is required here.",
        }
    }


def _edgar_entity_row(item: dict[str, Any]) -> dict[str, Any]:
    cik = str(item.get("cik_str") or "").strip()
    ticker = str(item.get("ticker") or "").strip()
    name = str(item.get("title") or "").strip()
    rkey = _slug(f"us-edgar-{cik or ticker or name}")
    return {
        "vertex_id": _entity_vid(rkey),
        "rkey": rkey,
        "repo": _OWNER_DID,
        "label": name[:256],
        "did": f"{_OWNER_DID}:{rkey}",
        "collection": _COL_ENTITY,
        "name": name,
        "display_name": name,
        "description": f"SEC EDGAR company {cik}".strip(),
        "entity_type": "public_company",
        "registration_number": cik,
        "jurisdiction": "US",
        "country": "US",
        "status": "active",
        "source_did": f"{_OWNER_DID}:source:sec-edgar",
        "tax_id": cik,
        "created_date": _date_today(),
        "sensitivity_ord": 1,
        "owner_did": _OWNER_DID,
        "source": "sec-edgar",
        "source_record_id": cik,
        "actor_did": _OWNER_DID,
        "org_did": "anon",
        "props": _json({"ticker": ticker, "edgar": item}),
    }


def _clean(value: Any) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _registry_entity_row(
    *,
    name: Any,
    registration_number: Any,
    jurisdiction: Any,
    country: str,
    source: str,
    source_record_id: Any,
    entity_type: Any = "",
    entity_status: Any = "ACTIVE",
    industry_code: Any = "",
    incorporation_date: Any = "",
    raw: Any = None,
) -> dict[str, Any] | None:
    record_name = _clean(name)
    record_id = _clean(source_record_id or registration_number)
    reg_number = _clean(registration_number)
    if not record_name or not record_id:
        return None
    source_key = source.lower().replace("_", "-")
    rkey = _slug(f"{source_key}-{record_id}")
    now = _utc_now()
    return {
        "vertex_id": _entity_vid(rkey),
        "rkey": rkey,
        "repo": _OWNER_DID,
        "label": record_name[:256],
        "did": f"{_OWNER_DID}:{rkey}",
        "collection": _COL_ENTITY,
        "name": record_name,
        "display_name": record_name,
        "description": f"{source_key}:{record_id} - {_clean(jurisdiction)}",
        "entity_type": _clean(entity_type),
        "registration_number": reg_number,
        "jurisdiction": _clean(jurisdiction),
        "country": country,
        "incorporation_date": _clean(incorporation_date),
        "status": (_clean(entity_status) or "ACTIVE").lower(),
        "source_did": f"{_OWNER_DID}:source:{source_key}",
        "industry_code": _clean(industry_code),
        "created_date": _date_today(),
        "sensitivity_ord": 1,
        "owner_did": _OWNER_DID,
        "source": source_key,
        "source_record_id": record_id,
        "actor_did": _OWNER_DID,
        "org_did": "anon",
        "props": _json({"registry": source, "raw": raw}) if raw is not None else _json({"registry": source}),
    }


async def _get_json(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    headers: dict[str, str] | None = None,
) -> Any:
    async with session.get(url, params=params, headers=headers or {"Accept": "application/json"}) as resp:
        if resp.status >= 400:
            text = await resp.text()
            raise RuntimeError(f"GET {url} {resp.status}: {text[:300]}")
        return await resp.json(content_type=None)


async def _post_json(
    session: aiohttp.ClientSession,
    url: str,
    payload: dict[str, Any],
    *,
    headers: dict[str, str] | None = None,
) -> Any:
    async with session.post(url, json=payload, headers=headers or {"Accept": "application/json"}) as resp:
        if resp.status >= 400:
            text = await resp.text()
            raise RuntimeError(f"POST {url} {resp.status}: {text[:300]}")
        return await resp.json(content_type=None)


async def _get_text(
    session: aiohttp.ClientSession,
    url: str,
    *,
    params: dict[str, Any] | None = None,
) -> str:
    async with session.get(url, params=params) as resp:
        if resp.status >= 400:
            text = await resp.text()
            raise RuntimeError(f"GET {url} {resp.status}: {text[:300]}")
        body = await resp.read()
    for encoding in ("utf-8-sig", "cp932", "shift_jis"):
        try:
            return body.decode(encoding)
        except UnicodeDecodeError:
            continue
    return body.decode("utf-8", errors="replace")


def _collect_records(items: Any, mapper: Any) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    if not isinstance(items, list):
        return records
    for item in items:
        if isinstance(item, dict):
            record = mapper(item)
            if record:
                records.append(record)
    return records


def _list_payload(data: Any, *keys: str) -> list[Any]:
    if isinstance(data, list):
        return data
    if not isinstance(data, dict):
        return []
    for key in keys:
        value = data.get(key)
        if isinstance(value, list):
            return value
    return []


def _next_cursor(data: Any) -> str:
    if not isinstance(data, dict):
        return ""
    header = data.get("header") if isinstance(data.get("header"), dict) else {}
    for key in ("curseurSuivant", "nextCursor", "curseur"):
        value = header.get(key) or data.get(key)
        if value:
            return str(value)
    return ""


def _insert_many_entities(rows: list[dict[str, Any]]) -> tuple[int, int, int, str]:
    inserted = 0
    skipped = 0
    errors = 0
    first_error = ""
    for row in rows:
        try:
            if _insert_row("vertex_legal_entity", row):
                inserted += 1
        except Exception as e:  # noqa: BLE001
            if _is_dup_error(e):
                skipped += 1
            else:
                errors += 1
                first_error = first_error or str(e)[:300]
    return inserted, skipped, errors, first_error


def _basic_auth_header(api_key: str) -> dict[str, str]:
    token = base64.b64encode(f"{api_key}:".encode("utf-8")).decode("ascii")
    return {"Accept": "application/json", "Authorization": f"Basic {token}"}


def _missing_env(suffix: str) -> list[str]:
    return [name for name in _REQUIRED_ENV.get(suffix, ()) if not os.environ.get(name, "").strip()]


def _missing_query(suffix: str, variables: dict[str, Any]) -> list[str]:
    keys = _REQUIRED_QUERY.get(suffix, ())
    if not keys:
        return []
    if any(_clean(variables.get(key)) for key in keys):
        return []
    return list(keys)


def _config_error_result(
    suffix: str,
    *,
    pages: int,
    page_size: int,
    start_page: int,
    dry_run: bool,
    missing_env: list[str] | None = None,
    missing_query: list[str] | None = None,
) -> dict[str, Any]:
    meta = _REGISTRY_TASKS[suffix]
    details: dict[str, Any] = {}
    if missing_env:
        details["requiresAuthEnv"] = missing_env
    if missing_query:
        details["requiresQuery"] = missing_query
    first_error = (
        f"missing required env: {', '.join(missing_env)}"
        if missing_env
        else f"missing required query: one of {', '.join(missing_query or [])}"
    )
    return {
        "result": {
            "ok": False,
            "source": meta["source"],
            "country": meta["country"],
            "registry": meta["label"],
            "pagesProcessed": 0,
            "pageSize": page_size,
            "startPage": start_page,
            "totalInserted": 0,
            "totalSkipped": 0,
            "totalErrors": 1,
            "apiTotal": 0,
            "firstError": first_error,
            "pages": [],
            "dryRun": dry_run,
            **details,
            "ts": _utc_now(),
        }
    }


def _simple_error_result(
    suffix: str,
    *,
    pages: int,
    page_size: int,
    start_page: int,
    dry_run: bool,
    first_error: str,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    meta = _REGISTRY_TASKS[suffix]
    return {
        "result": {
            "ok": False,
            "source": meta["source"],
            "country": meta["country"],
            "registry": meta["label"],
            "pagesProcessed": 0,
            "pageSize": page_size,
            "startPage": start_page,
            "totalInserted": 0,
            "totalSkipped": 0,
            "totalErrors": 1,
            "apiTotal": 0,
            "firstError": first_error,
            "pages": [],
            "dryRun": dry_run,
            **(extra or {}),
            "ts": _utc_now(),
        }
    }


async def task_edgar_collect_usa(
    offset: int = 0,
    limit: int = 200,
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    off = max(0, int(offset or 0))
    lim = max(1, min(int(limit or 200), 1000))
    async with aiohttp.ClientSession() as session:
        async with session.get(
            _EDGAR_TICKERS_URL,
            headers={"User-Agent": _EDGAR_UA},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                return {"result": {"ok": False, "error": f"EDGAR tickers {resp.status}", "inserted": 0}}
            payload = await resp.json(content_type=None)

    rows = list(payload.values()) if isinstance(payload, dict) else []
    batch = [row for row in rows[off: off + lim] if isinstance(row, dict)]
    inserted = 0
    skipped = 0
    errors = 0
    if not dryRun:
        for item in batch:
            try:
                if _insert_row("vertex_legal_entity", _edgar_entity_row(item)):
                    inserted += 1
            except Exception as e:  # noqa: BLE001
                if _is_dup_error(e):
                    skipped += 1
                else:
                    errors += 1

    return {
        "result": {
            "ok": errors == 0,
            "source": "sec-edgar",
            "total": len(rows),
            "offset": off,
            "limit": lim,
            "fetched": len(batch),
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "nextOffset": off + len(batch),
            "exhausted": len(batch) < lim,
            "dryRun": bool(dryRun),
        }
    }


async def task_edgar_ingest_sec_disclosure(
    cik: int | str = 0,
    limit: int = 40,
    dryRun: bool = False,
    **_: Any,
) -> dict[str, Any]:
    cik_raw = str(cik or "").strip()
    if not cik_raw:
        return {"result": {"ok": False, "error": "cik required", "inserted": 0}}
    cik_str = cik_raw.zfill(10)
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://data.sec.gov/submissions/CIK{cik_str}.json",
            headers={"User-Agent": _EDGAR_UA},
            timeout=aiohttp.ClientTimeout(total=30),
        ) as resp:
            if resp.status != 200:
                return {"result": {"ok": False, "error": f"EDGAR CIK {resp.status}", "cik": cik_raw, "inserted": 0}}
            payload = await resp.json(content_type=None)

    recent = ((payload.get("filings") or {}).get("recent") or {}) if isinstance(payload, dict) else {}
    accession = recent.get("accessionNumber") if isinstance(recent, dict) else []
    forms = recent.get("form") if isinstance(recent, dict) else []
    filing_dates = recent.get("filingDate") if isinstance(recent, dict) else []
    report_dates = recent.get("reportDate") if isinstance(recent, dict) else []
    bounded = max(1, min(int(limit or 40), 200))
    n = min(len(accession or []), bounded)
    inserted = 0
    skipped = 0
    errors = 0
    company_vid = _entity_vid(_slug(f"us-edgar-{int(cik_raw)}"))
    company_name = str(payload.get("name") or "") if isinstance(payload, dict) else ""
    ticker = ",".join(str(t) for t in (payload.get("tickers") or [])[:5]) if isinstance(payload, dict) else ""
    exchange = ",".join(str(t) for t in (payload.get("exchanges") or [])[:5]) if isinstance(payload, dict) else ""
    for i in range(n):
        acc = str(accession[i] or "")
        rkey = _slug(f"sec-{cik_str}-{acc}", max_len=96)
        filing_url = f"https://www.sec.gov/Archives/edgar/data/{int(cik_raw)}/{acc.replace('-', '')}/"
        row = {
            "vertex_id": _filing_vid(rkey),
            "rkey": rkey,
            "repo": _OWNER_DID,
            "label": f"{company_name} {forms[i] if i < len(forms) else ''}".strip()[:256],
            "company_did": company_vid,
            "filing_source": "sec-edgar",
            "filing_type": forms[i] if i < len(forms) else "",
            "filing_date": filing_dates[i] if i < len(filing_dates) else "",
            "period_end": report_dates[i] if i < len(report_dates) else "",
            "accession_no": acc,
            "filing_url": filing_url,
            "issuer_name": company_name,
            "issuer_ticker": ticker,
            "issuer_exchange": exchange,
            "country": "US",
            "language": "en",
            "source_license": "SEC public data",
            "owner_did": _OWNER_DID,
            "sensitivity_ord": 1,
            "created_date": _date_today(),
            "ingested_at": _utc_now(),
            "props": _json({"cik": cik_raw}),
        }
        if dryRun:
            continue
        try:
            if _insert_row("vertex_company_filing", row):
                inserted += 1
        except Exception as e:  # noqa: BLE001
            if _is_dup_error(e):
                skipped += 1
            else:
                errors += 1

    return {
        "result": {
            "ok": errors == 0,
            "source": "sec-edgar-submissions",
            "cik": cik_raw,
            "companyDid": company_vid,
            "fetched": n,
            "inserted": inserted,
            "skipped": skipped,
            "errors": errors,
            "dryRun": bool(dryRun),
        }
    }


async def _fetch_country_registry_page(
    session: aiohttp.ClientSession,
    suffix: str,
    page: int,
    page_size: int,
    variables: dict[str, Any],
) -> tuple[list[dict[str, Any]], int, dict[str, Any]]:
    if suffix == "Jpn":
        params: dict[str, Any] = {
            "id": os.environ["NTA_APPLICATION_ID"],
            "type": "12",
            "from": _clean(variables.get("from") or "2015-10-05"),
            "to": _clean(variables.get("to") or _utc_now()[:10]),
            "divide": page,
        }
        if variables.get("kind"):
            params["kind"] = _clean(variables.get("kind"))
        if variables.get("prefecture"):
            params["address"] = _clean(variables.get("prefecture"))
        text = await _get_text(session, "https://api.houjin-bangou.nta.go.jp/4/diff", params=params)
        rows = list(csv.reader(StringIO(text)))
        records: list[dict[str, Any]] = []
        for cols in rows[1:]:
            if len(cols) < 9 or len(records) >= page_size:
                continue
            row = _registry_entity_row(
                name=cols[6],
                registration_number=cols[1],
                jurisdiction=f"JP-{_clean(cols[7])}",
                country="JP",
                entity_type=cols[5] if len(cols) > 5 else "",
                entity_status="ACTIVE",
                incorporation_date=cols[4] if len(cols) > 4 else "",
                source="NTA_JPN",
                source_record_id=cols[1],
                raw={"csv": cols},
            )
            if row:
                records.append(row)
        return records, len(records), {}

    if suffix == "Gbr":
        api_key = os.environ["COMPANIES_HOUSE_API_KEY"].strip()
        headers = _basic_auth_header(api_key)
        params: dict[str, Any] = {
            "company_status": _clean(variables.get("companyStatus") or "active"),
            "size": page_size,
            "start_index": int(variables.get("startIndex") or 0) + page * page_size,
        }
        if variables.get("companyType"):
            params["company_type"] = _clean(variables.get("companyType"))
        if variables.get("incorporatedFrom"):
            params["incorporated_from"] = _clean(variables.get("incorporatedFrom"))
        data = await _get_json(
            session,
            "https://api.company-information.service.gov.uk/advanced-search/companies",
            params=params,
            headers=headers,
        )
        records = _collect_records(data.get("items") or [], lambda item: _registry_entity_row(
            name=item.get("company_name"),
            registration_number=item.get("company_number"),
            jurisdiction="GB",
            country="GB",
            entity_type=item.get("company_type"),
            entity_status=item.get("company_status") or "active",
            industry_code=(item.get("sic_codes") or [""])[0],
            incorporation_date=item.get("date_of_creation"),
            source="CH_GBR",
            source_record_id=item.get("company_number"),
            raw=item,
        ))
        return records, int(data.get("total_results") or 0), {}

    if suffix == "Fra":
        cursor = _clean(variables.get("cursor"))
        params: dict[str, Any] = {"nombre": page_size}
        if cursor and page == int(variables.get("startPage") or 0):
            params["curseur"] = cursor
        elif not cursor:
            params["debut"] = page * page_size
        filters: list[str] = []
        if variables.get("activesOnly") is not False:
            filters.append("etatAdministratifUniteLegale:A")
        if variables.get("departement"):
            filters.append(f"codePostalEtablissement:{_clean(variables.get('departement'))}*")
        if filters:
            params["q"] = " AND ".join(filters)
        headers = {"Accept": "application/json"}
        token = os.environ["INSEE_API_TOKEN"].strip()
        headers["Authorization"] = f"Bearer {token}"
        data = await _get_json(session, "https://api.insee.fr/entreprises/sirene/V3.11/siren", params=params, headers=headers)
        records = _collect_records(data.get("unitesLegales") or [], lambda item: _registry_entity_row(
            name=((item.get("periodesUniteLegale") or [{}])[0]).get("denominationUniteLegale") or item.get("siren"),
            registration_number=item.get("siren"),
            jurisdiction="FR",
            country="FR",
            entity_type=((item.get("periodesUniteLegale") or [{}])[0]).get("categorieJuridiqueUniteLegale"),
            entity_status="ACTIVE" if ((item.get("periodesUniteLegale") or [{}])[0]).get("etatAdministratifUniteLegale") == "A" else "INACTIVE",
            industry_code=((item.get("periodesUniteLegale") or [{}])[0]).get("activitePrincipaleUniteLegale"),
            incorporation_date=item.get("dateCreationUniteLegale"),
            source="SIRENE_FRA",
            source_record_id=item.get("siren"),
            raw=item,
        ))
        return records, int((data.get("header") or {}).get("total") or 0), {"nextCursor": _next_cursor(data)}

    if suffix == "Nor":
        params: dict[str, Any] = {"size": page_size, "page": page}
        if variables.get("organisasjonsform"):
            params["organisasjonsform"] = _clean(variables.get("organisasjonsform"))
        data = await _get_json(session, "https://data.brreg.no/enhetsregisteret/api/enheter", params=params)
        records = _collect_records(((data.get("_embedded") or {}).get("enheter") or []), lambda item: _registry_entity_row(
            name=item.get("navn"),
            registration_number=item.get("organisasjonsnummer"),
            jurisdiction=f"NO-{_clean((item.get('forretningsadresse') or {}).get('kommunenummer'))}",
            country="NO",
            entity_type=(item.get("organisasjonsform") or {}).get("kode"),
            entity_status="ACTIVE" if item.get("registreringsdatoEnhetsregisteret") else "INACTIVE",
            industry_code=(item.get("naeringskode1") or {}).get("kode"),
            incorporation_date=item.get("stiftelsesdato") or item.get("registreringsdatoEnhetsregisteret"),
            source="BRREG_NOR",
            source_record_id=item.get("organisasjonsnummer"),
            raw=item,
        ))
        return records, int((data.get("page") or {}).get("totalElements") or 0), {}

    if suffix == "Dnk":
        search = _clean(variables.get("search") or variables.get("vat") or variables.get("name") or variables.get("phone"))
        params = {"country": "dk", "format": "json", "search": search}
        data = await _get_json(
            session,
            "https://cvrapi.dk/api",
            params=params,
            headers={"Accept": "application/json", "User-Agent": _EDGAR_UA},
        )
        records = _collect_records([data], lambda item: _registry_entity_row(
            name=item.get("name"),
            registration_number=item.get("vat"),
            jurisdiction="DK",
            country="DK",
            entity_type=item.get("companydesc") or variables.get("virksomhedsform"),
            entity_status="ACTIVE" if item.get("status") == "NORMAL" else item.get("status") or "ACTIVE",
            industry_code=item.get("industrycode"),
            incorporation_date=item.get("startdate"),
            source="CVR_DNK",
            source_record_id=item.get("vat"),
            raw=item,
        ))
        return records, len(records), {}

    if suffix == "Fin":
        params: dict[str, Any] = {"totalResults": "true", "maxResults": page_size, "resultsFrom": page * page_size}
        if variables.get("companyForm"):
            params["companyForm"] = _clean(variables.get("companyForm"))
        data = await _get_json(session, "https://avoindata.prh.fi/opendata-ytj-api/v3/companies", params=params)

        def fin_name(item: dict[str, Any]) -> str:
            names = item.get("names") if isinstance(item.get("names"), list) else []
            current = [n for n in names if isinstance(n, dict) and not n.get("endDate")]
            picked = (current or names or [{}])[0]
            return _clean(picked.get("name") if isinstance(picked, dict) else "")

        def fin_value(item: dict[str, Any], key: str) -> str:
            value = item.get(key)
            if isinstance(value, dict):
                return _clean(value.get("value"))
            return _clean(value)

        def fin_description(value: Any) -> str:
            if not isinstance(value, dict):
                return _clean(value)
            descriptions = value.get("descriptions") if isinstance(value.get("descriptions"), list) else []
            picked = next((d for d in descriptions if isinstance(d, dict) and d.get("languageCode") == "3"), None)
            if picked is None:
                picked = next((d for d in descriptions if isinstance(d, dict)), {})
            return _clean(picked.get("description") if isinstance(picked, dict) else "")

        records = _collect_records(data.get("companies") or [], lambda item: _registry_entity_row(
            name=fin_name(item),
            registration_number=fin_value(item, "businessId"),
            jurisdiction="FI",
            country="FI",
            entity_type=fin_description(item.get("companyForm")),
            entity_status="ACTIVE" if not item.get("endDate") else "INACTIVE",
            industry_code=fin_value(item.get("mainBusinessLine") or {}, "type"),
            incorporation_date=fin_value(item, "registrationDate"),
            source="PRH_FIN",
            source_record_id=fin_value(item, "businessId"),
            raw=item,
        ))
        return records, int(data.get("totalResults") or 0), {}

    if suffix == "Est":
        data = await _get_json(
            session,
            os.environ["EST_ARIREGISTER_DATA_URL"].strip(),
            params={"limit": page_size, "offset": page * page_size},
        )
        items = _list_payload(data, "data", "items", "records", "ettevotjad")
        records = _collect_records(items, lambda item: _registry_entity_row(
            name=item.get("nimi") or item.get("arinimi"),
            registration_number=item.get("ariregistri_kood") or item.get("registrikood"),
            jurisdiction="EE",
            country="EE",
            entity_type=item.get("oiguslik_vorm") or variables.get("legalForm"),
            entity_status="ACTIVE" if item.get("staatus") == "R" else item.get("staatus") or "ACTIVE",
            industry_code=item.get("emtak_kood"),
            incorporation_date=item.get("registreerimise_kpv"),
            source="ARIK_EST",
            source_record_id=item.get("ariregistri_kood") or item.get("registrikood"),
            raw=item,
        ))
        return records, len(records), {}

    if suffix == "Cze":
        query = _clean(variables.get("obchodniJmeno") or variables.get("query") or variables.get("prefix"))
        if not query:
            return [], 0, {"needsQuery": True}
        data = await _post_json(
            session,
            "https://ares.gov.cz/ekonomicke-subjekty-v-be/rest/ekonomicke-subjekty/vyhledat",
            {"obchodniJmeno": query, "start": page * page_size, "pocet": page_size},
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        records = _collect_records(data.get("ekonomickeSubjekty") or [], lambda item: _registry_entity_row(
            name=item.get("obchodniJmeno"),
            registration_number=item.get("ico"),
            jurisdiction="CZ",
            country="CZ",
            entity_type=item.get("pravniForma") or variables.get("pravniForma"),
            entity_status="ACTIVE",
            industry_code=(item.get("czNace") or [""])[0],
            incorporation_date=item.get("datumVzniku"),
            source="ARES_CZE",
            source_record_id=item.get("ico"),
            raw=item,
        ))
        return records, int(data.get("pocetCelkem") or 0), {}

    if suffix == "Nzl":
        headers = {"Accept": "application/json"}
        api_key = os.environ["NZBN_API_KEY"].strip()
        headers["Ocp-Apim-Subscription-Key"] = api_key
        data = await _get_json(session, "https://api.business.govt.nz/gateway/nzbn/v5/entities", params={
            "page-size": page_size,
            "page-number": page,
            "entity-status": _clean(variables.get("entityStatus") or "Registered"),
            "search-type": "all",
        }, headers=headers)
        records = _collect_records(data.get("items") or [], lambda item: _registry_entity_row(
            name=item.get("entityName"),
            registration_number=item.get("nzbn"),
            jurisdiction="NZ",
            country="NZ",
            entity_type=item.get("entityTypeDescription") or variables.get("entityType"),
            entity_status=item.get("entityStatusDescription") or "Registered",
            industry_code=item.get("industryClassificationCode"),
            incorporation_date=item.get("registrationDate"),
            source="MBIE_NZL",
            source_record_id=item.get("nzbn"),
            raw=item,
        ))
        return records, int(data.get("totalRecords") or 0), {}

    if suffix == "Che":
        auth = aiohttp.BasicAuth(os.environ["ZEFIX_USERNAME"].strip(), os.environ["ZEFIX_PASSWORD"].strip())
        data = await _post_json(session, "https://www.zefix.admin.ch/ZefixPublicREST/api/v1/company/search", {
            "offset": page * page_size,
            "maxEntries": page_size,
            "activeOnly": variables.get("activeOnly") is not False,
            **({"registryOffice": _clean(variables.get("canton"))} if variables.get("canton") else {}),
        }, headers={"Content-Type": "application/json", "Accept": "application/json", "Authorization": auth.encode()})
        items = _list_payload(data, "results", "items", "companies", "data")
        records = _collect_records(items, lambda item: _registry_entity_row(
            name=item.get("name"),
            registration_number=item.get("uid") or item.get("chid"),
            jurisdiction=f"CH-{_clean(item.get('canton'))}",
            country="CH",
            entity_type=item.get("legalFormId") or variables.get("legalForm"),
            entity_status=item.get("status") or "ACTIVE",
            industry_code=_clean(item.get("purpose"))[:10],
            incorporation_date=item.get("registrationDate"),
            source="ZEFIX_CHE",
            source_record_id=item.get("uid") or item.get("chid"),
            raw=item,
        ))
        total = data.get("total") if isinstance(data, dict) else len(records)
        return records, int(total or len(records)), {}

    if suffix == "Nld":
        headers = {"Accept": "application/json"}
        api_key = os.environ["KVK_API_KEY"].strip()
        headers["apikey"] = api_key
        params: dict[str, Any] = {"pagina": page + 1, "resultatenPerPagina": page_size}
        if variables.get("kvkNummer"):
            params["kvkNummer"] = _clean(variables.get("kvkNummer"))
        elif variables.get("handelsnaam"):
            params["handelsnaam"] = _clean(variables.get("handelsnaam"))
        else:
            params["handelsnaam"] = _clean(variables.get("query"))
        data = await _get_json(session, "https://api.kvk.nl/api/v1/zoeken", params=params, headers=headers)
        records = _collect_records(data.get("resultaten") or [], lambda item: _registry_entity_row(
            name=item.get("handelsnaam"),
            registration_number=item.get("kvkNummer"),
            jurisdiction="NL",
            country="NL",
            entity_type=item.get("type"),
            entity_status="ACTIVE",
            industry_code=((item.get("sbiActiviteiten") or [{}])[0]).get("sbiCode"),
            source="KVK_NLD",
            source_record_id=item.get("kvkNummer"),
            raw=item,
        ))
        return records, int(data.get("totaal") or 0), {}

    if suffix == "Isr":
        data = await _get_json(session, "https://data.gov.il/api/3/action/datastore_search", params={
            "resource_id": "f004176c-b85f-4542-8901-7b3176f9a054",
            "limit": page_size,
            "offset": page * page_size,
        })
        result = data.get("result") or {}
        records = _collect_records(result.get("records") or [], lambda item: _registry_entity_row(
            name=item.get("company_name") or item.get("company_name_eng"),
            registration_number=item.get("company_number"),
            jurisdiction="IL",
            country="IL",
            entity_type=item.get("company_type") or variables.get("companyType"),
            entity_status="ACTIVE" if item.get("company_status") == "active" else item.get("company_status") or variables.get("status") or "ACTIVE",
            incorporation_date=item.get("incorporation_date"),
            source="RASHAM_ISR",
            source_record_id=item.get("company_number"),
            raw=item,
        ))
        return records, int(result.get("total") or 0), {}

    raise ValueError(f"unknown country registry suffix: {suffix}")


async def _collect_country_registry(suffix: str, **kwargs: Any) -> dict[str, Any]:
    meta = _REGISTRY_TASKS[suffix]
    pages = max(1, min(int(kwargs.get("pages") or 5), 50))
    default_page_size = 500 if suffix == "Jpn" else 100
    page_size_max = 1000 if suffix in {"Fra", "Dnk"} else default_page_size
    page_size = max(1, min(int(kwargs.get("pageSize") or default_page_size), page_size_max))
    start_page = int(kwargs.get("startPage") or 0)
    if suffix in {"Jpn", "Nzl"}:
        start_page = max(1, start_page or 1)
    total_inserted = 0
    total_skipped = 0
    total_errors = 0
    api_total = 0
    first_error = ""
    dry_run = bool(kwargs.get("dryRun"))
    missing_env = _missing_env(suffix)
    if missing_env:
        return _config_error_result(
            suffix,
            pages=pages,
            page_size=page_size,
            start_page=start_page,
            dry_run=dry_run,
            missing_env=missing_env,
        )
    missing_query = _missing_query(suffix, kwargs)
    if missing_query:
        return _config_error_result(
            suffix,
            pages=pages,
            page_size=page_size,
            start_page=start_page,
            dry_run=dry_run,
            missing_query=missing_query,
        )
    if suffix == "Nor" and (start_page + pages) * page_size > 10_000:
        return _simple_error_result(
            suffix,
            pages=pages,
            page_size=page_size,
            start_page=start_page,
            dry_run=dry_run,
            first_error="Norway Bronnoysund page window exceeds 10000 result limit",
            extra={"maxPageWindow": 10_000},
        )
    page_results: list[dict[str, Any]] = []
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=45)) as session:
        for page in range(start_page, start_page + pages):
            try:
                fetched = await _fetch_country_registry_page(session, suffix, page, page_size, kwargs)
                records, page_total, page_meta = fetched
                api_total = page_total or api_total
                if not records:
                    page_results.append({
                        "page": page,
                        "ok": True,
                        "submitted": 0,
                        "inserted": 0,
                        "skipped": 0,
                        **page_meta,
                    })
                    break
                if dry_run:
                    inserted, skipped, errors, err = 0, 0, 0, ""
                else:
                    inserted, skipped, errors, err = _insert_many_entities(records)
                total_inserted += inserted
                total_skipped += skipped
                total_errors += errors
                first_error = first_error or err
                page_results.append({
                    "page": page,
                    "ok": not err,
                    "submitted": len(records),
                    "inserted": inserted,
                    "skipped": skipped,
                    "errors": errors,
                    "dryRun": dry_run,
                    **page_meta,
                })
            except Exception as e:  # noqa: BLE001
                first_error = first_error or str(e)[:300]
                total_errors += 1
                page_results.append({"page": page, "ok": False, "error": str(e)[:300]})
                break
    return {
        "result": {
            "ok": not first_error,
            "source": meta["source"],
            "country": meta["country"],
            "registry": meta["label"],
            "pagesProcessed": len(page_results),
            "pageSize": page_size,
            "startPage": start_page,
            "totalInserted": total_inserted,
            "totalSkipped": total_skipped,
            "totalErrors": total_errors,
            "apiTotal": api_total,
            "firstError": first_error,
            "pages": page_results,
            "dryRun": dry_run,
            "ts": _utc_now(),
        }
    }


def _make_registry_task(suffix: str) -> Any:
    async def _task(**kwargs: Any) -> dict[str, Any]:
        return await _collect_country_registry(suffix, **kwargs)

    _task.__name__ = f"task_registry_collect_{suffix.lower()}"
    return _task


def _selected_registry_suffixes(registry_suffixes: list[str] | tuple[str, ...] | None) -> list[str]:
    if not registry_suffixes:
        return list(_REGISTRY_TASKS)

    selected: list[str] = []
    for suffix in registry_suffixes:
        normalized = suffix.strip()
        if not normalized:
            continue
        normalized = normalized[:1].upper() + normalized[1:].lower()
        if normalized not in _REGISTRY_TASKS:
            raise ValueError(f"unknown legal entity registry suffix: {suffix!r}")
        selected.append(normalized)
    return selected


def register(
    worker: Any,
    timeout_ms: int = 180_000,
    max_jobs_to_activate: int | None = None,
    max_running_jobs: int | None = None,
    registry_suffixes: list[str] | tuple[str, ...] | None = None,
    include_gleif: bool = True,
    include_edgar: bool = True,
) -> None:
    task_options = {"single_value": False, "timeout_ms": timeout_ms}
    if max_jobs_to_activate is not None:
        task_options["max_jobs_to_activate"] = max_jobs_to_activate
    if max_running_jobs is not None:
        task_options["max_running_jobs"] = max_running_jobs

    if include_gleif:
        worker.task(task_type="legalEntity.gleif.fetchPages", **task_options)(task_gleif_fetch_pages)
        worker.task(task_type="legalEntity.gleif.registerDids", **task_options)(task_gleif_register_dids)
    if include_edgar:
        worker.task(task_type="legalEntity.edgar.collectUsa", **task_options)(task_edgar_collect_usa)
        worker.task(task_type="legalEntity.edgar.ingestSecDisclosure", **task_options)(task_edgar_ingest_sec_disclosure)
    selected = set(_selected_registry_suffixes(registry_suffixes))
    if "Jpn" in selected:
        worker.task(task_type="legalEntity.registry.collectJpn", **task_options)(_make_registry_task("Jpn"))
    if "Gbr" in selected:
        worker.task(task_type="legalEntity.registry.collectGbr", **task_options)(_make_registry_task("Gbr"))
    if "Fra" in selected:
        worker.task(task_type="legalEntity.registry.collectFra", **task_options)(_make_registry_task("Fra"))
    if "Nor" in selected:
        worker.task(task_type="legalEntity.registry.collectNor", **task_options)(_make_registry_task("Nor"))
    if "Dnk" in selected:
        worker.task(task_type="legalEntity.registry.collectDnk", **task_options)(_make_registry_task("Dnk"))
    if "Fin" in selected:
        worker.task(task_type="legalEntity.registry.collectFin", **task_options)(_make_registry_task("Fin"))
    if "Est" in selected:
        worker.task(task_type="legalEntity.registry.collectEst", **task_options)(_make_registry_task("Est"))
    if "Cze" in selected:
        worker.task(task_type="legalEntity.registry.collectCze", **task_options)(_make_registry_task("Cze"))
    if "Nzl" in selected:
        worker.task(task_type="legalEntity.registry.collectNzl", **task_options)(_make_registry_task("Nzl"))
    if "Che" in selected:
        worker.task(task_type="legalEntity.registry.collectChe", **task_options)(_make_registry_task("Che"))
    if "Nld" in selected:
        worker.task(task_type="legalEntity.registry.collectNld", **task_options)(_make_registry_task("Nld"))
    if "Isr" in selected:
        worker.task(task_type="legalEntity.registry.collectIsr", **task_options)(_make_registry_task("Isr"))
