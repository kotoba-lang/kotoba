#!/usr/bin/env python3
"""Parallel S3 upload for CC Parquet files.

s3_upload_and_ingest.py のシングルスレッドアップロードを並列化。
concurrent.futures.ThreadPoolExecutor で --workers 並列アップロード。

Usage:
  python3 scripts/s3_upload_parallel.py             # 全ファイル並列アップロード
  python3 scripts/s3_upload_parallel.py --workers 16
  python3 scripts/s3_upload_parallel.py --dry-run
"""

import argparse
import logging
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import boto3
from botocore.config import Config

PARQUET_DIR = Path(os.environ.get("CC_PARQUET_DIR", "/Volumes/251220/CC/2603/parquet-rs"))
S3_BUCKET = "kagami-graphar"
S3_PREFIX = "cc-parquet"
S3_ENDPOINT = "https://sg-sin-1.linodeobjects.com"
S3_REGION = "sg-sin-2"
S3_ACCESS = os.environ.get("S3_ACCESS_KEY", "LJF40TXHIUSVGBRKXEFU")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "Wv5b0cNdv7wNoZuiSmnJAxMwlye1MHEl1C6TowgR")

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
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
            max_pool_connections=50,
        ),
    )


def upload_one(fname: str) -> bool:
    s3 = make_s3()
    local = PARQUET_DIR / fname
    key = f"{S3_PREFIX}/{fname}"
    try:
        s3.upload_file(str(local), S3_BUCKET, key)
        return True
    except Exception as e:
        log.error(f"  FAILED {fname}: {e}")
        return False


def main():
    p = argparse.ArgumentParser(description="Parallel S3 upload for CC Parquet")
    p.add_argument("--workers", type=int, default=8, help="並列ワーカー数 (default: 8)")
    p.add_argument("--dry-run", action="store_true")
    args = p.parse_args()

    s3 = make_s3()

    # 既存 S3 ファイルをリスト
    log.info(f"Listing s3://{S3_BUCKET}/{S3_PREFIX}/ ...")
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_PREFIX}/"):
        for obj in page.get("Contents", []):
            existing.add(obj["Key"].split("/")[-1])
    log.info(f"  {len(existing):,} files already on S3")

    all_files = sorted(f for f in os.listdir(PARQUET_DIR) if f.endswith(".parquet"))
    to_upload = [f for f in all_files if f not in existing]
    log.info(f"  {len(all_files):,} local files, {len(to_upload):,} to upload, workers={args.workers}")

    if dry_run := args.dry_run:
        log.info(f"  [DRY-RUN] would upload {len(to_upload):,} files")
        return

    if not to_upload:
        log.info("  Nothing to upload")
        return

    t0 = time.time()
    uploaded = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = {pool.submit(upload_one, f): f for f in to_upload}
        for fut in as_completed(futures):
            if fut.result():
                uploaded += 1
            else:
                errors += 1

            if (uploaded + errors) % 1000 == 0:
                elapsed = time.time() - t0
                rate = (uploaded + errors) / elapsed
                eta = (len(to_upload) - uploaded - errors) / rate / 60 if rate > 0 else 0
                log.info(
                    f"  {uploaded + errors:,}/{len(to_upload):,} "
                    f"({rate:.0f} files/s, ETA {eta:.0f}min, {errors} errors)"
                )

    elapsed = time.time() - t0
    rate = uploaded / elapsed if elapsed > 0 else 0
    log.info(f"Upload complete: {uploaded:,} new, {errors} errors in {elapsed:.0f}s ({rate:.0f} files/s)")


if __name__ == "__main__":
    main()
