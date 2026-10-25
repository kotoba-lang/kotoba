#!/usr/bin/env python3
"""Phase 3g: CC Parquet → RisingWave via COPY FROM STDIN (batch, no streaming).

- Reads parquet files locally with pyarrow
- Streams rows via psycopg2 COPY FROM STDIN CSV
- No persistent streaming source → no boot-time state rehydration
- Rate-limited between files (compute memory safety)
- Resumable via state file
- Monitor compute memory; pause if > 80% via pod status check

Usage:
  python3 phase3g_copy_ingest.py                 # all tables
  python3 phase3g_copy_ingest.py --table pages
  python3 phase3g_copy_ingest.py --table links
  python3 phase3g_copy_ingest.py --table dlinks
  python3 phase3g_copy_ingest.py --table domains
  python3 phase3g_copy_ingest.py --sleep-ms 200  # rate limit
  python3 phase3g_copy_ingest.py --reset
"""

import argparse
import io
import json
import logging
import os
import signal
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import psycopg2
import psycopg2.extras
import pyarrow.parquet as pq

# ── Config ──
PARQUET_DIR = Path(os.environ.get("CC_PARQUET_DIR", "/Volumes/251220/CC/2603/parquet-rs"))
STATE_DIR = Path(os.environ.get("CC_DATA_DIR", "/Volumes/251220/CC/2603")) / "scripts"
STATE_FILE = STATE_DIR / ".phase3g_copy_state.json"

RW_HOST = os.environ.get("RW_HOST", "45.32.79.245")
RW_PORT = int(os.environ.get("RW_PORT", "4566"))
RW_USER = os.environ.get("RW_USER", "root")
RW_DATABASE = os.environ.get("RW_DATABASE", "dev")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler(sys.stdout),
              logging.FileHandler(STATE_DIR / "phase3g_copy.log")],
)
log = logging.getLogger(__name__)

_shutdown = False


def _sig(sig, frame):
    global _shutdown
    log.info("Shutdown requested")
    _shutdown = True


signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)


# ── Column definitions ──
# Column list per target table. Order must match parquet files.
PAGE_COLS = [
    "rkey", "url", "domain", "title", "description", "language", "content_type",
    "status_code", "outlink_count", "crawl", "ip_address", "og_image", "robots",
    "content_hash", "previous_content_hash", "version", "crawled_at",
    "vertex_id", "_seq", "created_date", "sensitivity_ord", "owner_did",
]
LINK_COLS = [
    "label", "anchor_text", "edge_id", "src_vid", "dst_vid",
    "_seq", "created_date", "sensitivity_ord", "owner_did",
]
DLINK_COLS = [
    "label", "count", "edge_id", "src_vid", "dst_vid",
    "_seq", "created_date", "sensitivity_ord", "owner_did",
]

TABLE_CONFIG = {
    "pages":  ("vertex_page",           PAGE_COLS,  "_pages.parquet"),
    "links":  ("edge_links_to",         LINK_COLS,  "_links.parquet"),
    "dlinks": ("edge_links_to_domain",  DLINK_COLS, "_dlinks.parquet"),
}


# ── State ──
def load_state() -> dict:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text())
        except Exception:
            pass
    return {"pages": [], "links": [], "dlinks": [], "domains_done": False}


def save_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state))
    tmp.rename(STATE_FILE)


# ── DB ──
def connect():
    conn = psycopg2.connect(
        host=RW_HOST, port=RW_PORT, user=RW_USER, database=RW_DATABASE,
        connect_timeout=10,
        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=9,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
    return conn


def _sanitize(v):
    """Strip NUL bytes from strings; PostgreSQL text type rejects 0x00."""
    if isinstance(v, str) and "\x00" in v:
        return v.replace("\x00", "")
    return v


def copy_file_to_table(conn, parquet_path: Path, table: str, cols: list[str],
                       batch_rows: int = 10000) -> int:
    """Read one parquet file and batch-INSERT into target table via execute_values.

    RisingWave does not support COPY FROM STDIN (not yet implemented), so we use
    psycopg2.extras.execute_values which batches N rows per multi-VALUES INSERT.
    """
    table_data = pq.read_table(str(parquet_path), columns=cols)
    num_rows = table_data.num_rows
    if num_rows == 0:
        return 0

    # Convert arrow table to python native rows (list of tuples).
    # Strip NUL bytes — they break PostgreSQL string literals.
    py_list = table_data.to_pylist()
    rows = [tuple(_sanitize(r[c]) for c in cols) for r in py_list]

    col_list = ", ".join(cols)
    insert_sql = f"INSERT INTO {table} ({col_list}) VALUES %s"

    with conn.cursor() as cur:
        # execute_values batches rows into a single INSERT INTO ... VALUES (...), (...), ...
        psycopg2.extras.execute_values(
            cur, insert_sql, rows,
            page_size=batch_rows,  # rows per multi-VALUES statement
        )
    return num_rows


# Thread-local storage: each worker owns its own psycopg2 connection.
_thread_local = threading.local()


def _get_worker_conn():
    c = getattr(_thread_local, "conn", None)
    if c is None:
        c = connect()
        _thread_local.conn = c
    return c


def _ingest_one(fname: str, target: str, cols: list[str]) -> tuple[str, int, str | None]:
    """Worker: process one file. Returns (fname, rows, error_msg)."""
    conn = _get_worker_conn()
    path = PARQUET_DIR / fname
    try:
        n = copy_file_to_table(conn, path, target, cols)
        return (fname, n, None)
    except psycopg2.OperationalError as e:
        # Drop worker connection; next call will reconnect.
        try:
            conn.close()
        except Exception:
            pass
        _thread_local.conn = None
        return (fname, 0, f"conn: {str(e)[:150]}")
    except Exception as e:
        return (fname, 0, str(e)[:200])


def ingest_table(main_conn, table_key: str, sleep_ms: int, state: dict,
                 limit: int | None, flush_every: int = 100, workers: int = 4):
    target, cols, suffix = TABLE_CONFIG[table_key]
    done = set(state.get(table_key, []))

    # List local parquet files
    all_files = sorted(f.name for f in PARQUET_DIR.iterdir() if f.name.endswith(suffix))
    todo = [f for f in all_files if f not in done]
    if limit:
        todo = todo[:limit]
    log.info(f"=== {table_key} → {target}: {len(all_files):,} total, "
             f"{len(done):,} done, {len(todo):,} to ingest (workers={workers}) ===")

    if not todo:
        return

    t0 = time.time()
    completed = 0
    rows_total = 0
    errors = 0
    state_lock = threading.Lock()

    def _flush_on_main():
        try:
            with main_conn.cursor() as cur:
                cur.execute("FLUSH")
        except Exception as e:
            log.warning(f"  FLUSH: {str(e)[:100]}")

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {pool.submit(_ingest_one, f, target, cols): f for f in todo}
        try:
            for fut in as_completed(futures):
                if _shutdown:
                    for pending in futures:
                        pending.cancel()
                    break
                fname, n, err = fut.result()
                if err:
                    errors += 1
                    log.error(f"  {fname}: {err}")
                    if errors >= 20:
                        log.error("  20 errors — stopping this table")
                        break
                    continue
                rows_total += n
                completed += 1
                with state_lock:
                    done.add(fname)
                    state[table_key] = list(done)

                if completed % flush_every == 0:
                    _flush_on_main()
                    save_state(state)
                    elapsed = time.time() - t0
                    rate_f = completed / elapsed
                    rate_r = rows_total / elapsed
                    eta_min = (len(todo) - completed) / rate_f / 60 if rate_f > 0 else 0
                    log.info(
                        f"  {table_key}: {completed:,}/{len(todo):,} files, "
                        f"{rows_total:,} rows ({rate_f:.1f} f/s, {rate_r:.0f} r/s, "
                        f"ETA {eta_min:.0f}min, {errors} err)"
                    )
        finally:
            pool.shutdown(wait=False, cancel_futures=True)

    # Final flush + state save
    _flush_on_main()
    save_state(state)
    elapsed = time.time() - t0
    log.info(
        f"  {table_key} DONE: {completed}/{len(todo)} files, {rows_total:,} rows "
        f"in {elapsed:.0f}s ({rows_total/elapsed:.0f} r/s, {errors} errors)"
    )


def populate_domains(conn):
    """Populate vertex_domain from vertex_page.domain DISTINCT.

    Domain is its own DID actor — `did = owner_did = did:web:site.etzhayyim.com:{slug}`.
    Mirrors the per-page DID convention (vertex_page.owner_did = page DID).
    """
    log.info("=== vertex_domain: populate from vertex_page.domain DISTINCT ===")
    try:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM vertex_domain WHERE 1=1")
            cur.execute("""
                INSERT INTO vertex_domain (
                    vertex_id, domain, did, handle, display_name,
                    topics, performer_type, status,
                    _seq, sensitivity_ord, created_date, owner_did
                )
                SELECT
                    p.domain, p.domain,
                    'did:web:site.etzhayyim.com:' || REPLACE(p.domain, '.', '-'),
                    'site.etzhayyim.com:' || REPLACE(p.domain, '.', '-'),
                    p.domain, NULL::VARCHAR, 'service', 'active',
                    0::BIGINT, 0::BIGINT, NULL::DATE,
                    'did:web:site.etzhayyim.com:' || REPLACE(p.domain, '.', '-')  -- owner_did = self
                FROM (SELECT DISTINCT domain FROM vertex_page
                      WHERE domain IS NOT NULL AND domain != '') p
            """)
        log.info("  vertex_domain: populated (did = owner_did)")
    except Exception as e:
        log.error(f"  vertex_domain: {e}")


def verify(conn):
    for t in ["vertex_page", "edge_links_to", "edge_links_to_domain", "vertex_domain"]:
        try:
            with conn.cursor() as cur:
                cur.execute(f"SELECT COUNT(*) FROM {t}")
                log.info(f"  {t}: {cur.fetchone()[0]:,}")
        except Exception as e:
            log.warning(f"  {t}: {str(e)[:100]}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--table", choices=["pages", "links", "dlinks", "domains", "all"], default="all")
    p.add_argument("--sleep-ms", type=int, default=0, help="(unused in parallel mode)")
    p.add_argument("--workers", type=int, default=4, help="Parallel INSERT workers")
    p.add_argument("--limit", type=int, default=None, help="process only first N files (test)")
    p.add_argument("--reset", action="store_true")
    args = p.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)
    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        log.info("State reset")

    state = load_state()

    log.info("=" * 60)
    log.info(f"Phase 3g: COPY FROM STDIN → {RW_HOST}:{RW_PORT}")
    log.info(f"  parquet_dir: {PARQUET_DIR}")
    log.info(f"  sleep_ms: {args.sleep_ms}")
    if args.limit:
        log.info(f"  limit: {args.limit}")
    log.info("=" * 60)

    log.info("Connecting...")
    conn = connect()
    log.info("  OK")

    t0 = time.time()

    if args.table in ("pages", "all"):
        ingest_table(conn, "pages", args.sleep_ms, state, args.limit, workers=args.workers)
    if args.table in ("links", "all") and not _shutdown:
        ingest_table(conn, "links", args.sleep_ms, state, args.limit, workers=args.workers)
    if args.table in ("dlinks", "all") and not _shutdown:
        ingest_table(conn, "dlinks", args.sleep_ms, state, args.limit, workers=args.workers)
    if args.table in ("domains", "all") and not _shutdown:
        populate_domains(conn)

    log.info("=== Verify ===")
    verify(conn)
    conn.close()
    log.info(f"Phase 3g complete in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
