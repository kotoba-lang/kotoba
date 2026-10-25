#!/usr/bin/env python3
"""ARCHIVED: Phase 3c: CC Parquet → RisingWave via Hyperdrive (graph Worker XRPC).

Superseded on 2026-04-13 by `phase3g_copy_ingest.py` on `path-j-cc-hummock`.

データフロー:
  Local Parquet → S3 (boto3 upload, skip existing)
  → CREATE SOURCE in RisingWave (via graph.etzhayyim.com XRPC → Hyperdrive)
  → Chunked INSERT INTO vertex_page / edge_* (via XRPC → Hyperdrive)

全 SQL は Cloudflare graph Worker の XRPC エンドポイントを通して実行する。
Hyperdrive が CF Worker ↔ RisingWave の PG 接続をプールする。

Usage:
  # 全ステップ (upload + source作成 + INSERT + vertex_domain)
  python3 scripts/archive/phase3c_hyperdrive_ingest.py

  # S3 アップロードのみ
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --phase upload

  # DB 取り込みのみ (S3 upload 済みの場合)
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --phase ingest

  # テーブル個別
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --phase ingest --table pages
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --phase ingest --table links
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --phase ingest --table dlinks
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --phase ingest --table domains

  # dry-run 確認
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --dry-run

  # 状態リセットして再実行
  python3 scripts/archive/phase3c_hyperdrive_ingest.py --reset

環境変数:
  CC_PARQUET_DIR   - ローカル Parquet ディレクトリ (default: /Volumes/251220/CC/2603/parquet-rs)
  S3_ACCESS_KEY    - Linode S3 access key
  S3_SECRET_KEY    - Linode S3 secret key
  GRAPH_XRPC_URL   - graph Worker XRPC URL (default: https://graph.etzhayyim.com/xrpc/com.etzhayyim.kagami.sql)
  XRPC_TIMEOUT     - SQL timeout per chunk in seconds (default: 600)
  CHUNK_SIZE       - batches per INSERT chunk (default: 100)
"""

import argparse
import json
import logging
import os
import signal
import time
from pathlib import Path

import boto3
import httpx
from botocore.config import Config

# ── Config ──

PARQUET_DIR = Path(os.environ.get("CC_PARQUET_DIR", "/Volumes/251220/CC/2603/parquet-rs"))
STATE_DIR = Path(os.environ.get("CC_DATA_DIR", "/Volumes/251220/CC/2603")) / "scripts"
STATE_FILE = STATE_DIR / ".phase3c_hyperdrive_state.json"

S3_BUCKET = "kagami-graphar"
S3_PREFIX = "cc-parquet"
S3_ENDPOINT = "https://sg-sin-1.linodeobjects.com"
S3_REGION = "sg-sin-2"
S3_ACCESS = os.environ.get("S3_ACCESS_KEY", "LJF40TXHIUSVGBRKXEFU")
S3_SECRET = os.environ.get("S3_SECRET_KEY", "Wv5b0cNdv7wNoZuiSmnJAxMwlye1MHEl1C6TowgR")

# Hyperdrive 経由の XRPC エンドポイント (graph Worker → Hyperdrive → RisingWave)
GRAPH_XRPC_URL = os.environ.get(
    "GRAPH_XRPC_URL",
    "https://graph.etzhayyim.com/xrpc/com.etzhayyim.kagami.sql",
)

# タイムアウト: CF Worker の CPU 上限は 30s だが I/O wait は別カウント
# file_scan は RisingWave の S3 読み込み → 大きいチャンクは時間がかかる
XRPC_TIMEOUT = int(os.environ.get("XRPC_TIMEOUT", "600"))

# S3 source 認証情報 (CREATE SOURCE SQL に埋め込む)
S3_CONF = (
    f"s3.region_name='{S3_REGION}', "
    f"s3.bucket_name='{S3_BUCKET}', "
    f"s3.credentials.access='{S3_ACCESS}', "
    f"s3.credentials.secret='{S3_SECRET}', "
    f"s3.endpoint_url='{S3_ENDPOINT}'"
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(STATE_DIR / "phase3c_hyperdrive.log"),
    ],
)
log = logging.getLogger(__name__)

# graceful shutdown
_shutdown = False


def _signal_handler(sig, frame):
    global _shutdown
    log.info("Shutdown requested — will stop after current chunk")
    _shutdown = True


signal.signal(signal.SIGINT, _signal_handler)
signal.signal(signal.SIGTERM, _signal_handler)

# ── State management ──

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


# ── XRPC client (Hyperdrive 経由) ──

def xrpc_sql(sql: str, timeout: int = XRPC_TIMEOUT) -> dict:
    """Execute SQL via graph Worker XRPC → Cloudflare Hyperdrive → RisingWave."""
    resp = httpx.post(
        GRAPH_XRPC_URL,
        json={"statement": sql},
        timeout=timeout,
    )
    if resp.status_code >= 400:
        body = resp.text[:400]
        raise RuntimeError(f"XRPC {resp.status_code}: {body}")
    data = resp.json()
    if "error" in data:
        raise RuntimeError(f"XRPC error: {data['error']} — {data.get('message', '')}")
    return data


# ── Step 1: S3 Upload ──

def upload_parquet(dry_run: bool = False) -> int:
    """ローカル Parquet を S3 にアップロード (既存ファイルはスキップ)。"""
    s3 = boto3.client(
        "s3",
        endpoint_url=S3_ENDPOINT,
        aws_access_key_id=S3_ACCESS,
        aws_secret_access_key=S3_SECRET,
        region_name=S3_REGION,
        config=Config(request_checksum_calculation="when_required"),
    )

    log.info(f"S3 upload: listing s3://{S3_BUCKET}/{S3_PREFIX}/ ...")
    existing = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix=f"{S3_PREFIX}/"):
        for obj in page.get("Contents", []):
            existing.add(obj["Key"].split("/")[-1])
    log.info(f"  {len(existing):,} files already on S3")

    all_files = sorted(f for f in os.listdir(PARQUET_DIR) if f.endswith(".parquet"))
    to_upload = [f for f in all_files if f not in existing]
    log.info(f"  {len(all_files):,} local files, {len(to_upload):,} to upload")

    if dry_run:
        if to_upload:
            log.info(f"  [DRY-RUN] first 3: {to_upload[:3]}")
        return len(to_upload)

    uploaded = 0
    errors = 0
    t0 = time.time()

    for fname in to_upload:
        if _shutdown:
            break
        local_path = PARQUET_DIR / fname
        s3_key = f"{S3_PREFIX}/{fname}"
        try:
            s3.upload_file(str(local_path), S3_BUCKET, s3_key)
            uploaded += 1
            if uploaded % 500 == 0:
                elapsed = time.time() - t0
                rate = uploaded / elapsed
                eta = (len(to_upload) - uploaded) / rate / 60 if rate > 0 else 0
                log.info(f"  Uploaded {uploaded:,}/{len(to_upload):,} ({rate:.0f} files/s, ETA {eta:.0f}min)")
        except Exception as e:
            errors += 1
            if errors <= 5:
                log.error(f"  Upload failed {fname}: {e}")

    log.info(f"S3 upload: {uploaded:,} new, {len(existing):,} already existed, {errors} errors")
    return uploaded


# ── Step 2: S3 Sources ──

# RisingWave S3 SOURCE 定義
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


def create_sources(dry_run: bool = False):
    """RisingWave に S3 SOURCE を作成 (via Hyperdrive XRPC)。"""
    for name, cols, pattern in SOURCES:
        drop_sql = f"DROP SOURCE IF EXISTS {name} CASCADE"
        create_sql = (
            f"CREATE SOURCE {name} ({cols})\n"
            f"INCLUDE file AS source_file\n"
            f"WITH (connector='s3', match_pattern='{pattern}', {S3_CONF})\n"
            f"FORMAT PLAIN ENCODE PARQUET"
        )

        if dry_run:
            log.info(f"  [DRY-RUN] would create source: {name} ({pattern})")
            continue

        try:
            xrpc_sql(drop_sql, timeout=30)
        except Exception as e:
            log.warning(f"  DROP {name}: {e}")

        try:
            xrpc_sql(create_sql, timeout=60)
            log.info(f"  Source {name}: created via Hyperdrive")
        except Exception as e:
            log.error(f"  Source {name}: FAILED — {e}")
            raise


# ── Step 3: Chunked INSERT ──

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
    table: str,
    source: str,
    cols: str,
    state_key: str,
    state: dict,
    chunk_size: int = 100,
    total_batches: int = 25292,
    dry_run: bool = False,
):
    """Chunked INSERT INTO {table} SELECT FROM {source} via Hyperdrive XRPC.

    各チャンク: source_file フィルタで batch_id 範囲を絞って INSERT。
    チャンク完了ごとに state を保存 → resume 可能。
    """
    done = set(state.get(state_key, []))
    chunks_total = (total_batches + chunk_size - 1) // chunk_size
    chunks_remaining = sum(
        1 for start in range(0, total_batches, chunk_size)
        if f"{start}-{min(start + chunk_size, total_batches)}" not in done
    )

    log.info(
        f"  {table}: {chunks_total} chunks total, "
        f"{len(done)} done, {chunks_remaining} remaining"
    )

    t0 = time.time()
    completed = 0
    errors = 0

    for chunk_start in range(0, total_batches, chunk_size):
        if _shutdown:
            log.info("  Shutdown requested — stopping")
            break

        chunk_end = min(chunk_start + chunk_size, total_batches)
        chunk_key = f"{chunk_start}-{chunk_end}"

        if chunk_key in done:
            continue

        # source_file フィルタ: cc-parquet/batch_000100_ のような prefix range
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
            xrpc_sql(sql, timeout=XRPC_TIMEOUT)
            elapsed = time.time() - tc
            completed += 1
            done.add(chunk_key)
            state[state_key] = list(done)
            save_state(state)

            total_elapsed = time.time() - t0
            rate = completed / total_elapsed if total_elapsed > 0 else 0
            eta = (chunks_remaining - completed) / rate / 60 if rate > 0 else 0

            log.info(
                f"  {table} [{chunk_start:06d}-{chunk_end:06d}]: {elapsed:.0f}s "
                f"({completed}/{chunks_remaining}, ETA {eta:.0f}min)"
            )

        except Exception as e:
            errors += 1
            log.error(f"  {table} [{chunk_start:06d}-{chunk_end:06d}]: {str(e)[:200]}")
            if errors >= 5:
                log.error("  5 consecutive errors — stopping this table")
                break
            log.info("  Sleeping 20s before retry...")
            time.sleep(20)
            errors = 0  # reset after sleep

    elapsed = time.time() - t0
    log.info(f"  {table}: {completed} chunks inserted in {elapsed:.0f}s")


# ── Step 4: vertex_domain ──

def populate_domains(dry_run: bool = False):
    """vertex_domain を vertex_page.domain の DISTINCT から派生 (via Hyperdrive)。"""
    # まず既存の CC ドメインをクリア
    delete_sql = "DELETE FROM vertex_domain WHERE source_file IS NULL OR 1=1"
    # より安全: 既存の CC domain を消して再作成
    delete_sql = "DELETE FROM vertex_domain WHERE 1=1"

    insert_sql = """INSERT INTO vertex_domain (
        vertex_id, domain, did, handle, display_name,
        topics, performer_type, status,
        _seq, sensitivity_ord, created_date, owner_did
    )
    SELECT
        p.domain,
        p.domain,
        'did:web:site.etzhayyim.com:' || REPLACE(p.domain, '.', '-'),
        'site.etzhayyim.com:' || REPLACE(p.domain, '.', '-'),
        p.domain,
        NULL::VARCHAR,
        'service',
        'active',
        0::BIGINT,
        0::BIGINT,
        NULL::DATE,
        NULL::VARCHAR
    FROM (
        SELECT DISTINCT domain
        FROM vertex_page
        WHERE domain IS NOT NULL AND domain != ''
    ) p"""

    if dry_run:
        log.info("  [DRY-RUN] would populate vertex_domain from vertex_page.domain")
        return

    try:
        xrpc_sql(delete_sql, timeout=60)
        log.info("  vertex_domain: cleared")
    except Exception as e:
        log.warning(f"  vertex_domain DELETE: {e}")

    try:
        xrpc_sql(insert_sql, timeout=300)
        log.info("  vertex_domain: populated via Hyperdrive")
    except Exception as e:
        log.error(f"  vertex_domain INSERT: {e}")


# ── Step 5: Verify ──

def verify():
    """テーブルカウントと top domains を確認。"""
    tables = ["vertex_page", "edge_links_to", "edge_links_to_domain", "vertex_domain"]
    for t in tables:
        try:
            result = xrpc_sql(f"SELECT COUNT(*) AS cnt FROM {t}", timeout=30)
            count = result.get("rows", [{}])[0].get("cnt", "?")
            log.info(f"  {t}: {int(count):,}" if str(count).isdigit() else f"  {t}: {count}")
        except Exception as e:
            log.warning(f"  {t}: {e}")

    try:
        result = xrpc_sql(
            "SELECT domain, page_count FROM mv_cc_domain_page_count "
            "ORDER BY page_count DESC LIMIT 5",
            timeout=30,
        )
        log.info("  Top domains:")
        for row in result.get("rows", []):
            log.info(f"    {row.get('domain')}: {row.get('page_count'):,}")
    except Exception as e:
        log.warning(f"  mv_cc_domain_page_count: {e}")


# ── Main ──

def main():
    p = argparse.ArgumentParser(
        description="Phase 3c: CC Parquet → RisingWave via Hyperdrive (graph Worker XRPC)"
    )
    p.add_argument(
        "--phase",
        choices=["upload", "ingest", "all"],
        default="all",
        help="upload=S3のみ, ingest=DB取り込みのみ, all=両方",
    )
    p.add_argument(
        "--table",
        choices=["pages", "links", "dlinks", "domains", "all"],
        default="all",
        help="取り込むテーブル (ingest フェーズのみ)",
    )
    p.add_argument(
        "--chunk-size",
        type=int,
        default=int(os.environ.get("CHUNK_SIZE", "100")),
        help="1チャンクあたりのバッチ数 (default: 100)",
    )
    p.add_argument(
        "--total-batches",
        type=int,
        default=25292,
        help="バッチ総数 (default: 25292 = ls parquet-rs | wc -l / 3)",
    )
    p.add_argument("--dry-run", action="store_true", help="実行せずに確認のみ")
    p.add_argument("--reset", action="store_true", help="state をリセットして再実行")
    p.add_argument("--recreate-sources", action="store_true", help="SOURCE を再作成する")
    args = p.parse_args()

    STATE_DIR.mkdir(parents=True, exist_ok=True)

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        log.info("State reset")

    state = load_state()

    log.info("=" * 60)
    log.info("Phase 3c: CC Parquet → RisingWave via Hyperdrive")
    log.info(f"  XRPC URL: {GRAPH_XRPC_URL}")
    log.info(f"  S3 bucket: s3://{S3_BUCKET}/{S3_PREFIX}/")
    log.info(f"  Parquet dir: {PARQUET_DIR}")
    log.info(f"  Chunk size: {args.chunk_size} batches")
    log.info(f"  Total batches: {args.total_batches}")
    log.info("=" * 60)

    t0 = time.time()

    # Step 1: S3 Upload
    if args.phase in ("upload", "all"):
        log.info("=== Step 1: S3 Upload ===")
        upload_parquet(dry_run=args.dry_run)

    if args.phase in ("ingest", "all"):
        # Step 2: Create S3 Sources
        if not state.get("sources_created") or args.recreate_sources:
            log.info("=== Step 2: Create S3 Sources (via Hyperdrive) ===")
            create_sources(dry_run=args.dry_run)
            if not args.dry_run:
                state["sources_created"] = True
                save_state(state)
                log.info("  Waiting 5s for source file discovery...")
                time.sleep(5)
        else:
            log.info("=== Step 2: S3 Sources (already created, skipping) ===")
            log.info("  Use --recreate-sources to force recreation")

        ingest_opts = dict(
            chunk_size=args.chunk_size,
            total_batches=args.total_batches,
            dry_run=args.dry_run,
        )

        # Step 3a: vertex_page
        if args.table in ("pages", "all"):
            log.info("=== Step 3a: INSERT vertex_page ===")
            chunked_insert(
                "vertex_page", "cc_pages_s3", PAGE_COLS,
                "pages_chunks_done", state, **ingest_opts,
            )

        # Step 3b: edge_links_to
        if args.table in ("links", "all") and not _shutdown:
            log.info("=== Step 3b: INSERT edge_links_to ===")
            chunked_insert(
                "edge_links_to", "cc_links_s3", LINK_COLS,
                "links_chunks_done", state, **ingest_opts,
            )

        # Step 3c: edge_links_to_domain
        if args.table in ("dlinks", "all") and not _shutdown:
            log.info("=== Step 3c: INSERT edge_links_to_domain ===")
            chunked_insert(
                "edge_links_to_domain", "cc_dlinks_s3", DLINK_COLS,
                "dlinks_chunks_done", state, **ingest_opts,
            )

        # Step 4: vertex_domain
        if args.table in ("domains", "all") and not _shutdown:
            if not state.get("domains_done"):
                log.info("=== Step 4: Populate vertex_domain ===")
                populate_domains(dry_run=args.dry_run)
                if not args.dry_run:
                    state["domains_done"] = True
                    save_state(state)
            else:
                log.info("=== Step 4: vertex_domain (already done, skipping) ===")

        # Step 5: Verify
        if not _shutdown:
            log.info("=== Step 5: Verify ===")
            verify()

    log.info(f"Phase 3c complete in {time.time()-t0:.0f}s")


if __name__ == "__main__":
    main()
