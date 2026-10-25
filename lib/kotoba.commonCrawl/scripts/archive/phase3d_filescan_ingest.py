#!/usr/bin/env python3
"""ARCHIVED: Phase 3d: CC Parquet → RisingWave via file_scan() per file (Hyperdrive XRPC).

Superseded on 2026-04-13 by `phase3g_copy_ingest.py` on `path-j-cc-hummock`.

SOURCE ベースの wildcard enumeration を回避するため、各 parquet ファイルを
file_scan() で個別に読み込む。1 ファイル = 1 INSERT → S3 listing なし。

Usage:
  python3 scripts/archive/phase3d_filescan_ingest.py                        # 全テーブル
  python3 scripts/archive/phase3d_filescan_ingest.py --table pages          # pages のみ
  python3 scripts/archive/phase3d_filescan_ingest.py --table links
  python3 scripts/archive/phase3d_filescan_ingest.py --table dlinks
  python3 scripts/archive/phase3d_filescan_ingest.py --workers 4            # 並列ワーカー
  python3 scripts/archive/phase3d_filescan_ingest.py --dry-run
  python3 scripts/archive/phase3d_filescan_ingest.py --reset                # 状態リセット
"""

import argparse
import json
import logging
import os
import signal
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
import httpx
from botocore.config import Config

# ── Config ──

PARQUET_DIR = Path(os.environ.get("CC_PARQUET_DIR", "/Volumes/251220/CC/2603/parquet-rs"))
STATE_DIR = Path(os.environ.get("CC_DATA_DIR", "/Volumes/251220/CC/2603")) / "scripts"
STATE_FILE = STATE_DIR / ".phase3d_filescan_state.json"

S3_BUCKET = "kagami-graphar"
S3_PREFIX = "cc-parquet"
S3_ENDPOINT = "https://sg-sin-1.linodeobjects.com"
S3_REGION = "sg-sin-2"
S3_ACCESS = os.environ.get("S3_ACCESS_KEY", "LJF40TXHIUSVGBRKXEFU")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "Wv5b0cNdv7wNoZuiSmnJAxMwlye1MHEl1C6TowgR")

GRAPH_XRPC_URL = os.environ.get(
    "GRAPH_XRPC_URL",
    "https://graph.etzhayyim.com/xrpc/com.etzhayyim.kagami.sql",
)
XRPC_TIMEOUT = int(os.environ.get("XRPC_TIMEOUT", "120"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(STATE_DIR / "phase3d_filescan.log"),
    ],
)
log = logging.getLogger(__name__)

_shutdown = False


def _signal_handler(sig, frame):
    global _shutdown
    log.info("Shutdown requested — will stop after current file")
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
    return {"pages_done": [], "links_done": [], "dlinks_done": []}


def save_state(state: dict):
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(state, indent=2))
    tmp.rename(STATE_FILE)


# ── S3 file listing ──

def list_s3_files(suffix: str) -> list[str]:
    """List all S3 keys matching cc-parquet/*_{suffix}.parquet"""
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS,
        aws_secret_access_key=S3_SECRET,
        region_name=S3_REGION,
        config=Config(request_checksum_calculation="when_required"),
    )
    keys = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_PREFIX}/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(f"_{suffix}.parquet"):
                keys.append(key)
    return sorted(keys)


# ── XRPC ──

def xrpc_sql(sql: str, timeout: int = XRPC_TIMEOUT) -> dict:
    resp = httpx.post(
        GRAPH_XRPC_URL,
        json={"statement": sql},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        raise RuntimeError(f"XRPC {resp.status_code}: {resp.text[:300]}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"XRPC error: {data['error']} — {data.get('message', '')}")
    return data


# ── Column definitions ──

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

PAGE_SCHEMA = (
    "rkey VARCHAR, url VARCHAR, domain VARCHAR, title VARCHAR, "
    "description VARCHAR, language VARCHAR, content_type VARCHAR, "
    "status_code VARCHAR, outlink_count BIGINT, crawl VARCHAR, "
    "ip_address VARCHAR, og_image VARCHAR, robots VARCHAR, "
    "content_hash VARCHAR, previous_content_hash VARCHAR, "
    "version BIGINT, crawled_at VARCHAR, "
    "vertex_id VARCHAR, _seq BIGINT, created_date DATE, "
    "sensitivity_ord BIGINT, owner_did VARCHAR"
)

LINK_SCHEMA = (
    "label VARCHAR, anchor_text VARCHAR, "
    "edge_id VARCHAR, src_vid VARCHAR, dst_vid VARCHAR, "
    "_seq BIGINT, created_date DATE, sensitivity_ord BIGINT, owner_did VARCHAR"
)

DLINK_SCHEMA = (
    "label VARCHAR, count BIGINT, "
    "edge_id VARCHAR, src_vid VARCHAR, dst_vid VARCHAR, "
    "_seq BIGINT, created_date DATE, sensitivity_ord BIGINT, owner_did VARCHAR"
)

S3_CREDS = (
    f"'{S3_ACCESS}', '{S3_SECRET}', "
    f"'{{\"endpoint\": \"{S3_ENDPOINT}\", \"region\": \"{S3_REGION}\"}}'"
)


def make_insert_sql(table: str, cols: str, schema: str, s3_key: str) -> str:
    """file_scan() INSERT for a single parquet file."""
    s3_path = f"s3://{S3_BUCKET}/{s3_key}"
    return (
        f"INSERT INTO {table} ({cols})\n"
        f"SELECT {cols} FROM file_scan(\n"
        f"  'parquet',\n"
        f"  '{s3_path}',\n"
        f"  {S3_CREDS},\n"
        f"  {schema}\n"
        f")"
    )


# ── Per-file INSERT ──

def insert_file(table: str, cols: str, schema: str, s3_key: str, dry_run: bool) -> tuple[str, bool, float]:
    """Insert one parquet file. Returns (key, success, elapsed)."""
    if dry_run:
        return s3_key, True, 0.0
    sql = make_insert_sql(table, cols, schema, s3_key)
    t0 = time.time()
    try:
        xrpc_sql(sql)
        return s3_key, True, time.time() - t0
    except Exception as e:
        log.error(f"  FAILED {s3_key}: {str(e)[:200]}")
        return s3_key, False, time.time() - t0


def ingest_table(
    table: str,
    cols: str,
    schema: str,
    suffix: str,
    state_key: str,
    state: dict,
    workers: int = 1,
    dry_run: bool = False,
):
    log.info(f"=== {table}: listing S3 files (*_{suffix}.parquet) ===")
    s3_keys = list_s3_files(suffix)
    done = set(state.get(state_key, []))
    to_do = [k for k in s3_keys if k not in done]
    log.info(f"  {len(s3_keys):,} total, {len(done):,} done, {len(to_do):,} remaining")

    if not to_do:
        log.info(f"  {table}: nothing to do")
        return

    t0 = time.time()
    completed = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=workers) as pool:
        futures = {
            pool.submit(insert_file, table, cols, schema, key, dry_run): key
            for key in to_do
            if not _shutdown
        }
        for fut in as_completed(futures):
            if _shutdown:
                break
            key, ok, elapsed = fut.result()
            if ok:
                completed += 1
                done.add(key)
                state[state_key] = list(done)
                if completed % 100 == 0:
                    save_state(state)
                    total_elapsed = time.time() - t0
                    rate = completed / total_elapsed if total_elapsed > 0 else 0
                    eta = (len(to_do) - completed) / rate / 60 if rate > 0 else 0
                    log.info(
                        f"  {table}: {completed}/{len(to_do)} "
                        f"({rate:.1f} files/s, ETA {eta:.0f}min, {errors} errors)"
                    )
            else:
                errors += 1

    save_state(state)
    elapsed = time.time() - t0
    log.info(
        f"  {table}: {completed}/{len(to_do)} done, {errors} errors "
        f"in {elapsed:.0f}s ({completed/elapsed:.1f} files/s)"
    )


def verify():
    tables = ["vertex_page", "edge_links_to", "edge_links_to_domain", "vertex_domain"]
    for t in tables:
        try:
            result = xrpc_sql(f"SELECT COUNT(*) AS cnt FROM {t}", timeout=30)
            count = result.get("rows", [{}])[0].get("cnt", "?")
            log.info(f"  {t}: {count}")
        except Exception as e:
            log.warning(f"  {t}: {e}")


def populate_domains(dry_run: bool = False):
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

    if dry_run:
        log.info("  [DRY-RUN] would populate vertex_domain")
        return
    try:
        xrpc_sql("DELETE FROM vertex_domain WHERE 1=1", timeout=60)
        log.info("  vertex_domain: cleared")
    except Exception as e:
        log.warning(f"  vertex_domain DELETE: {e}")
    try:
        xrpc_sql(insert_sql, timeout=300)
        log.info("  vertex_domain: populated")
    except Exception as e:
        log.error(f"  vertex_domain INSERT: {e}")


def main():
    p = argparse.ArgumentParser(description="Phase 3d: file_scan() per-file ingestion")
    p.add_argument("--table", choices=["pages", "links", "dlinks", "domains", "all"], default="all")
    p.add_argument("--workers", type=int, default=1, help="Parallel INSERT workers (default: 1)")
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--reset", action="store_true")
    args = p.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        log.info("State reset")

    state = load_state()

    log.info("=" * 60)
    log.info("Phase 3d: file_scan() per-file → RisingWave via Hyperdrive")
    log.info(f"  XRPC: {GRAPH_XRPC_URL}")
    log.info(f"  S3: s3://{S3_BUCKET}/{S3_PREFIX}/")
    log.info(f"  Workers: {args.workers}")
    log.info("=" * 60)

    # Test connection
    try:
        result = xrpc_sql("SELECT 1 AS ok", timeout=10)
        log.info(f"  XRPC connection: OK ({result})")
    except Exception as e:
        log.error(f"  XRPC connection FAILED: {e}")
        return

    t0 = time.time()

    if args.table in ("pages", "all"):
        ingest_table("vertex_page", PAGE_COLS, PAGE_SCHEMA, "pages",
                     "pages_done", state, workers=args.workers, dry_run=args.dry_run)

    if args.table in ("links", "all") and not _shutdown:
        ingest_table("edge_links_to", LINK_COLS, LINK_SCHEMA, "links",
                     "links_done", state, workers=args.workers, dry_run=args.dry_run)

    if args.table in ("dlinks", "all") and not _shutdown:
        ingest_table("edge_links_to_domain", DLINK_COLS, DLINK_SCHEMA, "dlinks",
                     "dlinks_done", state, workers=args.workers, dry_run=args.dry_run)

    if args.table in ("domains", "all") and not _shutdown:
        log.info("=== vertex_domain ===")
        populate_domains(dry_run=args.dry_run)

    if not _shutdown:
        log.info("=== Verify ===")
        verify()

    log.info(f"Phase 3d complete in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
