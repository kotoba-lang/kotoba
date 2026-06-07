"""Onion (.onion / Tor) darkweb crawl primitives for BPMN/LangServer.

Zeebe owns cadence (`crawlSeeds.bpmn`, R/PT6H). This module owns the Python
worker side: pick stale seeds → fetch via `darkweb-proxy.etzhayyim.com/fetch`
(Tor + Playwright CF Container) → classify → write `vertex_onion_*` rows
directly via RW so the onion appview keeps its current Kysely read path.

Replaces the legacy onion CF Worker XRPC-on-demand crawl path
(`60-apps/etzhayyim-project-onion/wasm/.../src/app.ts`) with a scheduled,
durable Zeebe worker per ADR-0056.
"""

from __future__ import annotations

import datetime
from datetime import datetime, timezone
import hashlib
import html
import json
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from kotodama.kotoba_datomic import get_kotoba_client


OWNER_DID = "did:web:onion.etzhayyim.com"
ACTOR_ID = "sys.langserver.onion.crawl"
DARKWEB_PROXY_URL = "https://darkweb-proxy.etzhayyim.com/fetch"
DEFAULT_TIMEOUT_SEC = 45.0
STALE_SEED_MAX_AGE_SEC = 6 * 60 * 60  # 6h — match BPMN cadence
MAX_INTERNAL_LINKS = 5  # BFS depth-1 cap, mirrors legacy Worker

THREAT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "marketplace": ("market", "vendor", "escrow", "btc", "monero", "xmr"),
    "drugs": ("drug", "cocaine", "heroin", "mdma", "lsd", "meth"),
    "weapons": ("weapon", "firearm", "ammo", "ammunition", "rifle"),
    "fraud": ("carding", "cvv", "fullz", "dump", "skimmer", "phishing"),
    "ransomware": ("ransomware", "leak site", "victim", "decryptor", "negotiat"),
    "csam": ("cp ", "child", "loli", "preteen"),  # surface only — never enrich
    "hacking": ("exploit", "0day", "rat ", "botnet", "stresser", "ddos"),
}


# ─── helpers ─────────────────────────────────────────────────────────────


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def _today() -> str:
    return _utc_now()[:10]


def _sha(prefix: str, *parts: Any) -> str:
    raw = "\x1f".join(str(p or "") for p in parts)
    return f"{prefix}-{hashlib.sha256(raw.encode('utf-8')).hexdigest()[:24]}"


def _onion_host_from_url(url: str) -> str:
    try:
        host = urllib.parse.urlparse(url).hostname or ""
    except ValueError:
        return ""
    return host.lower()


def _onion_slug(host: str) -> str:
    base = host[: -len(".onion")] if host.endswith(".onion") else host
    return base or _sha("h", host)


def _site_vid(host: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.onion.site/{_onion_slug(host)}"


def _page_vid(url: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.onion.page/{_sha('p', url)}"


def _crawl_vid(host: str, started_at: str) -> str:
    return f"at://{OWNER_DID}/com.etzhayyim.apps.onion.crawl/{_onion_slug(host)}-{_sha('s', host, started_at)}"


def _site_did(host: str) -> str:
    return f"did:web:onion.etzhayyim.com:{_onion_slug(host)}"


def _clean_text(value: str, limit: int) -> str:
    text = html.unescape(value or "")
    text = re.sub(r"<script[\s\S]*?</script>", " ", text, flags=re.I)
    text = re.sub(r"<style[\s\S]*?</style>", " ", text, flags=re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def _extract_title(raw: str) -> str:
    match = re.search(r"<title[^>]*>([\s\S]*?)</title>", raw, flags=re.I)
    if match:
        return _clean_text(match.group(1), 240)
    h1 = re.search(r"<h1[^>]*>([\s\S]*?)</h1>", raw, flags=re.I)
    if h1:
        return _clean_text(h1.group(1), 240)
    return ""


def _extract_links(raw: str, base_url: str) -> list[str]:
    base_host = _onion_host_from_url(base_url)
    out: list[str] = []
    seen: set[str] = set()
    for m in re.finditer(r'href=["\']([^"\']+)["\']', raw, flags=re.I):
        href = m.group(1).strip()
        if not href or href.startswith("#") or href.startswith("javascript:"):
            continue
        try:
            absu = urllib.parse.urljoin(base_url, href)
        except ValueError:
            continue
        host = _onion_host_from_url(absu)
        if not host.endswith(".onion") or host != base_host:
            continue
        if absu in seen:
            continue
        seen.add(absu)
        out.append(absu)
        if len(out) >= MAX_INTERNAL_LINKS:
            break
    return out


def _classify(text: str) -> dict[str, Any]:
    lower = text.lower()
    found: list[str] = []
    category_scores: dict[str, int] = {}
    for cat, kws in THREAT_KEYWORDS.items():
        hits = sum(1 for kw in kws if kw in lower)
        if hits:
            category_scores[cat] = hits
            found.extend(kw for kw in kws if kw in lower)
    top_category = max(category_scores, key=lambda c: category_scores[c]) if category_scores else "unknown"
    risk = min(100, (20 + 8 * len(set(found))) if found else 0)
    return {"category": top_category, "threatIndicators": sorted(set(found)), "riskScore": risk}


# ─── HTTP fetch via darkweb-proxy ───────────────────────────────────────


def _fetch_via_proxy(url: str, timeout_sec: float) -> dict[str, Any]:
    body = json.dumps({"url": url, "timeout": int(timeout_sec * 1000)}).encode("utf-8")
    req = urllib.request.Request(
        DARKWEB_PROXY_URL,
        data=body,
        headers={
            "Content-Type": "application/json",
            "User-Agent": "kotodama-onion-crawl/1 (+https://onion.etzhayyim.com)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec + 5.0) as resp:
            raw = resp.read(2_000_000)
            payload = json.loads(raw.decode("utf-8", errors="replace") or "{}")
            return {
                "ok": True,
                "statusCode": int(payload.get("statusCode") or 0),
                "html": str(payload.get("html") or ""),
                "title": str(payload.get("title") or ""),
                "outboundLinks": list(payload.get("outboundLinks") or []),
                "error": str(payload.get("error") or ""),
            }
    except urllib.error.HTTPError as e:
        body = e.read(200_000)
        return {"ok": False, "statusCode": int(e.code), "html": "", "title": "", "outboundLinks": [], "error": f"http {e.code}: {body[:200]!r}"}
    except Exception as e:  # noqa: BLE001
        return {"ok": False, "statusCode": 0, "html": "", "title": "", "outboundLinks": [], "error": f"transport: {e}"}


# ─── DB writes ──────────────────────────────────────────────────────────


def _insert_ignore(table: str, row: dict[str, Any]) -> int:
    """Kotoba Datom log plain INSERT. Same-PK re-insert upserts."""
    get_kotoba_client().insert_row(table, row)
    return 1 # Assume 1 row processed for simplicity, as it's an upsert operation


def _update_site(host: str, *, last_seen: str, page_count_inc: int, reachable: bool, category: str | None, risk_score: int | None) -> None:
    vid = _site_vid(host)
    # R0: Replaced SQL UPDATE with select_first_where + in-Python update + insert_row for upsert
    kotoba_client = get_kotoba_client()
    existing_site = kotoba_client.select_first_where("vertex_onion_site", "vertex_id", vid)

    if existing_site:
        existing_site["last_seen"] = last_seen
        existing_site["page_count"] = (existing_site.get("page_count") or 0) + page_count_inc
        existing_site["reachable"] = reachable
        if category is not None:
            existing_site["category"] = category
        if risk_score is not None:
            existing_site["risk_score"] = max(existing_site.get("risk_score") or 0, risk_score)
        kotoba_client.insert_row("vertex_onion_site", existing_site)
    else:
        # If site doesn't exist, this implies a potential race condition or data inconsistency.
        # For now, we'll re-ensure the site if it wasn't found, though it should ideally exist
        # before an update is attempted. This might create a new entry with partial data.
        # A more robust solution might involve logging or raising an error.
        _ensure_site(host, started_at=last_seen, category=category)



def _ensure_site(host: str, *, started_at: str, category: str | None) -> str:
    vid = _site_vid(host)
    _insert_ignore("vertex_onion_site", {
        "vertex_id": vid,
        "onion_host": host,
        "node_id": f"onion:site:{host}",
        "title": None,
        "category": category or None,
        "risk_score": 0,
        "reachable": True,
        "page_count": 0,
        "first_seen": started_at,
        "last_seen": started_at,
        "site_did": _site_did(host),
        "mirror_clearnet": None,
        "threat_actor_ref": None,
        "owner_did": OWNER_DID,
        "created_date": _today(),
    })
    return vid


def _write_crawl(host: str, *, session_id: str, started_at: str, finished_at: str, page_count: int, error_count: int, reachable: bool, error_msg: str | None) -> str:
    vid = _crawl_vid(host, started_at)
    _insert_ignore("vertex_onion_crawl", {
        "vertex_id": vid,
        "onion_host": host,
        "session_id": session_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "page_count": page_count,
        "error_count": error_count,
        "reachable": reachable,
        "error_msg": (error_msg or None),
        "owner_did": OWNER_DID,
        "created_date": _today(),
    })
    return vid


def _write_page(*, url: str, host: str, fetched: dict[str, Any], crawled_at: str, site_node_id: str) -> tuple[bool, dict[str, Any]]:
    text = _clean_text(fetched.get("html") or "", 4000)
    title = (fetched.get("title") or "").strip() or _extract_title(fetched.get("html") or "")
    links = fetched.get("outboundLinks") or _extract_links(fetched.get("html") or "", url)
    classify = _classify(f"{title}\n{text}")
    content_hash = hashlib.sha256((fetched.get("html") or "").encode("utf-8")).hexdigest() if fetched.get("html") else None
    inserted = _insert_ignore("vertex_onion_page", {
        "vertex_id": _page_vid(url),
        "onion_url": url,
        "onion_host": host,
        "title": title[:240] if title else None,
        "content_hash": content_hash,
        "content_blob_cid": None,
        "screenshot_blob_cid": None,
        "status_code": int(fetched.get("statusCode") or 0),
        "language": None,
        "text_snippet": text[:1000] if text else None,
        "outbound_links": json.dumps(links[:MAX_INTERNAL_LINKS]) if links else None,
        "threat_indicators": json.dumps(classify["threatIndicators"]) if classify["threatIndicators"] else None,
        "risk_score": int(classify["riskScore"]),
        "category": classify["category"],
        "crawled_at": crawled_at,
        "site_node_id": site_node_id,
        "owner_did": OWNER_DID,
        "created_date": _today(),
    })
    return bool(inserted), {"category": classify["category"], "riskScore": int(classify["riskScore"]), "links": links[:MAX_INTERNAL_LINKS]}


# ─── Seed selection ─────────────────────────────────────────────────────


def _claim_stale_seeds(limit: int) -> list[dict[str, Any]]:
    """Pick the stalest reachable sites in vertex_onion_site that haven't
    been re-crawled within STALE_SEED_MAX_AGE_SEC. Returns a list of
    {url, host, category} dicts. Each becomes one seed for processQueue."""
    cutoff = datetime.now(timezone.utc) - datetime.timedelta(seconds=STALE_SEED_MAX_AGE_SEC)
    cutoff_iso = cutoff.replace(microsecond=0).isoformat().replace("+00:00", "Z")

    # R0: Multi-predicate / ORDER BY / LIMIT handled in Python
    kotoba_client = get_kotoba_client()
    potential_seeds = kotoba_client.select_where(
        "vertex_onion_site",
        "reachable",
        True,
        columns=["onion_host", "category", "last_seen"]
    )

    # Filter onion_host IS NOT NULL and (last_seen IS NULL OR last_seen < cutoff_iso)
    filtered_seeds = [
        s for s in potential_seeds
        if s.get("onion_host") is not None and
           (s.get("last_seen") is None or s.get("last_seen") < cutoff_iso)
    ]

    # Order by last_seen NULLS FIRST
    # Python's sort handles None values by placing them before other values by default
    # if None is considered "less" than other comparable values, or after if "greater".
    # We want NULLS FIRST, so we'll sort based on last_seen directly.
    # Note: Datetime strings can be compared lexicographically.
    filtered_seeds.sort(key=lambda x: x.get("last_seen") or "") # Sorts None (which becomes empty string) first

    # Apply limit
    rows = filtered_seeds[:limit]

    return [
        {"url": f"http://{r['onion_host']}/", "host": str(r["onion_host"]), "category": r.get("category")}
        for r in rows
        if r.get("onion_host")
    ]


def _normalize_explicit_seeds(raw: list[Any], category: str | None) -> tuple[list[dict[str, Any]], int]:
    out: list[dict[str, Any]] = []
    skipped = 0
    seen: set[str] = set()
    for entry in raw:
        if isinstance(entry, str):
            url = entry.strip()
        elif isinstance(entry, dict):
            url = str(entry.get("url") or "").strip()
        else:
            skipped += 1
            continue
        if not url:
            skipped += 1
            continue
        host = _onion_host_from_url(url)
        if not host.endswith(".onion"):
            skipped += 1
            continue
        if url in seen:
            skipped += 1
            continue
        seen.add(url)
        out.append({"url": url, "host": host, "category": category or (entry.get("category") if isinstance(entry, dict) else None)})
    return out, skipped


# ─── BPMN tasks ─────────────────────────────────────────────────────────


def queue_seeds(*, seeds: Any = None, category: str | None = None, limit: int = 10) -> dict[str, Any]:
    cap = max(1, min(int(limit or 10), 50))
    explicit = seeds if isinstance(seeds, list) else []
    runs, skipped = _normalize_explicit_seeds(explicit, category)
    if len(runs) < cap:
        for stale in _claim_stale_seeds(cap - len(runs)):
            if stale["url"] in {r["url"] for r in runs}:
                continue
            runs.append(stale)
            if len(runs) >= cap:
                break
    return {"queued": len(runs), "skipped": skipped, "runs": runs[:cap]}


def process_queue(*, runs: Any = None, timeout_sec: float = DEFAULT_TIMEOUT_SEC) -> dict[str, Any]:
    items = runs if isinstance(runs, list) else []
    timeout = max(5.0, min(float(timeout_sec or DEFAULT_TIMEOUT_SEC), 60.0))
    processed = 0
    completed = 0
    failed = 0
    pages_written = 0
    for raw in items:
        if not isinstance(raw, dict):
            failed += 1
            continue
        url = str(raw.get("url") or "").strip()
        host = str(raw.get("host") or _onion_host_from_url(url))
        category = raw.get("category")
        if not url or not host.endswith(".onion"):
            failed += 1
            continue
        processed += 1
        started_at = _utc_now()
        session_id = _sha("sess", host, started_at)
        site_node_id = f"onion:site:{host}"
        _ensure_site(host, started_at=started_at, category=category)

        seed_fetched = _fetch_via_proxy(url, timeout)
        if not seed_fetched["ok"] or not seed_fetched.get("html"):
            _update_site(host, last_seen=started_at, page_count_inc=0, reachable=False, category=category, risk_score=None)
            _write_crawl(
                host,
                session_id=session_id,
                started_at=started_at,
                finished_at=_utc_now(),
                page_count=0,
                error_count=1,
                reachable=False,
                error_msg=seed_fetched.get("error") or "unreachable",
            )
            failed += 1
            continue

        page_count = 0
        error_count = 0
        ok, info = _write_page(url=url, host=host, fetched=seed_fetched, crawled_at=started_at, site_node_id=site_node_id)
        if ok:
            page_count += 1
            pages_written += 1
        _update_site(host, last_seen=started_at, page_count_inc=1 if ok else 0, reachable=True, category=info.get("category") or category, risk_score=info.get("riskScore"))

        for link in info.get("links") or []:
            sub = _fetch_via_proxy(link, timeout)
            if not sub["ok"] or not sub.get("html"):
                error_count += 1
                continue
            ok2, _ = _write_page(url=link, host=host, fetched=sub, crawled_at=_utc_now(), site_node_id=site_node_id)
            if ok2:
                page_count += 1
                pages_written += 1

        _write_crawl(
            host,
            session_id=session_id,
            started_at=started_at,
            finished_at=_utc_now(),
            page_count=page_count,
            error_count=error_count,
            reachable=True,
            error_msg=None,
        )
        completed += 1

    # No FLUSH — RW_DDL_GUARD blocks it in hot-path workers (FLUSH is
    # diagnostic-only). RisingWave's barrier checkpoint handles visibility.
    return {
        "processed": processed,
        "completed": completed,
        "failed": failed,
        "pagesWritten": pages_written,
    }


# ─── LangServer glue ───────────────────────────────────────────────────────


def task_queue_seeds(**kwargs: Any) -> dict[str, Any]:
    return queue_seeds(
        seeds=kwargs.get("seeds"),
        category=(kwargs.get("category") or None) or None,
        limit=int(kwargs.get("limit") or 10),
    )


def task_process_queue(**kwargs: Any) -> dict[str, Any]:
    return process_queue(
        runs=kwargs.get("runs"),
        timeout_sec=float(kwargs.get("timeoutSec") or DEFAULT_TIMEOUT_SEC),
    )


def register(worker: Any, *, timeout_ms: int) -> None:
    worker.task(
        task_type="onion.crawl.queueSeeds",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_queue_seeds)
    worker.task(
        task_type="onion.crawl.processQueue",
        single_value=False,
        timeout_ms=timeout_ms,
    )(task_process_queue)
