#!/usr/bin/env python3
"""Phase 3j: Upload all parquet to S3 cc-parquet-v2/ prefix for S3-connector ingest.

  pages  → parquet-rs-v2/ (new URL-slug rkey, phase3h output)
  links  → parquet-rs/    (old SHA-hex src/dst, resolved at query via alias VIEW)
  dlinks → parquet-rs/    (old SHA-hex src/dst, resolved at query via alias VIEW)

After upload, use CREATE TABLE ... WITH (connector='s3') + ALTER TABLE SWAP
to atomically replace the live tables without TRUNCATE.

Usage:
  python3 scripts/phase3j_s3_upload_v2.py                  # upload all 3 types
  python3 scripts/phase3j_s3_upload_v2.py --type pages     # pages only
  python3 scripts/phase3j_s3_upload_v2.py --workers 16
  python3 scripts/phase3j_s3_upload_v2.py --dry-run
"""

import argparse
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.config import Config

# Source directories
PAGES_DIR  = Path(os.environ.get("CC_PARQUET_V2",  "/Volumes/251220/CC/2603/parquet-rs-v2"))
LINKS_DIR  = Path(os.environ.get("CC_PARQUET_DIR", "/Volumes/251220/CC/2603/parquet-rs"))
DLINKS_DIR = LINKS_DIR  # same dir

S3_BUCKET   = "kagami-graphar"
S3_PREFIX   = "cc-parquet-v2"
S3_ENDPOINT = "https://sg-sin-1.linodeobjects.com"
S3_REGION   = "sg-sin-1"
S3_ACCESS   = os.environ.get("S3_ACCESS_KEY", "LJF40TXHIUSVGBRKXEFU")
S3_SECRET   = os.environ.get("S3_SECRET_KEY", "Wv5b0cNdv7wNoZuiSmnJAxMwlye1MHEl1C6TowgR")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()],
)
log = logging.getLogger(__name__)


def make_s3():
    return boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS,
        aws_secret_access_key=S3_SECRET,
        region_name=S3_REGION,
        config=Config(
            request_checksum_calculation="when_required",
            max_pool_connections=64,
        ),
    )


def list_s3_prefix(s3, prefix: str) -> set[str]:
    """Return set of filenames (not full keys) already on S3 under prefix."""
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{prefix}/"):
        for obj in page.get("Contents", []):
            existing.add(obj["Key"].split("/")[-1])
    return existing


def upload_one(local_path: Path, s3_key: str, dry_run: bool) -> tuple[str, bool]:
    if dry_run:
        return (local_path.name, True)
    s3 = make_s3()
    try:
        s3.upload_file(str(local_path), S3_BUCKET, s3_key)
        return (local_path.name, True)
    except Exception as e:
        log.error(f"  FAIL {local_path.name}: {e}")
        return (local_path.name, False)


def upload_batch(label: str, src_dir: Path, glob_pattern: str,
                 workers: int, dry_run: bool):
    s3 = make_s3()
    prefix = S3_PREFIX
    log.info(f"[{label}] Listing s3://{S3_BUCKET}/{prefix}/ …")
    existing = list_s3_prefix(s3, prefix)
    log.info(f"  {len(existing):,} files already on S3")

    files = sorted(src_dir.glob(glob_pattern))
    todo = [f for f in files if f.name not in existing]
    log.info(f"  {len(files):,} local, {len(todo):,} to upload, workers={workers}")

    if not todo:
        log.info(f"  [{label}] all done, skipping.")
        return

    t0 = time.time()
    done = errors = 0

    with ThreadPoolExecutor(max_workers=workers) as ex:
        futs = {
            ex.submit(upload_one, f, f"{prefix}/{f.name}", dry_run): f
            for f in todo
        }
        for fut in as_completed(futs):
            name, ok = fut.result()
            done += 1
            if not ok:
                errors += 1
            if done % 500 == 0 or done == len(todo):
                elapsed = time.time() - t0
                rate = done / elapsed if elapsed > 0 else 0
                eta = (len(todo) - done) / rate / 60 if rate > 0 else 0
                log.info(
                    f"  [{label}] {done}/{len(todo)} "
                    f"({rate:.1f} f/s, ETA {eta:.0f}min, err={errors})"
                )

    elapsed = time.time() - t0
    log.info(
        f"  [{label}] done: {done} files in {elapsed:.0f}s "
        f"({done/elapsed:.1f} f/s), {errors} errors"
    )


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--type", choices=["pages", "links", "dlinks", "all"],
                   default="all", help="which table type to upload")
    p.add_argument("--workers", type=int, default=16)
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    log.info(f"S3 target: s3://{S3_BUCKET}/{S3_PREFIX}/")
    log.info(f"  pages src:  {PAGES_DIR}  (new URL-slug format)")
    log.info(f"  links src:  {LINKS_DIR}  (old SHA-hex, alias VIEW resolves at query)")
    log.info(f"  dlinks src: {DLINKS_DIR} (old SHA-hex, alias VIEW resolves at query)")

    if args.type in ("pages", "all"):
        upload_batch("pages",  PAGES_DIR,  "batch_*_pages.parquet",  args.workers, args.dry_run)
    if args.type in ("links", "all"):
        upload_batch("links",  LINKS_DIR,  "batch_*_links.parquet",  args.workers, args.dry_run)
    if args.type in ("dlinks", "all"):
        upload_batch("dlinks", DLINKS_DIR, "batch_*_dlinks.parquet", args.workers, args.dry_run)

    log.info("All uploads complete.")


if __name__ == "__main__":
    main()
