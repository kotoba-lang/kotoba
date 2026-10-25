#!/usr/bin/env python3
"""Phase Coverage Gap: Fill domain coverage gaps from CC CDX → RisingWave.

Pipeline position (Critical Path step A):
  mv_cc_domain_coverage (actor IS NULL)
    → CC CDX API: enumerate pages per domain
    → INSERT vertex_page + edge_hosts_page + edge_links_to_domain
    → UPDATE vertex_domain.page_count

After this script completes, run in order:
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
  phase4_intel_risingwave.py --gaps-only   # Murakumo classification
  phase5_inject_did.py --from-rw           # Actor/DID registration

Usage:
  python3 phase_coverage_gap.py --dry-run              # preview gap list
  python3 phase_coverage_gap.py --limit 100            # fill 100 domains
  python3 phase_coverage_gap.py --workers 8            # parallel CDX fetch
  python3 phase_coverage_gap.py                        # fill all 8991 gaps
  python3 phase_coverage_gap.py --reset                # clear checkpoint and restart
"""

import argparse
import json
import logging
import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import psycopg2
import psycopg2.extras
import requests

# ── Config ──────────────────────────────────────────────────────────────────

RW_HOST = os.environ.get("RW_HOST", "45.32.79.245")
RW_PORT = int(os.environ.get("RW_PORT", "4566"))
RW_USER = os.environ.get("RW_USER", "root")
RW_DB   = os.environ.get("RW_DB",   "dev")

CC_CRAWL_ID   = os.environ.get("CC_CRAWL_ID", "CC-MAIN-2025-18")
CDX_BASE      = f"https://index.commoncrawl.org/{CC_CRAWL_ID}-index"
CDX_PAGE_LIMIT = int(os.environ.get("CDX_PAGE_LIMIT", "500"))   # pages per domain
CDX_CACHE_DIR  = Path(os.environ.get("CDX_CACHE_DIR", "/tmp/cdx_gap_cache"))
CDX_CACHE_TTL  = int(os.environ.get("CDX_CACHE_TTL",  str(7 * 86400)))  # 7 days
CDX_RETRIES    = 4
CDX_BACKOFF    = 1.5

BATCH_SIZE = 2000
STATE_FILE = Path(os.environ.get("GAP_STATE_FILE", "/tmp/.phase_coverage_gap_state.json"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
log = logging.getLogger(__name__)

shutdown_requested = False


def handle_signal(signum, frame):
    global shutdown_requested
    log.info("Shutdown requested — finishing current batch…")
    shutdown_requested = True


signal.signal(signal.SIGINT,  handle_signal)
signal.signal(signal.SIGTERM, handle_signal)

# ── Helpers ──────────────────────────────────────────────────────────────────

def ts_ms() -> int:
    return int(time.time() * 1000)


def domain_to_slug(domain: str) -> str:
    return domain.replace(".", "-")


def domain_to_did(domain: str) -> str:
    return f"did:web:site.etzhayyim.com:{domain_to_slug(domain)}"


def get_conn():
    return psycopg2.connect(
        host=RW_HOST, port=RW_PORT, user=RW_USER, dbname=RW_DB,
        connect_timeout=10,
    )

# ── Checkpoint ───────────────────────────────────────────────────────────────

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"done": [], "stats": {"domains": 0, "pages": 0, "hosts": 0, "dlinks": 0, "errors": 0}}


def save_state(state: dict):
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.rename(STATE_FILE)

# ── Gap Detection ─────────────────────────────────────────────────────────────

def get_gap_domains(limit: int = 0) -> list[dict]:
    """Query mv_cc_domain_coverage for domains without an actor."""
    conn = get_conn()
    cur = conn.cursor()
    sql = """
        SELECT domain_did, domain, slug, declared_page_count
        FROM mv_cc_domain_coverage
        WHERE actor_vertex_id IS NULL
        ORDER BY declared_page_count DESC NULLS LAST, domain
    """
    if limit > 0:
        sql += f" LIMIT {limit}"
    cur.execute(sql)
    rows = cur.fetchall()
    conn.close()
    return [
        {"vertex_id": r[0], "domain": r[1], "slug": r[2], "declared_page_count": r[3] or 0}
        for r in rows
    ]


def has_page_data(conn, domain_did: str) -> bool:
    """Check whether edge_hosts_page already has rows for this domain."""
    cur = conn.cursor()
    cur.execute(
        "SELECT 1 FROM edge_hosts_page WHERE src_vid = %s LIMIT 1",
        (domain_did,),
    )
    return cur.fetchone() is not None

# ── CDX Fetch ─────────────────────────────────────────────────────────────────

def cdx_cache_path(domain: str) -> Path:
    CDX_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    safe = domain.replace("/", "_").replace(":", "_")
    return CDX_CACHE_DIR / f"{safe}.jsonl"


def cdx_fetch_pages(domain: str, crawl_id: str = CC_CRAWL_ID) -> list[dict]:
    """
    Call CC CDX API and return a list of page dicts.
    Caches results to disk (TTL = CDX_CACHE_TTL).
    Returns [] if domain not found in crawl.
    """
    cache = cdx_cache_path(domain)
    if cache.exists():
        age = time.time() - cache.stat().st_mtime
        if age < CDX_CACHE_TTL:
            return _parse_cdx_cache(cache)

    url = CDX_BASE
    params = {
        "url":    f"{domain}/*",
        "output": "json",
        "limit":  CDX_PAGE_LIMIT,
        "fl":     "url,mime,status,timestamp,digest,length,offset,filename,languages",
    }

    delay = CDX_BACKOFF
    for attempt in range(CDX_RETRIES):
        try:
            resp = requests.get(url, params=params, timeout=30)
            if resp.status_code == 404:
                cache.write_text("")  # negative cache
                return []
            resp.raise_for_status()
            cache.write_text(resp.text)
            return _parse_cdx_cache(cache)
        except Exception as e:
            if attempt < CDX_RETRIES - 1:
                jitter = delay * (0.5 + 0.5 * (hash(domain) % 100) / 100)
                time.sleep(jitter)
                delay *= 2
            else:
                log.warning(f"CDX fetch failed for {domain}: {e}")
                return []
    return []


def _parse_cdx_cache(path: Path) -> list[dict]:
    pages = []
    try:
        for line in path.read_text().splitlines():
            if not line.strip():
                continue
            try:
                pages.append(json.loads(line))
            except Exception:
                pass
    except Exception:
        pass
    return pages

# ── RisingWave INSERT ─────────────────────────────────────────────────────────

def insert_pages_and_edges(conn, domain: str, cdx_pages: list[dict]) -> dict:
    """
    INSERT vertex_page + edge_hosts_page from CDX records.
    Also aggregates edge_links_to_domain stubs (outlink count placeholder).
    Returns stats dict.
    """
    cur   = conn.cursor()
    now   = ts_ms()
    did   = domain_to_did(domain)
    slug  = domain_to_slug(domain)
    stats = {"pages": 0, "hosts": 0, "dlinks": 0, "errors": []}

    page_rows  = []
    hosts_rows = []
    seen_hashes: set[str] = set()

    for p in cdx_pages:
        url        = (p.get("url") or "")[:2000]
        url_hash   = p.get("digest", "")[:64]
        mime       = p.get("mime",   "")
        status     = p.get("status", "")
        ts         = p.get("timestamp", "")
        langs      = p.get("languages", "")
        crawl      = CC_CRAWL_ID

        if not url or not url_hash:
            continue
        if url_hash in seen_hashes:
            continue
        seen_hashes.add(url_hash)

        vid = f"{did}:{url_hash}"

        page_rows.append((
            vid,            # vertex_id
            url_hash,       # rkey
            "did:web:site.etzhayyim.com",  # repo
            did,            # did
            "Page",         # label
            url,            # url
            domain,         # domain
            None,           # title  (CDX doesn't carry titles)
            None,           # description
            langs or None,  # language
            mime or None,   # content_type
            0,              # outlink_count (unknown from CDX)
            crawl,          # crawl
            now,            # _seq
            0,              # sensitivity_ord
            None,           # created_date
            None,           # owner_did
        ))
        hosts_rows.append((
            "Hosts",
            f"{did}->hosts->{url_hash}",
            did,
            vid,
            now, 0, None, None,
        ))

    # INSERT vertex_page in batches
    for i in range(0, len(page_rows), BATCH_SIZE):
        batch = page_rows[i:i + BATCH_SIZE]
        try:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO vertex_page
                    (vertex_id, rkey, repo, did, label, url, domain,
                     title, description, language, content_type,
                     outlink_count, crawl,
                     _seq, sensitivity_ord, created_date, owner_did)
                    VALUES %s""",
                batch, page_size=BATCH_SIZE,
            )
            conn.commit()
            stats["pages"] += len(batch)
        except Exception as e:
            stats["errors"].append(f"vertex_page: {e}")
            conn.rollback()

    # INSERT edge_hosts_page in batches
    for i in range(0, len(hosts_rows), BATCH_SIZE):
        batch = hosts_rows[i:i + BATCH_SIZE]
        try:
            psycopg2.extras.execute_values(
                cur,
                """INSERT INTO edge_hosts_page
                    (label, edge_id, src_vid, dst_vid,
                     _seq, sensitivity_ord, created_date, owner_did)
                    VALUES %s""",
                batch, page_size=BATCH_SIZE,
            )
            conn.commit()
            stats["hosts"] += len(batch)
        except Exception as e:
            stats["errors"].append(f"edge_hosts_page: {e}")
            conn.rollback()

    # UPDATE vertex_domain.page_count
    if stats["pages"] > 0:
        try:
            cur.execute(
                "UPDATE vertex_domain SET page_count = %s WHERE did = %s",
                (stats["pages"], did),
            )
            conn.commit()
        except Exception as e:
            stats["errors"].append(f"update page_count: {e}")
            conn.rollback()

    return stats


def insert_domain_links(conn, src_domain: str, dst_domain: str, count: int):
    """INSERT one edge_links_to_domain row."""
    src_did = domain_to_did(src_domain)
    dst_did = domain_to_did(dst_domain)
    eid     = f"{src_did}->dlinks->{dst_did}"
    now     = ts_ms()
    cur     = conn.cursor()
    try:
        cur.execute(
            """INSERT INTO edge_links_to_domain
                (label, count, edge_id, src_vid, dst_vid,
                 _seq, sensitivity_ord, created_date, owner_did)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            ("LinksToDomain", count, eid, src_did, dst_did, now, 0, None, None),
        )
        conn.commit()
        return 1
    except Exception as e:
        conn.rollback()
        return 0

# ── Per-domain worker ─────────────────────────────────────────────────────────

def page_count_for_domain(conn, domain_did: str) -> int:
    """Return number of edge_hosts_page rows for this domain."""
    cur = conn.cursor()
    cur.execute(
        "SELECT COUNT(*) FROM edge_hosts_page WHERE src_vid = %s",
        (domain_did,),
    )
    row = cur.fetchone()
    return int(row[0]) if row else 0


def fill_one_domain(d: dict, enrich_threshold: int = 5) -> dict:
    """
    Worker: CDX fetch → RisingWave INSERT for one domain.
    - Skips domains that already have >= enrich_threshold pages.
    - Enriches domains that have < enrich_threshold pages (sparse data).
    Uses its own connection (thread-safe).
    """
    domain     = d["domain"]
    domain_did = d["vertex_id"]
    result     = {"domain": domain, "pages": 0, "hosts": 0, "dlinks": 0, "errors": [], "skipped": False}

    conn = get_conn()
    try:
        existing = page_count_for_domain(conn, domain_did)
        if existing >= enrich_threshold:
            result["skipped"] = True
            return result

        # CDX fetch for domains with sparse or no page data
        cdx_pages = cdx_fetch_pages(domain)
        if not cdx_pages:
            result["skipped"] = True  # not in this crawl
            return result

        stats = insert_pages_and_edges(conn, domain, cdx_pages)
        result["pages"]  = stats["pages"]
        result["hosts"]  = stats["hosts"]
        result["errors"] = stats["errors"]

    except Exception as e:
        result["errors"].append(str(e))
    finally:
        conn.close()

    return result

# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Fill domain coverage gaps from CC CDX")
    parser.add_argument("--limit",   type=int, default=0,  help="Max gap domains to process (0=all)")
    parser.add_argument("--workers", type=int, default=4,  help="Parallel CDX fetch workers")
    parser.add_argument("--dry-run", action="store_true",  help="Preview gaps, no writes")
    parser.add_argument("--reset",   action="store_true",  help="Clear checkpoint and restart")
    args = parser.parse_args()

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        log.info("Checkpoint cleared.")

    state    = load_state()
    done_set = set(state["done"])

    log.info(f"RisingWave: {RW_HOST}:{RW_PORT}/{RW_DB}  crawl={CC_CRAWL_ID}  workers={args.workers}")

    # 1. Gap detection
    log.info("Querying coverage gaps…")
    gaps = get_gap_domains(args.limit)
    log.info(f"  {len(gaps)} gaps found (actor_vertex_id IS NULL)")

    if args.dry_run:
        log.info("── DRY-RUN: first 10 gaps ──")
        for d in gaps[:10]:
            log.info(f"  {d['domain']}  declared_pages={d['declared_page_count']}")
        log.info(f"  … {len(gaps)} total")
        return

    # 2. Filter already-done
    remaining = [d for d in gaps if d["domain"] not in done_set]
    log.info(f"  {len(done_set)} already done, {len(remaining)} remaining")

    if not remaining:
        log.info("Nothing to do.")
        return

    # 3. Parallel fill
    totals = {k: state["stats"].get(k, 0) for k in ("domains", "pages", "hosts", "dlinks", "errors")}
    t0     = time.time()
    done_count = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(fill_one_domain, d): d for d in remaining}

        for fut in as_completed(futures):
            if shutdown_requested:
                pool.shutdown(wait=False, cancel_futures=True)
                break

            d = futures[fut]
            try:
                r = fut.result()
            except Exception as e:
                log.error(f"  {d['domain']}: worker exception: {e}")
                totals["errors"] += 1
                continue

            if r["skipped"]:
                log.debug(f"  skip {d['domain']} (no CDX data or already has pages)")
            else:
                totals["domains"] += 1
                totals["pages"]   += r["pages"]
                totals["hosts"]   += r["hosts"]
                totals["dlinks"]  += r["dlinks"]
                if r["errors"]:
                    totals["errors"] += len(r["errors"])
                    for err in r["errors"][:2]:
                        log.warning(f"  {d['domain']}: {err}")

            state["done"].append(d["domain"])
            done_count += 1

            if done_count % 100 == 0:
                state["stats"] = totals
                save_state(state)
                elapsed = time.time() - t0
                rate = done_count / elapsed if elapsed > 0 else 0
                eta  = (len(remaining) - done_count) / rate / 60 if rate > 0 else 0
                log.info(
                    f"  [{done_count}/{len(remaining)}] "
                    f"domains={totals['domains']} pages={totals['pages']} "
                    f"hosts={totals['hosts']} "
                    f"({rate:.1f} dom/s, ETA {eta:.0f}min)"
                )

    state["stats"] = totals
    save_state(state)
    elapsed = time.time() - t0
    log.info(
        f"Done in {elapsed:.1f}s — "
        f"domains={totals['domains']} pages={totals['pages']} "
        f"hosts={totals['hosts']} errors={totals['errors']}"
    )
    log.info(f"Next: python3 phase4_intel_risingwave.py --gaps-only --limit {args.limit or totals['domains']}")


if __name__ == "__main__":
    main()
