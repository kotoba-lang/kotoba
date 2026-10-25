#!/usr/bin/env python3
"""ARCHIVED: Phase 3e: CC Parquet → RisingWave via direct psycopg2 (kubectl port-forward).

Superseded on 2026-04-13 by `phase3g_copy_ingest.py` on `path-j-cc-hummock`.

Hyperdrive の接続タイムアウトを回避するため、psycopg2 で RisingWave に直接接続。
事前に kubectl port-forward が必要:
# CHARTER-VIOLATION §substrate (centralized DB forbidden — migrate to AT MST + IPFS + Base L2)
  kubectl -n risingwave port-forward svc/risingwave 14566:4566

CREATE SOURCE (3 つ) + 各バッチの INSERT を chunk_size バッチ単位で実行。
statement_timeout = 0 で長時間 S3 file_scan も完走させる。

Usage:
  # port-forward してから実行
  kubectl -n risingwave port-forward svc/risingwave 14566:4566 &
  python3 scripts/archive/phase3e_direct_ingest.py

  # 特定テーブルのみ
  python3 scripts/archive/phase3e_direct_ingest.py --table pages
  python3 scripts/archive/phase3e_direct_ingest.py --table links
  python3 scripts/archive/phase3e_direct_ingest.py --table dlinks

  # 状態リセット
  python3 scripts/archive/phase3e_direct_ingest.py --reset

環境変数:
  RW_HOST         - RisingWave host (default: localhost)
  RW_PORT         - RisingWave PG port (default: 14566)
  S3_ACCESS_KEY   - Linode S3 access key
  S3_SECRET_KEY   - Linode S3 secret key
  CHUNK_SIZE      - batches per INSERT (default: 50)
  TOTAL_BATCHES   - total batch count (default: 28148)
"""

import argparse
import json
import logging
import os
import signal
import time
from pathlib import Path

import psycopg2
import psycopg2.extras

# ── Config ──

STATE_DIR = Path(os.environ.get("CC_DATA_DIR", "/Volumes/251220/CC/2603")) / "scripts"
STATE_FILE = STATE_DIR / ".phase3e_direct_state.json"

RW_HOST = os.environ.get("RW_HOST", "45.32.79.245")
RW_PORT = int(os.environ.get("RW_PORT", "4566"))
RW_USER = os.environ.get("RW_USER", "root")
RW_PASSWORD = os.environ.get("RW_PASSWORD", "")
RW_DATABASE = os.environ.get("RW_DATABASE", "dev")

S3_BUCKET = "kagami-graphar"
S3_PREFIX = "cc-parquet"
S3_ENDPOINT = "https://sg-sin-1.linodeobjects.com"
S3_REGION = "sg-sin-2"
S3_ACCESS = os.environ.get("S3_ACCESS_KEY", "LJF40TXHIUSVGBRKXEFU")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "Wv5b0cNdv7wNoZuiSmnJAxMwlye1MHEl1C6TowgR")

CHUNK_SIZE = int(os.environ.get("CHUNK_SIZE", "50"))
TOTAL_BATCHES = int(os.environ.get("TOTAL_BATCHES", "28148"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(STATE_DIR / "phase3e_direct.log"),
    ],
)
log = logging.getLogger(__name__)

_shutdown = False


def _signal_handler(sig, frame):
    global _shutdown
    log.info("Shutdown requested — stopping after current chunk")
    _shutdown = True


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)


# ── State ──

def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {
        "sources_created": False,
        "pages_chunks_done": [],
        "links_chunks_done": [],
        "dlinks_chunks_done": [],
        "domains_done": False,
    }


def save_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.rename(STATE_FILE)


# ── DB connection ──

def connect():
    conn = psycopg2.connect(
        host=RW_HOST,
        port=RW_PORT,
        user=RW_USER,
        password=RW_PASSWORD,
        database=RW_DATABASE,
        connect_timeout=10,
        # TCP keepalive to survive NAT idle timeouts during long queries
        keepalives=1,
        keepalives_idle=30,
        keepalives_interval=10,
        keepalives_count=9,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("SET iceberg_engine_connection = 'public.kagami_iceberg'")
    return conn


def exec_sql(conn, sql: str, timeout_hint: str = ""):
    with conn.cursor() as cur:
        t0 = time.time()
        cur.execute(sql)
        elapsed = time.time() - t0
        return elapsed


# ── S3 Source config ──

S3_CONF = (
    f"s3.region_name='{S3_REGION}', "
    f"s3.bucket_name='{S3_BUCKET}', "
    f"s3.credentials.access='{S3_ACCESS}', "
    f"s3.credentials.secret='{S3_SECRET}', "
    f"s3.endpoint_url='{S3_ENDPOINT}'"
)

SOURCES = [
    (
        "cc_pages_s3",
        """rkey VARCHAR, url VARCHAR, domain VARCHAR, title VARCHAR,
           description VARCHAR, language VARCHAR, content_type VARCHAR,
           status_code VARCHAR, outlink_count BIGINT, crawl VARCHAR,
           ip_address VARCHAR, og_image VARCHAR, robots VARCHAR,
           content_hash VARCHAR, previous_content_hash VARCHAR,
           version BIGINT, crawled_at VARCHAR,
           vertex_id VARCHAR, _seq BIGINT, created_date DATE,
           sensitivity_ord BIGINT, owner_did VARCHAR""",
        "cc-parquet/*_pages.parquet",
    ),
    (
        "cc_links_s3",
        """label VARCHAR, anchor_text VARCHAR,
           edge_id VARCHAR, src_vid VARCHAR, dst_vid VARCHAR,
           _seq BIGINT, created_date DATE, sensitivity_ord BIGINT, owner_did VARCHAR""",
        "cc-parquet/*_links.parquet",
    ),
    (
        "cc_dlinks_s3",
        """label VARCHAR, count BIGINT,
           edge_id VARCHAR, src_vid VARCHAR, dst_vid VARCHAR,
           _seq BIGINT, created_date DATE, sensitivity_ord BIGINT, owner_did VARCHAR""",
        "cc-parquet/*_dlinks.parquet",
    ),
]


def create_sources(conn, dry_run: bool = False):
    for name, cols, pattern in SOURCES:
        drop_sql = f"DROP SOURCE IF EXISTS {name} CASCADE"
        create_sql = (
            f"CREATE SOURCE {name} ({cols})\n"
            f"INCLUDE file AS source_file\n"
            f"WITH (connector='s3', match_pattern='{pattern}', {S3_CONF})\n"
            f"FORMAT PLAIN ENCODE PARQUET"
        )
        if dry_run:
            log.info(f"  [DRY-RUN] would create source: {name}")
            continue
        try:
            exec_sql(conn, drop_sql)
        except Exception as e:
            log.warning(f"  DROP {name}: {e}")
        try:
            elapsed = exec_sql(conn, create_sql)
            log.info(f"  Source {name}: created in {elapsed:.1f}s")
        except Exception as e:
            log.error(f"  Source {name}: FAILED — {e}")
            raise


# ── Column defs ──

PAGE_COLS = (
    "rkey, url, domain, title, description, language, content_type, "
    "status_code, outlink_count, crawl, ip_address, og_image, robots, "
    "content_hash, previous_content_hash, version, crawled_at, "
    "vertex_id, _seq, created_date, sensitivity_ord, owner_did"
)
LINK_COLS = (
    "label, anchor_text, edge_id, src_vid, dst_vid, "
    "_seq, created_date, sensitivity_ord, owner_did"
)
DLINK_COLS = (
    "label, count, edge_id, src_vid, dst_vid, "
    "_seq, created_date, sensitivity_ord, owner_did"
)


def chunked_insert(
    conn,
    table: str,
    source: str,
    cols: str,
    state_key: str,
    state: dict,
    chunk_size: int = CHUNK_SIZE,
    total_batches: int = TOTAL_BATCHES,
    dry_run: bool = False,
):
    done = set(state.get(state_key, []))
    chunks_total = (total_batches + chunk_size - 1) // chunk_size
    pending = [
        (s, min(s + chunk_size, total_batches))
        for s in range(0, total_batches, chunk_size)
        if f"{s}-{min(s+chunk_size, total_batches)}" not in done
    ]
    log.info(f"  {table}: {chunks_total} chunks total, {len(done)} done, {len(pending)} remaining")

    t0 = time.time()
    completed = 0
    errors = 0

    for chunk_start, chunk_end in pending:
        if _shutdown:
            log.info("  Shutdown — stopping")
            break

        chunk_key = f"{chunk_start}-{chunk_end}"
        start_str = f"cc-parquet/batch_{chunk_start:06d}_"
        end_str = f"cc-parquet/batch_{chunk_end:06d}_"

        sql = (
            f"INSERT INTO {table} ({cols})\n"
            f"SELECT {cols}\n"
            f"FROM {source}\n"
            f"WHERE source_file >= '{start_str}' AND source_file < '{end_str}'"
        )

        if dry_run:
            log.info(f"  [DRY-RUN] {table} [{chunk_start:06d}-{chunk_end:06d}]")
            done.add(chunk_key)
            continue

        tc = time.time()
        try:
            # Re-SET per chunk (connection might reset)
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = 0")
                cur.execute("SET iceberg_engine_connection = 'public.kagami_iceberg'")
                cur.execute(sql)

            elapsed = time.time() - tc
            completed += 1
            errors = 0
            done.add(chunk_key)
            state[state_key] = list(done)
            save_state(state)

            total_elapsed = time.time() - t0
            rate = completed / total_elapsed if total_elapsed > 0 else 0
            eta = (len(pending) - completed) / rate / 60 if rate > 0 else 0

            log.info(
                f"  {table} [{chunk_start:06d}-{chunk_end:06d}]: {elapsed:.0f}s "
                f"({completed}/{len(pending)}, ETA {eta:.0f}min)"
            )

        except psycopg2.OperationalError as e:
            log.error(f"  {table} [{chunk_start:06d}-{chunk_end:06d}] connection error: {e}")
            log.info("  Reconnecting in 10s...")
            time.sleep(10)
            try:
                conn = connect()
            except Exception as ce:
                log.error(f"  Reconnect failed: {ce}")
                break
            errors += 1

        except Exception as e:
            errors += 1
            log.error(f"  {table} [{chunk_start:06d}-{chunk_end:06d}]: {str(e)[:200]}")
            if errors >= 3:
                log.error("  3 consecutive errors — stopping this table")
                break
            log.info("  Sleeping 10s before retry...")
            time.sleep(10)

    elapsed = time.time() - t0
    log.info(f"  {table}: {completed}/{len(pending)} chunks done in {elapsed:.0f}s")
    return conn


def verify(conn):
    tables = ["vertex_page", "edge_links_to", "edge_links_to_domain", "vertex_domain"]
    for t in tables:
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                count = cur.fetchone()[0]
            log.info(f"  {t}: {count:,}")
        except Exception as e:
            log.warning(f"  {t}: {e}")


def populate_domains(conn, dry_run: bool = False):
    if dry_run:
        log.info("  [DRY-RUN] would populate vertex_domain")
        return
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM vertex_domain WHERE 1=1")
        log.info("  vertex_domain: cleared")
    except Exception as e:
        log.warning(f"  vertex_domain DELETE: {e}")
    insert_sql = """INSERT INTO vertex_domain (
        vertex_id, domain, did, handle, display_name,
        topics, performer_type, status,
        _seq, sensitivity_ord, created_date, owner_did
    )
    SELECT
        p.domain, p.domain,
        'did:web:site.etzhayyim.com:' || REPLACE(p.domain, '.', '-'),
        'site.etzhayyim.com:' || REPLACE(p.domain, '.', '-'),
        p.domain, NULL::VARCHAR, 'service', 'active',
        0::BIGINT, 0::BIGINT, NULL::DATE, NULL::VARCHAR
    FROM (SELECT DISTINCT domain FROM vertex_page WHERE domain IS NOT NULL AND domain != '') p"""
    try:
        with conn.cursor() as cur:
            cur.execute("SET statement_timeout = 0")
            cur.execute("SET iceberg_engine_connection = 'public.kagami_iceberg'")
            cur.execute(insert_sql)
        log.info("  vertex_domain: populated")
    except Exception as e:
        log.error(f"  vertex_domain INSERT: {e}")


def main():
    p = argparse.ArgumentParser(description="Phase 3e: direct psycopg2 ingestion (kubectl port-forward)")
    p.add_argument("--table", choices=["pages", "links", "dlinks", "domains", "all"], default="all")
    p.add_argument("--chunk-size", type=int, default=CHUNK_SIZE)
    p.add_argument("--total-batches", type=int, default=TOTAL_BATCHES)
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--reset", action="store_true")
    p.add_argument("--recreate-sources", action="store_true")
    args = p.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        log.info("State reset")

    state = load_state()

    log.info("=" * 60)
    log.info("Phase 3e: CC Parquet → RisingWave (direct psycopg2)")
    log.info(f"  RisingWave: {RW_HOST}:{RW_PORT}")
    log.info(f"  Chunk size: {args.chunk_size} batches, Total: {args.total_batches}")
    log.info("=" * 60)

    # Connect
    log.info(f"Connecting to RisingWave {RW_HOST}:{RW_PORT}...")
    try:
        conn = connect()
        log.info("  Connected OK")
    except Exception as e:
        log.error(f"  Connection FAILED: {e}")
        log.error("  Make sure kubectl port-forward is running:")
        log.error("  kubectl -n risingwave port-forward svc/risingwave 14566:4566")
        return

    t0 = time.time()

    # Sources
    if not state.get("sources_created") or args.recreate_sources:
        log.info("=== Create S3 Sources ===")
        create_sources(conn, dry_run=args.dry_run)
        if not args.dry_run:
            state["sources_created"] = True
            save_state(state)
            log.info("  Waiting 3s for source file discovery...")
            time.sleep(3)
    else:
        log.info("=== S3 Sources: already created (use --recreate-sources to force) ===")

    ingest_opts = dict(chunk_size=args.chunk_size, total_batches=args.total_batches, dry_run=args.dry_run)

    if args.table in ("pages", "all"):
        log.info("=== INSERT vertex_page ===")
        conn = chunked_insert(conn, "vertex_page", "cc_pages_s3", PAGE_COLS,
                              "pages_chunks_done", state, **ingest_opts)

    if args.table in ("links", "all") and not _shutdown:
        log.info("=== INSERT edge_links_to ===")
        conn = chunked_insert(conn, "edge_links_to", "cc_links_s3", LINK_COLS,
                              "links_chunks_done", state, **ingest_opts)

    if args.table in ("dlinks", "all") and not _shutdown:
        log.info("=== INSERT edge_links_to_domain ===")
        conn = chunked_insert(conn, "edge_links_to_domain", "cc_dlinks_s3", DLINK_COLS,
                              "dlinks_chunks_done", state, **ingest_opts)

    if args.table in ("domains", "all") and not _shutdown:
        if not state.get("domains_done"):
            log.info("=== Populate vertex_domain ===")
            populate_domains(conn, dry_run=args.dry_run)
            if not args.dry_run:
                state["domains_done"] = True
                save_state(state)

    if not _shutdown:
        log.info("=== Verify ===")
        verify(conn)

    conn.close()
    log.info(f"Phase 3e complete in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
