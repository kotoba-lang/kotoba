#!/usr/bin/env python3
"""Phase 3i: Populate vertex_did_alias by JOINing legacy + canonical vertex_page rows.

Runs after phase3h transform + phase3g ingest so that both rkey formats
coexist in `vertex_page`. Joins old (SHA-16 hex rkey, null owner_did) with
new (URL-slug rkey, page-DID owner_did) on URL, emits one alias row per
pair.

Usage:
  python3 phase3i_alias_backfill.py                    # full backfill
  python3 phase3i_alias_backfill.py --dry-run          # count only
  python3 phase3i_alias_backfill.py --batch-size 5000  # smaller batches
  python3 phase3i_alias_backfill.py --domain example.com  # scope to domain

Uses streaming pagination to avoid loading 80M+ rows into memory.

Invariants:
  - source rows live in `vertex_page` (already ingested)
  - target table is `vertex_did_alias` (migration 0026)
  - alias_kind = 'cc-sha-to-url-slug'
  - canonical_did = page DID (did:web:site.etzhayyim.com:{rkey})
  - legacy_did = NULL (legacy rows never had a page-level DID)
  - resumable: skips rows whose vertex_did_alias.vertex_id already exists
"""

import argparse
import logging
import os
import signal
import sys
import time

import psycopg2
import psycopg2.extras

RW_HOST = os.environ.get("RW_HOST", "45.32.79.245")
RW_PORT = int(os.environ.get("RW_PORT", "4566"))
RW_USER = os.environ.get("RW_USER", "root")
RW_DB = os.environ.get("RW_DATABASE", "dev")

logging.basicConfig(level=logging.INFO,
                    format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

_shutdown = False


def _sig(sig, frame):
    global _shutdown
    _shutdown = True


signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)


def connect():
    return psycopg2.connect(
        host=RW_HOST, port=RW_PORT, user=RW_USER, dbname=RW_DB,
        connect_timeout=30, keepalives=1, keepalives_idle=30,
        keepalives_interval=10, keepalives_count=5,
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--dry-run", action="store_true")
    p.add_argument("--batch-size", type=int, default=10000)
    p.add_argument("--domain", type=str, default="",
                   help="scope to one domain (for smoke testing)")
    args = p.parse_args()

    conn = connect()
    conn.autocommit = False
    cur = conn.cursor()

    where = "new.url IS NOT NULL AND new.rkey LIKE '%:%' AND old.rkey NOT LIKE '%:%'"
    if args.domain:
        where += f" AND new.domain = '{args.domain.replace(chr(39), chr(39)*2)}'"

    # Preview count
    log.info("Counting alias candidates…")
    cur.execute(f"""
        SELECT COUNT(*)
        FROM vertex_page new
        JOIN vertex_page old ON old.url = new.url
        WHERE {where}
    """)
    total = cur.fetchone()[0]
    log.info(f"  {total:,} (url, legacy_rkey, canonical_rkey) pairs to alias")

    if args.dry_run or total == 0:
        conn.close()
        return

    t0 = time.time()
    inserted = 0
    offset = 0

    while offset < total:
        if _shutdown:
            log.info("Shutdown requested")
            break
        cur.execute(f"""
            INSERT INTO vertex_did_alias
              (vertex_id, canonical_did, canonical_rkey, canonical_collection,
               legacy_did, legacy_rkey, legacy_collection,
               alias_kind, url, domain, first_seen_at,
               _seq, sensitivity_ord, owner_did)
            SELECT
              new.owner_did AS vertex_id,
              new.owner_did AS canonical_did,
              new.rkey      AS canonical_rkey,
              'com.etzhayyim.apps.site.page' AS canonical_collection,
              NULL          AS legacy_did,
              old.rkey      AS legacy_rkey,
              'com.etzhayyim.apps.site.page' AS legacy_collection,
              'cc-sha-to-url-slug' AS alias_kind,
              new.url       AS url,
              new.domain    AS domain,
              NOW()         AS first_seen_at,
              0, 0,
              new.owner_did AS owner_did
            FROM vertex_page new
            JOIN vertex_page old ON old.url = new.url
            WHERE {where}
              AND NOT EXISTS (
                SELECT 1 FROM vertex_did_alias a WHERE a.vertex_id = new.owner_did
              )
            LIMIT {args.batch_size}
        """)
        inserted_batch = cur.rowcount if cur.rowcount else 0
        conn.commit()
        inserted += inserted_batch
        elapsed = time.time() - t0
        rate = inserted / elapsed if elapsed > 0 else 0
        eta_min = (total - inserted) / rate / 60 if rate > 0 else 0
        log.info(f"  inserted={inserted:,}/{total:,} ({rate:.0f} r/s, ETA {eta_min:.0f}min)")

        if inserted_batch == 0:
            # No more rows (NOT EXISTS filter consumed the batch)
            break
        offset += args.batch_size

    log.info(f"Done: {inserted:,} alias rows in {time.time() - t0:.0f}s")
    conn.close()


if __name__ == "__main__":
    main()
