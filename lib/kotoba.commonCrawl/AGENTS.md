# etzhayyim-project-common-crawl — Common Crawl Intelligence Pipeline

**Shannon-optimal pipeline: WAT (gz) → Rust cc-phase3 (rayon) → Parquet (ZSTD) → S3 (cc-parquet-v2/) → RisingWave s3 connector → ALTER TABLE SWAP。**

## Per-page DID Actor (2026-04-14, CRITICAL)

Every page row carries its own DID actor derived from the URL directory
path. `domain` and `page` are both W3C did:web actors now.

| Layer | Actor | DID | rkey |
|---|---|---|---|
| Domain | domain | `did:web:site.etzhayyim.com:{domain-slug}` | `{domain}` |
| Page | page | `did:web:site.etzhayyim.com:{domain-slug}:{path-seg}:…` | `{domain-slug}:{path-seg}:…` |

URL → DID is path-isomorphic (`/` ↔ `:`), root `/` uses the sentinel
`:_root`. Query/fragment stripped. Long URLs (>2048 char total) fall
back to `:_h:{16hex}` SHA-256 slug.

**Legacy coexistence.** The original rkey format was SHA-16 hex + null
`owner_did`. Both legacy and new-format rows live together in
`vertex_page` and are unified by `view_cc_page_canonical` (per-URL
GROUP BY, MAX picks new if present else legacy). The alias mapping is
recorded in `vertex_did_alias` (migration `0026_cc_page_did_alias`).
No DELETE needed — full AT Protocol `alsoKnownAs` style aliasing.

**SSoT invariant**: `page_did_from_url()` in
`rust/cc-phase3/src/main.rs` and the Python mirror in
`scripts/phase3h_transform_parquet.py` must produce identical output.
Change one, change both (and add a test).

## Architecture

```
WAT files (49,591 × ~1GB gz)
  → rust/cc-phase3 --format parquet --workers 8
    → batch_{id}_pages.parquet   (vertex_page)
    → batch_{id}_links.parquet   (edge_links_to)
    → batch_{id}_dlinks.parquet  (edge_links_to_domain)
  → S3 upload (kagami-graphar bucket, cc-parquet/ prefix)
  → RisingWave: INSERT INTO vertex_page SELECT * FROM file_scan('parquet', 's3', ...)
  → vertex_domain: MV derived from vertex_page.domain (no explicit INSERT)

etzhayyim common-crawler (Go CLI)
  ├─ download  → Python download_all.py (WAT/WET/WARC, resumable)
  ├─ parquet   → Rust cc-phase3 --format parquet (primary pipeline)
  ├─ intel     → Python phase4_intel_extract.py (Murakumo LLM)
  ├─ inject    → Python phase5_inject.py (PDS DID records)
  └─ monitor   → status dashboard
```

## Pipeline Phases

| Phase | Input | Output | Tool | Status |
|---|---|---|---|---|
| **download** | CC-MAIN-YYYY-WW | WAT full (49,591 files) | Python + httpx + warcio | done |
| **parquet (from WAT)** | WAT files | Parquet (vertex_page, edge_links_to, edge_links_to_domain) | `rust/cc-phase3` (rayon, ZSTD) | done |
| **transform (parquet-to-parquet)** | Legacy parquet (SHA-hex rkey) | pages parquet with URL-slug rkey + page DID | `scripts/phase3h_transform_parquet.py` | done (pages only) |
| **s3-upload** | Local parquet (pages=new, links/dlinks=old) | S3 `kagami-graphar/cc-parquet-v2/` | `scripts/phase3j_s3_upload_v2.py` | **done** (148,773 files) |
| **s3-connector-swap** | S3 cc-parquet-v2/ | RisingWave tables via s3 connector + SWAP | `scripts/phase3k_s3_connector_swap.sql` | **done (2026-04-16)** — vertex_page=985M, edge_links_to=4.6B, edge_links_to_domain=2.3B |
| **alias-backfill** | vertex_page (both formats) | `vertex_did_alias` rows | `scripts/phase3i_alias_backfill.py` | **pending** |
| **intel** | domain JSONL | domain_intel.jsonl.gz | Murakumo fleet (qwen3.5-9b) | pending |
| **inject** | domain_intel | PDS DID records | PDS XRPC | pending |

### links/dlinks src_vid constraint (2026-04-15)

`edge_links_to.src_vid` / `dst_vid` stay SHA-hex (old format) because transforming them
requires a global 985M-row rkey↔URL lookup — infeasible without re-running cc-phase3 on
all WAT files (~4 days). Resolution at query time via `view_cc_edge_links_to_canonical`
JOIN `vertex_did_alias` (designed in migration 0026).

### S3-connector ingest vs COPY FROM STDIN (2026-04-15)

| | COPY FROM STDIN (phase3g) | S3 connector (phase3k) |
|---|---|---|
| Rate | ~3,000 r/s | ~9,300 r/s peak (benchmark: 1 file) |
| TCP disconnect | stops at 20 errors | not applicable |
| Dedup | state file | CREATE TABLE is fresh (no overlap) |
| Swap | n/a | ALTER TABLE SWAP (atomic, no downtime) |
| ETA pages | ~90h remaining | ~15h (2 CN estimate) |

### Pruned: SQL + JSONL output (2026-04-14)

`rust/cc-phase3` dropped the `--format sql` / `--format jsonl` code paths
and the `generate_sql_batch` / `generate_jsonl_batch` helpers. Parquet
is the single Shannon-optimal output. Legacy SQL batches still exist
on disk for `phase5b_inject_pages.py` backfill but new WAT runs only emit
parquet.

### Archived: SQL Pipeline (deprecated 2026-04-11)

SQL intermediate format (`scripts/archive/phase3_wat_to_cypher.py` → `scripts/archive/phase3b_ingest_risingwave.py`) は廃止。
理由: Shannon 冗長 (WAT → SQL → parse → INSERT = 3 変換)、PG wire INSERT の RTT ボトルネック。
WAT → Parquet 直接で変換 1 回 + S3 native bulk load。

## Knowledge Graph Schema

```sql
(:WebDomain {did, name, slug, entityType, industry, operator, jurisdiction, description, pageCount})
  -[:OPERATED_BY]->(:Operator {name, jurisdiction})
  -[:PROVIDES]->(:Service {name})
  -[:HOSTS_DATA]->(:DataType {name})
  -[:COVERS]->(:WorldDomain {name})
  -[:HOSTS]->(:WebPage {did, url, urlHash, title, language, contentType, outlinkCount})
    -[:LINKS_TO]->(:WebPage)

(:WorldDomain {name})
  -[:BELONGS_TO]->(:MajorCategory {name, description})

(:CrawlBatch {crawlId, startDate, source})
```

## CLI Examples

```bash
# Download CC-MAIN-2026-12 WAT (all)
etzhayyim common-crawler download --crawl CC-MAIN-2026-12 --format wat --workers 8

# Download filtered by government domains
etzhayyim common-crawler download --domains gov-domains.txt --format wat,wet

# Download specific shard range (for parallel machines)
etzhayyim common-crawler download --range-start 0 --range-end 25000 --workers 4

# Generate DID property graph from downloaded WAT
etzhayyim common-crawler graph --source full --output sql

# Graph for Japanese government domains only
etzhayyim common-crawler graph --domain "*.go.jp" --output jsonl

# Intelligence extraction (top 5000 domains by page count)
etzhayyim common-crawler intel --limit 5000 --min-pages 100

# Intel for specific domain pattern
etzhayyim common-crawler intel --domain "*.gov" --model qwen3.5-9b

# Inject to PDS (dry-run first)
etzhayyim common-crawler inject --dry-run
etzhayyim common-crawler inject --source intel --batch-size 500

# Status
etzhayyim common-crawler monitor

# List available crawls
etzhayyim common-crawler list-crawls --year 2026
```

## Scripts (monorepo, `60-apps/etzhayyim-project-common-crawl/scripts/`)

| Script | Phase | 機能 |
|---|---|---|
| `archive/phase3_wat_to_cypher.py` | graph | ARCHIVED: WAT → SQL DID property graph。resume checkpoint + 14 topic auto-classification + domain prefilter via Common Crawl Index (CDX) |

`etzhayyim common-crawler graph` は monorepo `60-apps/etzhayyim-project-common-crawl/scripts/` を優先する。旧 SQL 実装は `scripts/archive/` 配下に退避済み。

### Graph Query Optimization (domain 指定時)

`etzhayyim common-crawler graph --domain ...` は以下の順で処理する:

1. Common Crawl Index (CDX) で対象ドメインの `filename` を問い合わせ
2. ローカルの `*.warc.wat.gz` 候補へ変換し、WAT ファイル集合を事前に絞り込み
3. WAT レコード処理時にも `--domain` フィルタを適用（最終ガード）

CDX 側が一時失敗しても全停止しないよう、以下を実装済み:
- retry + exponential backoff + jitter
- ローカルキャッシュ（TTL）
- キャッシュファイルの原子的更新

環境変数:
- `CC_DOMAIN_FILTER`: domain csv filter (`*.go.jp,nlftp.mlit.go.jp`)
- `CC_CDX_CACHE_TTL_SEC`: CDX キャッシュ TTL 秒（default: 604800 = 7 days）
- `CC_CDX_RETRIES`: CDX retry 回数（default: 4）
- `CC_CDX_BACKOFF_BASE_SEC`: backoff 基本秒（default: 1.5）

## Data Directory

```
$CC_DATA_DIR (default: /Volumes/251220/CC/2603)
├── scripts/
│   ├── domains.txt                    — authority domain filter (103 domains)
│   ├── world_domains.json             — 405 world domains from coverage
│   ├── world_domain_taxonomy.json     — 10 major categories × sub-domains
│   ├── domain_mapping_v3.json         — domain → world domain mapping
│   ├── download_all.py                — Phase 1+2 download
│   ├── archive/phase3_wat_to_cypher.py — Archived Phase 3 graph
│   ├── phase4_intel_extract.py        — Phase 4 intel
│   ├── .phase3_state.json             — Phase 3 resume checkpoint
│   ├── .phase3_cdx_cache.json         — CDX prefilter cache (TTL)
│   └── .*.json                        — state files (resume)
├── wat-full/                          — all WAT files (~14.8TB)
├── filtered/{wet,wat}/                — authority domains only
└── graph/
    ├── batch_*.sql                 — DID property graph SQL (10K pages/file)
    ├── domains_for_classification.jsonl.gz — domain JSONL for Phase 4
    ├── link_graph_stats.json          — domain stats + topic distribution
    ├── domain_intel.jsonl.gz          — extracted intelligence
    └── knowledge_graph.sql         — knowledge graph SQL
```

## RisingWave Ingestion (Phase 3g — CURRENT, path-j-cc-hummock)

**Phase 3g = local parquet → RisingWave plain (hummock) tables via psycopg2 execute_values.** Active since 2026-04-13. Supersedes 3b (SQL) and 3c (Hyperdrive) after iceberg sink stall.

### Why phase3g replaced phase3c (Hyperdrive + ENGINE=iceberg)

| Issue (phase3c) | Resolution (phase3g + path-j) |
|---|---|
| Hyperdrive connection timeout on long INSERT SELECT FROM s3_source | Direct psycopg2 to `172.236.132.11:4566` + TCP keepalive |
| CREATE SOURCE wildcard enumerates all 28k S3 files → 2-10 min | Read parquet locally, batch INSERT via execute_values |
| ENGINE=iceberg sink stalled 537k rows in `__internal___iceberg_sink_*` | Dropped iceberg engine. Plain Hummock tables (path-j-cc-hummock) |
| `iceberg_intermediate_scan_rule` returns empty plan when no iceberg file | Plain tables → no iceberg rule → immediate read visibility |
| compute OOM with 200+ MV actors on 5Gi memory | Foyer disk cache (10 GiB data + 2 GiB meta on local SSD) + node separation |

Schema: `50-infra/linode/risingwave-iceberg/sql/01-tables-j-hummock.sql` (CC tables only, plain tables + 4 streaming MVs).

### phase3g scripts

- `scripts/phase3g_copy_ingest.py` — parquet → plain tables via psycopg2 execute_values (ThreadPoolExecutor, resume state)
- State: `$CC_DATA_DIR/scripts/.phase3g_copy_state.json` (per-table `done` file list)
- Log: `$CC_DATA_DIR/scripts/phase3g_copy.log`
- Rate (observed): ~2000 r/s single table, ~3500 r/s with 3 parallel tables (pages+links+dlinks)

### Usage

```bash
# Apply schema (destructive: drops iceberg versions of CC tables)
cd 50-infra/linode/risingwave-iceberg
PATH_MODE=path-j-hummock ./deploy.sh

# Ingest (3 parallel processes, 4 workers each — best throughput)
cd 60-apps/etzhayyim-project-common-crawl/scripts
python3 phase3g_copy_ingest.py --table pages  --workers 4 &
python3 phase3g_copy_ingest.py --table links  --workers 4 &
python3 phase3g_copy_ingest.py --table dlinks --workers 4 &

# Or all in one process, serial
python3 phase3g_copy_ingest.py --table all --workers 4

# Resume after interruption (state auto-saved every 100 files)
python3 phase3g_copy_ingest.py --table pages --workers 4

# Reset state and re-ingest
python3 phase3g_copy_ingest.py --table pages --workers 4 --reset
```

### Environment

- `RW_HOST=172.236.132.11` (direct, no port-forward needed)
- `RW_PORT=4566`
- `CC_PARQUET_DIR=/Volumes/251220/CC/2603/parquet-rs` (local SSD)

### Key lessons (2026-04-13)

1. **RisingWave ENGINE=iceberg is fragile on constrained clusters.** The iceberg sink accumulates writes in an internal log store until the iceberg commit succeeds. Under S3 SlowDown + compute memory pressure, commits stall and `iceberg_intermediate_scan_rule` hides the data. Plain Hummock tables bypass all of this.
2. **Foyer disk cache is essential** on small clusters (5-6 Gi compute). Shifts hummock hot data from RAM to local SSD. Configured via `computeComponent.configuration.[storage.data_file_cache]` in helm values.
3. **Node separation via labels** (rw-role=compute vs rw-role=control) gives compute exclusive use of its node's 8 Gi memory.
4. **FLUSH after INSERT** is required for read visibility on iceberg tables but not for plain tables (where INSERT + FLUSH is still good for durability).
5. **`COPY FROM STDIN` is not yet implemented** in RisingWave v2.8. Use `psycopg2.extras.execute_values` for bulk INSERT.
6. **`file_scan()` does not support custom S3 endpoints** (no Linode endpoint parameter). Must use `CREATE SOURCE ... WITH (connector='s3', s3.endpoint_url=...)`.

## Archived Ingest Paths (not active as of 2026-04-13)

Only `phase3g` on `path-j-cc-hummock` is active. Other ingest paths are retained for reference and should be treated as archived:

- `scripts/archive/phase3c_hyperdrive_ingest.py` — archived. Hyperdrive XRPC path timed out on long-running ingest.
- `scripts/archive/phase3d_filescan_ingest.py` — archived. Per-file `file_scan()` via Hyperdrive remained slower and operationally fragile.
- `scripts/archive/phase3e_direct_ingest.py` — archived. Direct psycopg2 + `kubectl port-forward` is superseded by direct host access on path-j.
- `scripts/archive/phase3f_staging_ingest.py` — archived. Streaming staging tables added complexity and did not beat the active path.

## Legacy: Phase 3b (psycopg2 iceberg, 2026-03)

Phase 3 output → RisingWave PG :4566 via psycopg2 (PostgreSQL wire protocol)。
Tables are models.py SSoT (DDL generated by `generate_rw_full.py`, Internal Iceberg `ENGINE = iceberg`)。

| Table | Source | Row count |
|---|---|---|
| `vertex_domain` | domains JSONL (Phase 3) | ~873 |
| `vertex_actor` | domains JSONL (shared table) | ~873 |
| `vertex_page` | S3 connector (cc-parquet-v2, phase3k) | **985,469,916** (LIVE 2026-04-16) |
| `edge_hosts_page` | SQL batch files (legacy) | ~8.4M+ |
| `edge_links_to` | S3 connector (cc-parquet-v2, phase3k) | **4,603,156,096** (LIVE 2026-04-16) |
| `edge_links_to_domain` | S3 connector (cc-parquet-v2, phase3k) | **2,328,938,130** (LIVE 2026-04-16) |

**Streaming MVs** (auto-refresh on INSERT, defined in `generate_rw_full.py`):
- `mv_cc_domain_page_count` — real-time page count per domain (from edge_hosts_page)
- `mv_cc_domain_out_degree` — outgoing domain link count + total links (from edge_links_to_domain)
- `mv_cc_domain_in_degree` — incoming domain link count + total links (from edge_links_to_domain)
- `mv_cc_domain_coverage` — domain × actor join

No Iceberg sinks needed — tables are natively Internal Iceberg (data stored directly in S3 Parquet).

**Scripts**:
- `scripts/archive/phase3b_ingest_risingwave.py` — PG INSERT (psycopg2, parallel workers, resume checkpoint)
- `scripts/phase5_inject_did.py` — PDS DID + Profile registration (`x-kotodama-verified` internal auth)

**Usage**:
```bash
# Port-forward RisingWave (if not direct access)
kubectl -n risingwave port-forward svc/risingwave 4566:4566

# 1) Domain + Actor + Pages (all phases)
python3 scripts/archive/phase3b_ingest_risingwave.py --phase all --workers 4

# 2) Domains only
python3 scripts/archive/phase3b_ingest_risingwave.py --phase domains

# 3) Actors only (CC domain actors into shared vertex_actor)
python3 scripts/archive/phase3b_ingest_risingwave.py --phase actors

# 4) Pages + edges only (parallel workers)
python3 scripts/archive/phase3b_ingest_risingwave.py --phase pages --workers 8

# 5) Dry-run
python3 scripts/archive/phase3b_ingest_risingwave.py --phase all --dry-run

# 6) Resume after interruption (state auto-saved)
python3 scripts/archive/phase3b_ingest_risingwave.py --phase pages

# 7) Reset state and re-ingest
python3 scripts/archive/phase3b_ingest_risingwave.py --phase all --reset
```

Environment variables:
- `RW_HOST` — RisingWave host (default: `localhost`, use port-forward)
- `RW_PORT` — PG port (default: `4566`)
- `RW_USER` — PG user (default: `root`)
- `RW_DB` — database (default: `dev`)
- `CC_DATA_DIR` — CC data directory (default: `/Volumes/251220/CC/2603`)
- `CC_CRAWL_ID` — crawl batch ID (default: `CC-MAIN-2026-12`)

State file: `$CC_DATA_DIR/scripts/.phase3b_rw_state.json`

Recommended phase order:
1. `domains` — vertex_domain (fast, ~873 rows)
2. `actors` — vertex_actor CC actors (fast, ~873 rows)
3. `pages` — vertex_page + edge_* (slow, ~22M+ rows, parallel workers)

**Coverage CLI**: `etzhayyim actors common-crawler-coverage` — RisingWave の CC DID coverage を graph Worker 経由で分析。

### Legacy Ingestion (REMOVED)

Legacy ingestion helpers from the removed RisingWave pipeline have been deleted.

## Relationship to site.etzhayyim.com

Common Crawl pipeline feeds into site.etzhayyim.com (internet clone gateway):
- **WebDomain** DIDs are created in `did:web:site.etzhayyim.com:{domain-slug}` namespace
- **WebPage** DIDs follow `did:web:site.etzhayyim.com:{domain-slug}:{page-slug}`
- Intelligence extraction results are written as `com.etzhayyim.apps.site.domain` records
- Link graph enables site.etzhayyim.com's coverage tracking for 403 world domains
- **Profile**: `vertex_actor` に 872 domain profiles 登録済み (PDS getProfile で取得可能)
