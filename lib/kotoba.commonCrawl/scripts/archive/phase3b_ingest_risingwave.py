#!/usr/bin/env python3
"""Phase 3b: Ingest Common Crawl DID property graph into RisingWave.

Reads Phase 3 output (domains JSONL + Cypher batch files) and writes to
RisingWave via PostgreSQL wire protocol (psycopg2, :4566).

Current ingestion path for Common Crawl graph data (psycopg2/PG).

Tables (models.py SSoT — already exist in RisingWave):
  vertex_domain        — web domains with DID + topic classification
  vertex_page          — web pages with metadata
  edge_hosts_page      — domain → page edges
  edge_links_to        — page → page cross-domain links
  edge_links_to_domain — domain → domain aggregated links

Streaming MVs (auto-refresh on INSERT):
  mv_cc_domain_page_count  — real-time page count per domain
  mv_cc_domain_out_degree  — outgoing domain link count
  mv_cc_domain_in_degree   — incoming domain link count
  mv_cc_domain_coverage    — domain × actor join

Usage:
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
  python3 scripts/archive/phase3b_ingest_risingwave.py --phase domains
  python3 scripts/archive/phase3b_ingest_risingwave.py --phase pages --workers 4
  python3 scripts/archive/phase3b_ingest_risingwave.py --phase all
  python3 scripts/archive/phase3b_ingest_risingwave.py --phase domains --dry-run
"""

import argparse
import gzip
import json
import logging
import os
import re
import signal
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.extras

# ── Config ──

BASE_DIR = Path(os.environ.get("CC_DATA_DIR", "/Volumes/251220/CC/2603"))
GRAPH_DIR = BASE_DIR / "graph"
STATE_FILE = BASE_DIR / "scripts" / ".phase3b_rw_state.json"

RW_HOST = os.environ.get("RW_HOST", "localhost")
RW_PORT = int(os.environ.get("RW_PORT", "4566"))
RW_USER = os.environ.get("RW_USER", "root")
RW_DB = os.environ.get("RW_DB", "dev")

BATCH_SIZE = 2000  # rows per INSERT (RisingWave memory-safe batch size)
CRAWL_ID = os.environ.get("CC_CRAWL_ID", "CC-MAIN-2026-12")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(BASE_DIR / "scripts" / "phase3b_rw.log"),
    ],
)
log = logging.getLogger(__name__)

shutdown_requested = False


def handle_signal(signum, frame):
    global shutdown_requested
    log.info("Shutdown requested...")
    shutdown_requested = True


signal.signal(signal.SIGINT, handle_signal)
signal.signal(signal.SIGTERM, handle_signal)


def get_conn():
    """Create psycopg2 connection to RisingWave PG :4566."""
    return psycopg2.connect(
        host=RW_HOST, port=RW_PORT, user=RW_USER, dbname=RW_DB,
        connect_timeout=10,
    )


def ts_ms():
    return int(time.time() * 1000)


# ── State management ──

def load_state():
    if STATE_FILE.exists():
        try:
            return json.load(open(STATE_FILE))
        except Exception:
            pass
    return {"domains_done": False, "cypher_files_done": [], "stats": {}}


def save_state(state):
    tmp = STATE_FILE.with_suffix(".tmp")
    with open(tmp, "w") as f:
        json.dump(state, f, indent=2)
    tmp.rename(STATE_FILE)


# ── Domain ingestion ──

def ingest_domains(conn, dry_run=False):
    """Ingest domains from Phase 3 JSONL into vertex_domain."""
    jsonl_path = GRAPH_DIR / "domains_for_classification.jsonl.gz"
    if not jsonl_path.exists():
        log.error(f"JSONL not found: {jsonl_path}. Run phase3 first.")
        return 0

    domains = []
    with gzip.open(jsonl_path, "rt") as f:
        for line in f:
            if not line.strip():
                continue
            domains.append(json.loads(line))

    log.info(f"Loaded {len(domains)} domains from JSONL")

    if dry_run:
        for d in domains[:5]:
            log.info(f"  [DRY-RUN] {d['domain']} ({d.get('pageCount', 0)} pages)")
        log.info(f"  ... {len(domains)} total")
        return len(domains)

    cur = conn.cursor()
    now = ts_ms()
    total = 0

    for i in range(0, len(domains), BATCH_SIZE):
        if shutdown_requested:
            break
        batch = domains[i:i + BATCH_SIZE]
        rows = []
        for d in batch:
            domain = d["domain"]
            topics = json.dumps(d.get("topics", []))
            rows.append((
                domain,  # vertex_id = domain (canonical key)
                domain, topics,
                now, 0, None, None,
            ))

        sql = """INSERT INTO vertex_domain
            (vertex_id, domain, topics,
             _seq, sensitivity_ord, created_date, owner_did)
            VALUES %s
            """
        try:
            psycopg2.extras.execute_values(cur, sql, rows, page_size=BATCH_SIZE)
            conn.commit()
            total += len(batch)
        except Exception as e:
            log.error(f"INSERT vertex_domain batch {i}: {e}")
            conn.rollback()

        if (i // BATCH_SIZE) % 5 == 0:
            log.info(f"  vertex_domain: {total}/{len(domains)}")

    log.info(f"vertex_domain: {total} rows inserted")
    return total


# ── Cypher batch parsing (unified) ──
# Extracts domain, rkey, url, title, outlink_count, crawl from any Cypher format.
# Uses property-based extraction instead of label-specific regex.

# Domain: extract domain= property from any MERGE line with domain info
RE_DOMAIN_PROP = re.compile(r'd\.domain = "([^"]*)"')
RE_TOPIC_PROP = re.compile(r'd\.topic = "([^"]*)"')

# Page: extract rkey/url_hash PK + properties
RE_PAGE_RKEY = re.compile(r'MERGE \([a-z]+:(?:CcPage|PageRecord) \{(?:url_hash|rkey): "([^"]+)"\}\)')
RE_PAGE_URL = re.compile(r'[pt]p?\.url = "([^"]*)"')
RE_PAGE_TITLE = re.compile(r'[pt]p?\.title = "([^"]*)"')
RE_PAGE_DOMAIN = re.compile(r'[pt]p?\.domain = "([^"]*)"')
RE_PAGE_OUTLINKS = re.compile(r'[pt]p?\.(?:outlink_count|outlinkCount) = (\d+)')
RE_PAGE_CRAWL = re.compile(r'[pt]p?\.crawl = "([^"]*)"')
RE_PAGE_DESC = re.compile(r'p\.description = "([^"]*)"')
RE_PAGE_LANG = re.compile(r'p\.language = "([^"]*)"')
RE_PAGE_CTYPE = re.compile(r'p\.contentType = "([^"]*)"')

# Edges: HOSTS/HOSTS_PAGE and LINKS_TO (any label variant)
RE_HOSTS_EDGE = re.compile(
    r'MATCH \(d:\w+ \{(?:name|did): "([^"]+)"\}\), \(p:\w+ \{(?:url_hash|rkey): "([^"]+)"\}\) '
    r'MERGE \(d\)-\[:(?:HOSTS|HOSTS_PAGE)\]->\(p\)'
)
RE_LINKS_EDGE = re.compile(
    r'MATCH \(s:\w+ \{(?:url_hash|rkey): "([^"]+)"\}\), \(t:\w+ \{(?:url_hash|rkey): "([^"]+)"\}\) '
    r'MERGE \(s\)-\[:LINKS_TO\]->\(t\)'
)


def domain_to_vid(domain: str) -> str:
    """Derive vertex_id for a domain. Shannon: domain is the canonical key."""
    return domain


def parse_cypher_file(path):
    """Parse a Cypher batch file into row tuples (format-agnostic).

    Uses property-based extraction — works with any Cypher label names.
    Returns: (domains, pages, links_edges, domain_links)
      domains:      dict[domain_name] → topic (or "")
      pages:        list of page dicts (rkey, url, domain, title, outlink_count, crawl, ...)
      links_edges:  list of {src_rkey, dst_rkey}
      domain_links: list of {src_domain, dst_domain, count} (aggregated cross-domain)
    """
    domains: dict[str, str] = {}  # domain_name → topic
    pages: list[dict] = []
    links_edges: list[dict] = []
    seen_pages: dict[str, int] = {}  # rkey → index in pages list

    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue

            # ── Page node ──
            m = RE_PAGE_RKEY.search(line)
            if m and "ON CREATE SET" in line:
                rkey = m.group(1)
                url = (RE_PAGE_URL.search(line) or _EMPTY).group(1)
                title = (RE_PAGE_TITLE.search(line) or _EMPTY).group(1)
                domain = (RE_PAGE_DOMAIN.search(line) or _EMPTY).group(1)
                outlinks_m = RE_PAGE_OUTLINKS.search(line)
                outlinks = int(outlinks_m.group(1)) if outlinks_m else 0
                crawl = (RE_PAGE_CRAWL.search(line) or _EMPTY_CRAWL).group(1)
                desc = (RE_PAGE_DESC.search(line) or _EMPTY).group(1)
                lang = (RE_PAGE_LANG.search(line) or _EMPTY).group(1)
                ctype = (RE_PAGE_CTYPE.search(line) or _EMPTY).group(1)

                if rkey in seen_pages:
                    # Update if this duplicate has better data (non-empty title)
                    if title:
                        idx = seen_pages[rkey]
                        if not pages[idx]["title"]:
                            pages[idx]["title"] = title
                        if outlinks > pages[idx]["outlink_count"]:
                            pages[idx]["outlink_count"] = outlinks
                        if desc and not pages[idx].get("description"):
                            pages[idx]["description"] = desc
                    continue

                seen_pages[rkey] = len(pages)
                pages.append({
                    "rkey": rkey, "url": url, "domain": domain,
                    "title": title, "outlink_count": outlinks, "crawl": crawl,
                    "description": desc or None, "language": lang or None,
                    "content_type": ctype or None,
                })
                if domain:
                    domains.setdefault(domain, "")
                continue

            # ── HOSTS / HOSTS_PAGE edge → extract domain ──
            m = RE_HOSTS_EDGE.search(line)
            if m:
                key = m.group(1)
                # key is either domain name (CcDomain) or DID (DomainDID)
                if key.startswith("did:web:site.etzhayyim.com:"):
                    pass  # domain already captured from DomainDID MERGE
                else:
                    domains.setdefault(key, "")
                continue

            # ── LINKS_TO edge ──
            m = RE_LINKS_EDGE.search(line)
            if m:
                links_edges.append({"src_rkey": m.group(1), "dst_rkey": m.group(2)})
                continue

            # ── Domain node (standalone) ──
            m = RE_DOMAIN_PROP.search(line)
            if m and "MERGE" in line:
                dn = m.group(1)
                if dn:
                    topic = (RE_TOPIC_PROP.search(line) or _EMPTY).group(1)
                    domains[dn] = topic or domains.get(dn, "")

    # Aggregate page-level links into domain-level edges
    rkey_to_domain = {p["rkey"]: p["domain"] for p in pages if p["domain"]}
    domain_link_counts: dict[tuple[str, str], int] = {}
    for le in links_edges:
        src_dom = rkey_to_domain.get(le["src_rkey"])
        dst_dom = rkey_to_domain.get(le["dst_rkey"])
        if src_dom and dst_dom and src_dom != dst_dom:
            key = (src_dom, dst_dom)
            domain_link_counts[key] = domain_link_counts.get(key, 0) + 1

    domain_links = [
        {"src_domain": k[0], "dst_domain": k[1], "count": v}
        for k, v in domain_link_counts.items()
    ]

    return domains, pages, links_edges, domain_links


# Sentinel for regex non-matches
class _EmptyMatch:
    def group(self, n): return ""

_EMPTY = _EmptyMatch()

class _EmptyCrawlMatch:
    def group(self, n): return CRAWL_ID

_EMPTY_CRAWL = _EmptyCrawlMatch()


def _batch_insert(cur, conn, sql, rows, batch_size):
    """INSERT rows in batch; on PK conflict, skip entire batch.

    For high-throughput CC ingest, skipping a conflicting batch (≤2000 rows)
    is acceptable — the data already exists from a previous file.
    """
    try:
        psycopg2.extras.execute_values(cur, sql, rows, page_size=batch_size)
        conn.commit()
        return len(rows)
    except Exception:
        conn.rollback()
        return 0


def process_one_file(cypher_file: Path) -> dict:
    """Parse one Cypher file and INSERT into Shannon-optimal tables.

    Tables written:
      vertex_domain:        domain (PK via vertex_id=domain), topics
      vertex_page:          rkey, url, domain, title, description, language, content_type, outlink_count, crawl
      edge_links_to:        src_rkey → dst_rkey
      edge_links_to_domain: src_domain → dst_domain (aggregated count)

    NOT written (derived by MV or JOIN):
      edge_hosts_page:  redundant — vertex_page.domain IS the HOSTS relationship
      slug, did, repo:  derived from domain — computed at query time
    """
    conn = get_conn()
    cur = conn.cursor()
    now = ts_ms()
    stats = {"file": cypher_file.name, "domains": 0, "pages": 0, "links": 0, "dlinks": 0, "errors": []}

    domains, pages, links_edges, domain_links = parse_cypher_file(cypher_file)

    # vertex_domain — SKIPPED during file processing.
    # Domains are derived from vertex_page.domain after all files are processed.
    # This avoids 884K domain × 84K file cross-product INSERT conflicts.
    stats["domains"] = len(domains)

    # vertex_page — Shannon: rkey as PK, domain as FK (replaces edge_hosts_page)
    page_sql = """INSERT INTO vertex_page
        (vertex_id, rkey, url, domain,
         title, description, language, content_type,
         outlink_count, crawl,
         _seq, sensitivity_ord, created_date, owner_did)
        VALUES %s"""
    for i in range(0, len(pages), BATCH_SIZE):
        batch = pages[i:i + BATCH_SIZE]
        rows = []
        for p in batch:
            vid = p["rkey"]
            rows.append((
                vid, p["rkey"], p["url"][:2048], p["domain"],
                p["title"][:1024] if p["title"] else None,
                p.get("description"),
                p.get("language"),
                p.get("content_type"),
                p["outlink_count"], p["crawl"],
                now, 0, None, None,
            ))
        if rows:
            ok = _batch_insert(cur, conn, page_sql, rows, BATCH_SIZE)
            stats["pages"] += ok

    # edge_links_to — page → page cross-links
    link_sql = """INSERT INTO edge_links_to
        (label, edge_id, src_vid, dst_vid,
         _seq, sensitivity_ord, created_date, owner_did)
        VALUES %s"""
    for i in range(0, len(links_edges), BATCH_SIZE):
        batch = links_edges[i:i + BATCH_SIZE]
        rows = []
        for e in batch:
            eid = f"{e['src_rkey']}->links->{e['dst_rkey']}"
            rows.append((
                "LinksTo", eid, e["src_rkey"], e["dst_rkey"],
                now, 0, None, None,
            ))
        if rows:
            ok = _batch_insert(cur, conn, link_sql, rows, BATCH_SIZE)
            stats["links"] += ok

    # edge_links_to_domain — domain-level aggregation
    dlink_sql = """INSERT INTO edge_links_to_domain
        (label, count, edge_id, src_vid, dst_vid,
         _seq, sensitivity_ord, created_date, owner_did)
        VALUES %s"""
    for i in range(0, len(domain_links), BATCH_SIZE):
        batch = domain_links[i:i + BATCH_SIZE]
        rows = []
        for dl in batch:
            eid = f"{dl['src_domain']}->dlinks->{dl['dst_domain']}"
            rows.append((
                "LinksToDomain", dl["count"], eid,
                dl["src_domain"], dl["dst_domain"],
                now, 0, None, None,
            ))
        if rows:
            ok = _batch_insert(cur, conn, dlink_sql, rows, BATCH_SIZE)
            stats["dlinks"] += ok

    conn.close()
    return stats


def ingest_cypher_parallel(dry_run=False, limit=0, workers=4):
    """Parse Cypher batch files and INSERT via parallel workers."""
    from concurrent.futures import ThreadPoolExecutor, as_completed

    state = load_state()
    done_files = set(state.get("cypher_files_done", []))

    cypher_files = sorted(GRAPH_DIR.glob("batch_*.cypher"))
    remaining = [f for f in cypher_files if f.name not in done_files]
    if limit > 0:
        remaining = remaining[:limit]

    log.info(f"Cypher batches: {len(cypher_files)} total, {len(done_files)} done, {len(remaining)} remaining, workers={workers}")

    if dry_run:
        for f in remaining[:3]:
            doms, pages, links, dlinks = parse_cypher_file(f)
            log.info(f"  [DRY-RUN] {f.name}: {len(doms)} domains, {len(pages)} pages, {len(links)} links, {len(dlinks)} dlinks")
        return

    totals = {"domains": 0, "pages": 0, "links": 0, "dlinks": 0}
    prev = state.get("stats", {})
    for k in totals:
        totals[k] = prev.get(k, 0)
    t0 = time.time()
    done_count = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {}
        for cf in remaining:
            if shutdown_requested:
                break
            futures[pool.submit(process_one_file, cf)] = cf

        for fut in as_completed(futures):
            if shutdown_requested:
                pool.shutdown(wait=False, cancel_futures=True)
                break
            cf = futures[fut]
            try:
                s = fut.result()
                totals["domains"] += s["domains"]
                totals["pages"] += s["pages"]
                totals["links"] += s["links"]
                totals["dlinks"] += s.get("dlinks", 0)
                state["cypher_files_done"].append(cf.name)
                done_count += 1

                if s["errors"]:
                    for err in s["errors"]:
                        log.error(f"  {cf.name}: {err}")

                if done_count % 50 == 0:
                    state["stats"] = totals
                    save_state(state)
                    elapsed = time.time() - t0
                    rate = done_count / elapsed if elapsed > 0 else 0
                    eta = (len(remaining) - done_count) / rate / 60 if rate > 0 else 0
                    log.info(
                        f"  [{done_count}/{len(remaining)}] "
                        f"domains={totals['domains']} pages={totals['pages']} "
                        f"links={totals['links']} dlinks={totals['dlinks']} "
                        f"({rate:.1f} files/s, ETA {eta:.0f}min)"
                    )
            except Exception as e:
                log.error(f"  {cf.name}: worker exception: {e}")

    state["stats"] = totals
    save_state(state)
    elapsed = time.time() - t0
    log.info(
        f"Done: domains={totals['domains']} pages={totals['pages']} "
        f"links={totals['links']} dlinks={totals['dlinks']} ({elapsed:.1f}s)"
    )


# ── Actor ingestion (from vertex_domain already in RisingWave) ──

def ingest_actors(conn, dry_run=False):
    """Ingest CC domain actors into vertex_actor from vertex_domain rows."""
    cur = conn.cursor()

    # Read all CC domains already in RisingWave
    cur.execute("""
        SELECT vertex_id, did, domain, slug
        FROM vertex_domain
        WHERE source = 'common-crawl'
        ORDER BY domain
    """)
    domains = cur.fetchall()
    log.info(f"Found {len(domains)} CC domains in vertex_domain")

    if not domains:
        log.error("No CC domains in vertex_domain. Run --phase pages first.")
        return 0

    if dry_run:
        for vid, did, domain, slug in domains[:5]:
            log.info(f"  [DRY-RUN] actor: {did} ({domain})")
        log.info(f"  ... {len(domains)} total")
        return len(domains)

    now = ts_ms()
    total = 0

    for i in range(0, len(domains), BATCH_SIZE):
        if shutdown_requested:
            break
        batch = domains[i:i + BATCH_SIZE]
        rows = []
        for vid, did, domain, slug in batch:
            handle = f"site.etzhayyim.com:{slug}"
            display_name = domain
            description = f"[AI Agent — unofficial] Internet domain: {domain}"
            rows.append((
                did, did, None, handle, display_name, None, None,
                None, "active", "com.etzhayyim.apps.site.domain", slug,
                "did:web:site.etzhayyim.com", None, None, None,
                "service", None, None, None, None, None, None,
                now, 0, None, None,
            ))

        sql = """INSERT INTO vertex_actor
            (vertex_id, did, nanoid, handle, display_name, avatar_cid, banner_cid,
             execution_tier, status, collection, rkey,
             repo, created_at, name, project,
             performer_type, runtime_type, ui_type, agent_type, classification,
             operator, category,
             _seq, sensitivity_ord, created_date, owner_did)
            VALUES %s
            """
        try:
            psycopg2.extras.execute_values(cur, sql, rows, page_size=BATCH_SIZE)
            conn.commit()
            total += len(batch)
        except Exception as e:
            log.error(f"INSERT vertex_actor batch {i}: {e}")
            conn.rollback()

        if (i // BATCH_SIZE) % 5 == 0:
            log.info(f"  vertex_actor (CC): {total}/{len(domains)}")

    log.info(f"vertex_actor (CC): {total} rows inserted")
    return total


# ── PDS profile update ──

def update_pds_profiles(conn, dry_run=False):
    """Update PDS profiles for CC domain actors (displayName + description)."""
    import requests

    PDS_URL = os.environ.get("PDS_URL", "https://atproto.etzhayyim.com")
    SITE_APP_DID = "did:web:site.etzhayyim.com"

    cur = conn.cursor()
    cur.execute("""
        SELECT vertex_id, did, domain, slug
        FROM vertex_domain
        WHERE source = 'common-crawl'
        ORDER BY domain
    """)
    domains = cur.fetchall()
    log.info(f"Updating PDS profiles for {len(domains)} CC domains")

    if not domains:
        return 0

    if dry_run:
        for vid, did, domain, slug in domains[:5]:
            log.info(f"  [DRY-RUN] profile: {did} displayName={domain}")
        log.info(f"  ... {len(domains)} total")
        return len(domains)

    total = 0
    errors = 0

    for i, (vid, did, domain, slug) in enumerate(domains):
        if shutdown_requested:
            break

        display_name = domain
        description = f"[AI Agent — unofficial] Internet domain: {domain}"

        body = {
            "$type": "app.bsky.actor.profile",
            "repo": did,
            "displayName": display_name,
            "description": description,
        }
        headers = {
            "Content-Type": "application/json",
            "x-kotodama-verified": "true",
            "X-Active-DID": SITE_APP_DID,
        }

        try:
            resp = requests.post(
                f"{PDS_URL}/xrpc/com.etzhayyim.pds.putProfile",
                json=body, headers=headers, timeout=30,
            )
            if resp.status_code < 400:
                total += 1
            else:
                errors += 1
                if errors <= 5:
                    log.error(f"  putRecord {did}: {resp.status_code} {resp.text[:120]}")
        except Exception as e:
            errors += 1
            if errors <= 5:
                log.error(f"  putRecord {did}: {e}")

        if (i + 1) % 100 == 0:
            log.info(f"  PDS profiles: {total}/{len(domains)} updated, {errors} errors")
            time.sleep(0.2)  # rate limit

    log.info(f"PDS profiles: {total} updated, {errors} errors")
    return total


def populate_domains_from_pages(dry_run=False):
    """Post-processing: populate vertex_domain from DISTINCT vertex_page.domain.

    Shannon: vertex_domain is derived from vertex_page — no need to INSERT
    during per-file processing (avoids 884K × 84K cross-product conflicts).
    """
    conn = get_conn()
    cur = conn.cursor()

    cur.execute("SELECT COUNT(DISTINCT domain) FROM vertex_page WHERE domain IS NOT NULL AND domain != ''")
    total = cur.fetchone()[0]
    log.info(f"Populating vertex_domain from {total:,} distinct page domains")

    if dry_run:
        conn.close()
        return total

    # INSERT ... SELECT — single SQL, no client-side loop
    try:
        cur.execute("""
            INSERT INTO vertex_domain (vertex_id, domain, topics, _seq, sensitivity_ord, created_date, owner_did)
            SELECT DISTINCT
                domain,              -- vertex_id = domain
                domain,
                NULL,                -- topics filled by Phase 4 intel
                0, 0, NULL, NULL
            FROM vertex_page
            WHERE domain IS NOT NULL AND domain != ''
        """)
        conn.commit()
        cur.execute("SELECT COUNT(*) FROM vertex_domain")
        count = cur.fetchone()[0]
        log.info(f"vertex_domain: {count:,} rows populated from vertex_page")
    except Exception as e:
        log.error(f"populate_domains_from_pages: {e}")
        conn.rollback()

    conn.close()
    return total


def main():
    parser = argparse.ArgumentParser(description="Phase 3b: Ingest CC graph into RisingWave")
    parser.add_argument("--phase", choices=["domains", "actors", "profiles", "pages", "all"], default="all")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--limit", type=int, default=0, help="Max Cypher batch files (0=all)")
    parser.add_argument("--workers", type=int, default=4, help="Parallel INSERT workers")
    parser.add_argument("--reset", action="store_true", help="Reset ingestion state")
    args = parser.parse_args()

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        log.info("Ingestion state reset")

    log.info(
        f"Phase 3b (RisingWave): {RW_HOST}:{RW_PORT}/{RW_DB} "
        f"phase={args.phase} workers={args.workers} dry_run={args.dry_run}"
    )

    t0 = time.time()

    if args.phase in ("domains", "all"):
        conn = None if args.dry_run else get_conn()
        ingest_domains(conn, args.dry_run)
        if conn:
            conn.close()

    if args.phase in ("actors", "all"):
        conn = None if args.dry_run else get_conn()
        ingest_actors(conn, args.dry_run)
        if conn:
            conn.close()

    if args.phase in ("profiles", "all"):
        conn = None if args.dry_run else get_conn()
        update_pds_profiles(conn, args.dry_run)
        if conn:
            conn.close()

    if args.phase in ("pages", "all"):
        ingest_cypher_parallel(args.dry_run, args.limit, args.workers)
        # Post-processing: populate vertex_domain from vertex_page.domain
        if not shutdown_requested:
            populate_domains_from_pages(args.dry_run)

    elapsed = time.time() - t0
    log.info(f"Phase 3b (RisingWave) completed in {elapsed:.1f}s")


if __name__ == "__main__":
    main()
