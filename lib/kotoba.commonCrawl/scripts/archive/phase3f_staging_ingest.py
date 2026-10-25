#!/usr/bin/env python3
"""ARCHIVED: Phase 3f: CC Parquet → RisingWave via streaming CREATE TABLE staging.

Superseded on 2026-04-13 by `phase3g_copy_ingest.py` on `path-j-cc-hummock`.

RisingWave の streaming S3 connector でstaging テーブルを作成。
CREATE TABLE は即座に返り、取り込みはバックグラウンドで実行される。
取り込み完了後、staging → vertex_page / edge_* へ INSERT。

Steps:
  1. CREATE TABLE cc_pages_staging WITH (connector='s3', ...) — 即返
  2. polling で SELECT COUNT(*) FROM cc_pages_staging を観察、stable で完了判定
  3. INSERT INTO vertex_page SELECT FROM cc_pages_staging
  4. links/dlinks 同様
  5. vertex_domain populate

Usage:
  python3 scripts/archive/phase3f_staging_ingest.py              # 全工程
  python3 scripts/archive/phase3f_staging_ingest.py --phase create   # staging のみ
  python3 scripts/archive/phase3f_staging_ingest.py --phase wait     # polling のみ
  python3 scripts/archive/phase3f_staging_ingest.py --phase insert   # staging → 本テーブル
  python3 scripts/archive/phase3f_staging_ingest.py --phase domains  # vertex_domain のみ
"""

import argparse
import logging
import os
import sys
import time

import psycopg2

RW_HOST = os.environ.get("RW_HOST", "45.32.79.245")
RW_PORT = int(os.environ.get("RW_PORT", "4566"))
RW_USER = os.environ.get("RW_USER", "root")
RW_DATABASE = os.environ.get("RW_DATABASE", "dev")

S3_BUCKET = "kagami-graphar"
S3_ENDPOINT = "https://sg-sin-1.linodeobjects.com"
S3_REGION = "sg-sin-2"
S3_ACCESS = os.environ.get("S3_ACCESS_KEY", "LJF40TXHIUSVGBRKXEFU")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "Wv5b0cNdv7wNoZuiSmnJAxMwlye1MHEl1C6TowgR")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    stream=sys.stdout,
)
log = logging.getLogger(__name__)


def connect():
    conn = psycopg2.connect(
        host=RW_HOST, port=RW_PORT, user=RW_USER, database=RW_DATABASE,
        connect_timeout=10,
        keepalives=1, keepalives_idle=30, keepalives_interval=10, keepalives_count=9,
    )
    conn.autocommit = True
    with conn.cursor() as cur:
        cur.execute("SET statement_timeout = 0")
        cur.execute("SET iceberg_engine_connection = 'public.kagami_iceberg'")
    return conn


S3_CONF = (
    f"s3.region_name='{S3_REGION}', "
    f"s3.bucket_name='{S3_BUCKET}', "
    f"s3.credentials.access='{S3_ACCESS}', "
    f"s3.credentials.secret='{S3_SECRET}', "
    f"s3.endpoint_url='{S3_ENDPOINT}'"
)

# Staging table definitions: streaming CREATE TABLE with s3_v2 connector.
STAGING = [
    (
        "cc_pages_staging",
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
        "cc_links_staging",
        """label VARCHAR, anchor_text VARCHAR,
           edge_id VARCHAR, src_vid VARCHAR, dst_vid VARCHAR,
           _seq BIGINT, created_date DATE, sensitivity_ord BIGINT, owner_did VARCHAR""",
        "cc-parquet/*_links.parquet",
    ),
    (
        "cc_dlinks_staging",
        """label VARCHAR, count BIGINT,
           edge_id VARCHAR, src_vid VARCHAR, dst_vid VARCHAR,
           _seq BIGINT, created_date DATE, sensitivity_ord BIGINT, owner_did VARCHAR""",
        "cc-parquet/*_dlinks.parquet",
    ),
]

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

TABLE_MAP = {
    "cc_pages_staging": ("vertex_page", PAGE_COLS),
    "cc_links_staging": ("edge_links_to", LINK_COLS),
    "cc_dlinks_staging": ("edge_links_to_domain", DLINK_COLS),
}


def drop_staging(conn):
    with conn.cursor() as cur:
        for name, _, _ in STAGING:
            try:
                cur.execute(f"DROP TABLE IF EXISTS {name} CASCADE")
                log.info(f"  DROP TABLE {name}: OK")
            except Exception as e:
                log.warning(f"  DROP {name}: {e}")


def create_staging(conn):
    with conn.cursor() as cur:
        for name, cols, pattern in STAGING:
            sql = (
                f"CREATE TABLE {name} ({cols})\n"
                f"WITH (connector='s3', match_pattern='{pattern}', {S3_CONF})\n"
                f"FORMAT PLAIN ENCODE PARQUET"
            )
            t0 = time.time()
            try:
                cur.execute(sql)
                log.info(f"  CREATE TABLE {name}: returned in {time.time()-t0:.1f}s (streaming)")
            except Exception as e:
                log.error(f"  CREATE TABLE {name} failed: {e}")
                raise


def count(conn, table: str) -> int:
    with conn.cursor() as cur:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        return cur.fetchone()[0]


def wait_for_staging(conn, stable_checks: int = 3, poll_interval: int = 60):
    """Poll staging tables until row counts are stable for N consecutive checks."""
    tables = [name for name, _, _ in STAGING]
    history = {t: [] for t in tables}
    stable = {t: 0 for t in tables}
    all_stable = False
    iteration = 0

    while not all_stable:
        iteration += 1
        line_parts = [f"iter={iteration}"]
        for t in tables:
            try:
                c = count(conn, t)
            except Exception as e:
                log.error(f"  {t}: count error {e}")
                c = -1
            prev = history[t][-1] if history[t] else None
            history[t].append(c)
            if prev is not None and c == prev and c > 0:
                stable[t] += 1
            else:
                stable[t] = 0
            line_parts.append(f"{t}={c:,}({'S' if stable[t]>=stable_checks else stable[t]})")
        log.info("  " + " ".join(line_parts))

        all_stable = all(stable[t] >= stable_checks for t in tables)
        if all_stable:
            break
        time.sleep(poll_interval)

    log.info("  All staging tables stable.")


def insert_to_target(conn):
    for staging_name, (target, cols) in TABLE_MAP.items():
        sql = f"INSERT INTO {target} ({cols}) SELECT {cols} FROM {staging_name}"
        log.info(f"  INSERT {staging_name} → {target} ...")
        t0 = time.time()
        try:
            with conn.cursor() as cur:
                cur.execute("SET statement_timeout = 0")
                cur.execute("SET iceberg_engine_connection = 'public.kagami_iceberg'")
                cur.execute(sql)
            elapsed = time.time() - t0
            log.info(f"    done in {elapsed:.0f}s")
        except Exception as e:
            log.error(f"    FAILED: {e}")
            raise


def populate_domains(conn):
    sql = """INSERT INTO vertex_domain (
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
            cur.execute("DELETE FROM vertex_domain WHERE 1=1")
            cur.execute(sql)
        log.info("  vertex_domain: populated")
    except Exception as e:
        log.error(f"  vertex_domain: {e}")


def verify(conn):
    for t in ["vertex_page", "edge_links_to", "edge_links_to_domain", "vertex_domain"]:
        try:
            log.info(f"  {t}: {count(conn, t):,}")
        except Exception as e:
            log.warning(f"  {t}: {e}")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--phase", choices=["create", "wait", "insert", "domains", "verify", "all"], default="all")
    p.add_argument("--poll-interval", type=int, default=60)
    p.add_argument("--stable-checks", type=int, default=3)
    p.add_argument("--drop-first", action="store_true", help="DROP staging tables first")
    args = p.parse_args()

    log.info(f"Connecting {RW_HOST}:{RW_PORT}...")
    conn = connect()
    log.info("  OK")

    if args.phase in ("create", "all"):
        log.info("=== Step 1: Drop + Create staging tables (streaming) ===")
        drop_staging(conn)
        create_staging(conn)

    if args.phase in ("wait", "all"):
        log.info("=== Step 2: Wait for staging ingestion ===")
        wait_for_staging(conn, stable_checks=args.stable_checks, poll_interval=args.poll_interval)

    if args.phase in ("insert", "all"):
        log.info("=== Step 3: INSERT staging → target tables ===")
        insert_to_target(conn)

    if args.phase in ("domains", "all"):
        log.info("=== Step 4: Populate vertex_domain ===")
        populate_domains(conn)

    log.info("=== Verify ===")
    verify(conn)
    conn.close()


if __name__ == "__main__":
    main()
