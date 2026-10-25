#!/usr/bin/env python3
"""Phase 3h: Transform existing parquet (old SHA-hex rkey) → new URL-path-DID parquet.

Reads every `batch_*_pages.parquet` from the legacy output dir, derives
per-page `rkey` (URL-path slug) + `owner_did` (page DID) from the `url`
column, and writes a new parquet with the updated columns preserved.

Mirrors the Rust `page_did_from_url` helper in
`60-apps/etzhayyim-project-common-crawl/rust/cc-phase3/src/main.rs`.

Skips WAT decompression entirely — this runs ~100x faster than
re-executing cc-phase3 on the full 14.8 TB WAT corpus.

Usage:
  python3 phase3h_transform_parquet.py                  # all pages parquet
  python3 phase3h_transform_parquet.py --limit 10       # first 10 batches (smoke)
  python3 phase3h_transform_parquet.py --workers 8      # parallel

Environment:
  CC_PARQUET_DIR   source dir (default /Volumes/251220/CC/2603/parquet-rs)
  CC_PARQUET_V2    dest   dir (default /Volumes/251220/CC/2603/parquet-rs-v2)

Links / dlinks are NOT transformed here — src_vid/dst_vid are SHA-hex
without URL back-references, so rewriting them requires a separate
alias-backfill step after new page rows are ingested (SEE phase3i).
"""

import argparse
import hashlib
import logging
import os
import signal
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import urlparse

import pyarrow as pa
import pyarrow.parquet as pq

SRC_DIR = Path(os.environ.get("CC_PARQUET_DIR", "/Volumes/251220/CC/2603/parquet-rs"))
DST_DIR = Path(os.environ.get("CC_PARQUET_V2", "/Volumes/251220/CC/2603/parquet-rs-v2"))
DID_PREFIX = "did:web:site.etzhayyim.com:"
PAGE_DID_MAX_LEN = 2048
SAFE_CHARS = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-._")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s",
                    handlers=[logging.StreamHandler(sys.stdout)])
log = logging.getLogger(__name__)

_shutdown = False


def _sig(sig, frame):
    global _shutdown
    _shutdown = True


signal.signal(signal.SIGINT, _sig)
signal.signal(signal.SIGTERM, _sig)


def encode_segment(s: str) -> str:
    """Percent-encode path segment, matching Rust encode_segment()."""
    out = []
    for b in s.encode("utf-8"):
        c = chr(b)
        if c in SAFE_CHARS:
            out.append(c)
        else:
            out.append(f"%{b:02X}")
    return "".join(out)


def domain_to_slug(domain: str) -> str:
    return domain.replace(".", "-").replace("_", "-")


def page_did_from_url(url: str, domain: str | None) -> tuple[str, str] | None:
    """Return (rkey, did) from URL. Matches Rust page_did_from_url()."""
    if not url or not domain:
        return None
    domain_slug = domain_to_slug(domain)
    try:
        parsed = urlparse(url)
    except Exception:
        return None
    path = parsed.path or ""
    # Strip query / fragment — urlparse already does that for us
    segments = [encode_segment(s) for s in path.split("/") if s]
    if not segments:
        rkey = f"{domain_slug}:_root"
    else:
        rkey = f"{domain_slug}:{':'.join(segments)}"
    did = f"{DID_PREFIX}{rkey}"
    if len(did) > PAGE_DID_MAX_LEN:
        h = hashlib.sha256(url.encode("utf-8")).hexdigest()[:16]
        rkey = f"{domain_slug}:_h:{h}"
        did = f"{DID_PREFIX}{rkey}"
    return (rkey, did)


def transform_one(src_path: Path, dst_path: Path) -> tuple[str, int, str]:
    """Transform one batch_*_pages.parquet file. Returns (name, rows, status)."""
    if dst_path.exists() and dst_path.stat().st_size > 0:
        return (src_path.name, 0, "skip")
    try:
        t = pq.read_table(src_path)
        urls = t.column("url").to_pylist()
        domains = t.column("domain").to_pylist()

        new_rkeys = []
        new_owner_dids = []
        for url, domain in zip(urls, domains):
            result = page_did_from_url(url or "", domain or "")
            if result is None:
                new_rkeys.append(None)
                new_owner_dids.append(None)
            else:
                new_rkeys.append(result[0])
                new_owner_dids.append(result[1])

        # Replace rkey, vertex_id, owner_did columns in-place
        t = t.drop(["rkey", "vertex_id", "owner_did"])
        t = t.append_column("rkey", pa.array(new_rkeys, pa.string()))
        t = t.append_column("vertex_id", pa.array(new_rkeys, pa.string()))
        t = t.append_column("owner_did", pa.array(new_owner_dids, pa.string()))

        # Drop rows with null rkey (url parse failed)
        mask = pa.compute.is_valid(t.column("rkey"))
        t = t.filter(mask)

        pq.write_table(t, dst_path, compression="zstd")
        return (src_path.name, t.num_rows, "ok")
    except Exception as e:
        return (src_path.name, 0, f"err:{str(e)[:100]}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--workers", type=int, default=4)
    parser.add_argument("--limit", type=int, default=0, help="first N batches only (smoke)")
    parser.add_argument("--src", type=str, default=str(SRC_DIR))
    parser.add_argument("--dst", type=str, default=str(DST_DIR))
    args = parser.parse_args()

    src = Path(args.src)
    dst = Path(args.dst)
    dst.mkdir(parents=True, exist_ok=True)

    log.info(f"Scanning {src} for batch_*_pages.parquet…")
    src_files = sorted(src.glob("batch_*_pages.parquet"))
    if args.limit > 0:
        src_files = src_files[:args.limit]
    log.info(f"Transforming {len(src_files)} pages parquet files with {args.workers} workers")

    t0 = time.time()
    done = 0
    rows_total = 0
    errors = 0
    skipped = 0

    with ProcessPoolExecutor(max_workers=args.workers) as ex:
        futs = {ex.submit(transform_one, s, dst / s.name): s for s in src_files}
        for fut in as_completed(futs):
            if _shutdown:
                break
            name, rows, status = fut.result()
            done += 1
            if status == "ok":
                rows_total += rows
            elif status == "skip":
                skipped += 1
            else:
                errors += 1
                log.warning(f"  {name}: {status}")
            if done % 100 == 0 or done == len(src_files):
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta_min = (len(src_files) - done) / rate / 60 if rate > 0 else 0
                log.info(f"  {done}/{len(src_files)} ({rate:.1f} f/s, ETA {eta_min:.0f}min, "
                         f"rows={rows_total:,}, skip={skipped}, err={errors})")

    elapsed = time.time() - t0
    log.info(f"Done: {done} files, {rows_total:,} rows, {skipped} skipped, {errors} errors "
             f"in {elapsed:.0f}s")


if __name__ == "__main__":
    main()
