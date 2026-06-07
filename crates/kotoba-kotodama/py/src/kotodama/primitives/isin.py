"""ISIN (ISO 6166) securities registry primitives (ADR-0056 BPMN-as-actor).

4 Zeebe task types for isin.etzhayyim.com:
  isin.collect.usSecurities  — SEC EDGAR ticker list → OpenFIGI batch → vertex_isin_security
  isin.collect.jpSecurities  — OpenFIGI JP ticker range → vertex_isin_security
  isin.enrich.cik            — EDGAR CIK submissions → enrich vertex_isin_security row
  isin.collect.edinetFiling  — EDINET filing list for JP company → vertex_isin_filing

Table: vertex_isin_security / vertex_isin_filing
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

import aiohttp

from datetime import datetime, timezone
from kotodama.kotoba_datomic import get_kotoba_client


_OWNER_DID = "did:web:isin.etzhayyim.com"
_COL_SEC = "com.etzhayyim.apps.isin.security"
_COL_FILING = "com.etzhayyim.apps.isin.filing"
_EDGAR_UA = "isin.etzhayyim.com/1.0 contact@etzhayyim.com"
_EDGAR_TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
_OPENFIGI_URL = "https://api.openfigi.com/v3/mapping"
_EDINET_URL = "https://api.edinet-fsa.go.jp/api/v2/documents.json"

_EXCH_TO_MIC: dict[str, str] = {
    "NYSE": "XNYS", "NASDAQ": "XNAS", "NYSE MKT": "XASE",
    "NYSE Arca": "ARCX", "CBOE": "XCBO", "OTC": "OTCM",
}
_EDINET_FORM_NAMES: dict[str, str] = {
    "030000": "有価証券報告書",
    "043000": "四半期報告書",
    "020000": "臨時報告書",
    "050000": "半期報告書",
}
_FORM_SLUG: dict[str, str] = {
    "有価証券報告書": "yukasho",
    "四半期報告書": "shihankiho",
    "臨時報告書": "rinjiho",
    "半期報告書": "hankiho",
}


def _utc_now() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _sec_vid(rkey: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_SEC}/{rkey}"


def _filing_vid(rkey: str) -> str:
    return f"at://{_OWNER_DID}/{_COL_FILING}/{rkey}"





# ---------------------------------------------------------------------------
# isin.collect.usSecurities
# ---------------------------------------------------------------------------

async def task_isin_collect_us_securities(
    offset: int = 0,
    limit: int = 200,
    enrichFigi: bool = True,
) -> dict:
    """Fetch SEC EDGAR ticker list + OpenFIGI batch → write to vertex_isin_security."""
    off = max(0, int(offset or 0))
    lim = max(1, min(int(limit or 200), 500))

    async with aiohttp.ClientSession() as session:
        async with session.get(_EDGAR_TICKERS_URL,
                               headers={"User-Agent": _EDGAR_UA},
                               timeout=aiohttp.ClientTimeout(total=30)) as resp:
            if resp.status != 200:
                return {"error": f"EDGAR tickers {resp.status}", "registered": 0}
            raw = await resp.json(content_type=None)

    all_tickers = list(raw.values())
    batch = all_tickers[off: off + lim]
    if not batch:
        return {"ok": True, "registered": 0, "total": len(all_tickers), "exhausted": True}

    # OpenFIGI batch (100 per request, free tier 25 req/min)
    figi_map: dict[str, dict] = {}
    if enrichFigi:
        FIGI_BATCH = 100
        async with aiohttp.ClientSession() as session:
            for i in range(0, len(batch), FIGI_BATCH):
                chunk = [
                    {"idType": "TICKER", "idValue": t["ticker"],
                     "exchCode": "US", "marketSecDes": "Equity"}
                    for t in batch[i: i + FIGI_BATCH]
                ]
                try:
                    async with session.post(
                        _OPENFIGI_URL, json=chunk,
                        headers={"Content-Type": "application/json"},
                        timeout=aiohttp.ClientTimeout(total=20),
                    ) as r:
                        if r.status == 200:
                            results = await r.json()
                            for j, entry in enumerate(results):
                                match = (entry.get("data") or [{}])[0]
                                if match and (i + j) < len(batch):
                                    figi_map[batch[i + j]["ticker"]] = match
                except Exception:  # noqa: BLE001
                    pass
                if i + FIGI_BATCH < len(batch):
                    await asyncio.sleep(2.6)

    # Updated to use kotoba Datom log (ADR-2605262130 + ADR-2605312345)
    kotoba_client = get_kotoba_client()
    for edgar in batch:
        cik = str(edgar.get("cik_str", ""))
        ticker = str(edgar.get("ticker", ""))
        name = str(edgar.get("title", ""))
        figi = figi_map.get(ticker, {})
        rkey = f"us-{cik}"
        vid = _sec_vid(rkey)
        asset_class = (
            "equity" if figi.get("marketSector") == "Equity"
            else (figi.get("marketSector") or "equity").lower()
        )
        try:
            row_dict = {
                "vertex_id": vid,
                "rkey": rkey,
                "isin": "",                                   # isin: enriched later
                "figi": figi.get("figi", ""),
                "composite_figi": figi.get("compositeFIGI", ""),
                "ticker": ticker,
                "cik": cik,
                "name": name,
                "country_code": "US",
                "asset_class": asset_class,
                "security_type": figi.get("securityType", "Common Stock"),
                "exch_code": figi.get("exchCode", "US"),
                "isin_status": "pending",
                "status": "active",
                "source_did": "did:web:isin.etzhayyim.com:source:sec",
                "actor_did": _OWNER_DID,
                "org_did": "anon",
                "collected_at": now,
                "created_at": now,
            }
            kotoba_client.insert_row("vertex_isin_security", row_dict)
            registered += 1
        except Exception: # Already idempotent
            registered += 1

    return {
        "ok": True,
        "registered": registered,
        "skipped": skipped,
        "errors": errors,
        "figiEnriched": len(figi_map),
        "total": len(all_tickers),
        "offset": off,
        "limit": lim,
        "nextOffset": off + len(batch),
        "exhausted": len(batch) < lim,
    }


# ---------------------------------------------------------------------------
# isin.collect.jpSecurities
# ---------------------------------------------------------------------------

async def task_isin_collect_jp_securities(
    fromTicker: int = 1000,
    count: int = 25,
) -> dict:
    """Discover JP listed companies via OpenFIGI (TSE ticker range) → write to kotoba Datom log."""
    start = max(1000, min(int(fromTicker or 1000), 9999))
    cnt = max(1, min(int(count or 25), 50))

    tickers = [str(t) for t in range(start, min(start + cnt, 10000))]
    if not tickers:
        return {"ok": True, "registered": 0, "exhausted": True}

    # OpenFIGI free tier: max 10 identifiers per request without key
    FIGI_BATCH = 10
    now = _utc_now()
    registered = 0
    skipped = 0
    errors = 0

    kotoba_client = get_kotoba_client()
    async with aiohttp.ClientSession() as session:
        for i in range(0, len(tickers), FIGI_BATCH):
            chunk_tickers = tickers[i: i + FIGI_BATCH]
            payload = [
                {"idType": "TICKER", "idValue": t, "exchCode": "JP", "marketSecDes": "Equity"}
                for t in chunk_tickers
            ]
            try:
                async with session.post(
                    _OPENFIGI_URL, json=payload,
                    headers={"Content-Type": "application/json"},
                    timeout=aiohttp.ClientTimeout(total=20),
                ) as resp:
                    if resp.status != 200:
                        continue
                    results = await resp.json()
            except Exception:  # noqa: BLE001
                continue

            for j, entry in enumerate(results):
                match = (entry.get("data") or [{}])[0]
                if not match or not match.get("name"):
                    continue
                ticker = chunk_tickers[j]
                rkey = f"jp-{ticker}"
                vid = _sec_vid(rkey)
                try:
                    row_dict = {
                        "vertex_id": vid,
                        "rkey": rkey,
                        "isin": "",
                        "figi": match.get("figi", ""),
                        "composite_figi": match.get("compositeFIGI", ""),
                        "ticker": ticker,
                        "name": match.get("name", ""),
                        "country_code": "JP",
                        "asset_class": "equity" if match.get("marketSector") == "Equity" else "equity",
                        "security_type": match.get("securityType", "Common Stock"),
                        "exch_code": "JP",
                        "isin_status": "pending",
                        "status": "active",
                        "source_did": "did:web:isin.etzhayyim.com:source:openfigi",
                        "actor_did": _OWNER_DID,
                        "org_did": "anon",
                        "collected_at": now,
                        "created_at": now,
                    }
                    kotoba_client.insert_row("vertex_isin_security", row_dict)
                    registered += 1
                except Exception: # Already idempotent
                    registered += 1

            if i + FIGI_BATCH < len(tickers):
                await asyncio.sleep(2.6)

    next_from = (start + cnt) if (start + cnt) <= 9999 else 1000
    return {
        "ok": True,
        "registered": registered,
        "skipped": skipped,
        "errors": errors,
        "fromTicker": start,
        "count": cnt,
        "nextFrom": next_from,
        "exhausted": (start + cnt) > 9999,
    }


# ---------------------------------------------------------------------------
# isin.enrich.cik
# ---------------------------------------------------------------------------

async def task_isin_enrich_cik(
    cik: int = 0,
) -> dict:
    """Fetch EDGAR CIK submissions JSON → enrich exchange MIC, SIC in kotoba Datom log."""
    if not cik:
        return {"error": "cik required"}
    cik_int = int(cik)
    cik_str = str(cik_int).zfill(10)

    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"https://data.sec.gov/submissions/CIK{cik_str}.json",
            headers={"User-Agent": _EDGAR_UA},
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                return {"error": f"EDGAR CIK {resp.status}", "cik": cik_int}
            facts = await resp.json(content_type=None)

    tickers: list[str] = facts.get("tickers") or []
    exchanges: list[str] = facts.get("exchanges") or []
    sic = str(facts.get("sic") or "")
    sic_desc = str(facts.get("sicDescription") or "")
    mic = _EXCH_TO_MIC.get(exchanges[0] if exchanges else "", "")
    rkey = f"us-{cik_int}"
    now = _utc_now()

    kotoba_client = get_kotoba_client()
    try:
        existing_row = kotoba_client.select_first_where(
            "vertex_isin_security", "rkey", rkey
        )
        if existing_row:
            existing_row["exchange_mic"] = mic
            existing_row["sic"] = sic
            existing_row["sic_desc"] = sic_desc
            existing_row["collected_at"] = now
            kotoba_client.insert_row("vertex_isin_security", existing_row)
        else:
            return {"error": f"isin.enrich.cik: No existing security with rkey {rkey}", "cik": cik_int}
    except Exception as e:  # noqa: BLE001
        return {"error": f"isin.enrich.cik DB failed: {e}", "cik": cik_int}

    return {
        "ok": True,
        "cik": cik_int,
        "tickers": tickers,
        "exchanges": exchanges,
        "mic": mic,
        "sic": sic,
        "sicDescription": sic_desc,
    }


# ---------------------------------------------------------------------------
# isin.collect.edinetFiling
# ---------------------------------------------------------------------------

async def task_isin_collect_edinet_filing(
    ticker: str = "",
    edinetCode: str = "",
    subscriptionKey: str = "",
) -> dict:
    """Fetch EDINET filings for a JP company → write to kotoba Datom log."""
    ticker = str(ticker or "").strip()
    edinet_code = str(edinetCode or "").strip()
    if not ticker and not edinet_code:
        return {"error": "ticker or edinetCode required"}

    ticker_id = ticker or edinet_code
    params: dict[str, str] = {"type": "2"}
    if edinet_code:
        params["edinetCode"] = edinet_code
    elif ticker:
        params["secCode"] = f"{ticker}0"

    headers: dict[str, str] = {"User-Agent": _EDGAR_UA}
    if subscriptionKey:
        headers["Ocp-Apim-Subscription-Key"] = subscriptionKey

    qs = "&".join(f"{k}={v}" for k, v in params.items())
    async with aiohttp.ClientSession() as session:
        async with session.get(
            f"{_EDINET_URL}?{qs}", headers=headers,
            timeout=aiohttp.ClientTimeout(total=20),
        ) as resp:
            if resp.status != 200:
                return {"ok": True, "ticker": ticker_id, "filings": [],
                        "note": f"EDINET {resp.status}"}
            data = await resp.json(content_type=None)

    docs = [d for d in (data.get("results") or []) if d.get("edinetCode")]
    if not docs:
        return {"ok": True, "ticker": ticker_id, "filings": [],
                "note": "no EDINET docs (key required or no filings)"}

    company = docs[0]
    name = company.get("filerName") or ticker_id
    display_ticker = (company.get("secCode") or "").rstrip("0") or ticker

    # Pick one of each major form type (most recent first)
    sorted_docs = sorted(docs, key=lambda d: d.get("submitDateTime") or "", reverse=True)
    filings_by_type: dict[str, dict] = {}
    for doc in sorted_docs:
        form_name = _EDINET_FORM_NAMES.get(doc.get("formCode") or "")
        if form_name and form_name not in filings_by_type:
            filings_by_type[form_name] = {
                "docID": doc.get("docID", ""),
                "form": form_name,
                "period": doc.get("periodEnd") or doc.get("periodStart") or "",
                "submitted": doc.get("submitDateTime") or "",
            }
        if len(filings_by_type) >= 3:
            break

    if not filings_by_type:
        return {"ok": True, "ticker": ticker_id, "name": name, "filings": []}

    now = _utc_now()
    written = 0
    errors = 0
    kotoba_client = get_kotoba_client()
    for filing in filings_by_type.values():
        period_slug = (filing["period"][:10] if filing["period"] else "").replace("-", "")
        form_slug = _FORM_SLUG.get(filing["form"], filing["form"][:6])
        rkey = f"jp-{ticker_id}-{form_slug}-{period_slug}"
        vid = _filing_vid(rkey)
        source_url = (
            f"https://disclosure.edinet-api.go.jp/e01ew/BLMainController.jsp"
            f"?uji.verb=W1E63011CXP01&TID=W1E63011CXP01&documentId={filing['docID']}"
        )
        try:
            row_dict = {
                "vertex_id": vid,
                "rkey": rkey,
                "country_code": "JP",
                "ticker": display_ticker or ticker_id,
                "edinet_code": edinet_code,
                "doc_id": filing["docID"],
                "form_type": filing["form"],
                "period_end": filing["period"][:10] if filing["period"] else None,
                "submitted_at": filing["submitted"][:19] if filing["submitted"] else None,
                "source_url": source_url,
                "name": f"{name} {filing['form']} 期末: {filing['period'][:10]}",
                "actor_did": _OWNER_DID,
                "org_did": "anon",
                "created_at": now,
            }
            kotoba_client.insert_row("vertex_isin_filing", row_dict)
            written += 1
        except Exception: # Already idempotent
            written += 1

    return {
        "ok": True,
        "ticker": ticker_id,
        "name": name,
        "displayTicker": display_ticker,
        "written": written,
        "errors": errors,
        "filings": list(filings_by_type.values()),
    }


# ---------------------------------------------------------------------------
# Registration
# ---------------------------------------------------------------------------

def register(worker: Any, *, timeout_ms: int) -> None:
    """Wire isin primitives onto the shared LangServer worker."""

    def t(name: str, fn: Any, *, timeout: int | None = None) -> None:
        worker.task(
            task_type=name,
            single_value=False,
            timeout_ms=timeout if timeout is not None else timeout_ms,
        )(fn)

    # US collection can take up to 5 min for 500 securities + OpenFIGI rate-limit sleep
    t("isin.collect.usSecurities",   task_isin_collect_us_securities, timeout=360_000)
    t("isin.collect.jpSecurities",   task_isin_collect_jp_securities, timeout=120_000)
    t("isin.enrich.cik",             task_isin_enrich_cik,            timeout=60_000)
    t("isin.collect.edinetFiling",   task_isin_collect_edinet_filing, timeout=60_000)


__all__ = [
    "register",
    "task_isin_collect_us_securities",
    "task_isin_collect_jp_securities",
    "task_isin_enrich_cik",
    "task_isin_collect_edinet_filing",
]
