# etzhayyim-project-site — Site Intelligence Platform (Internet Clone Gateway)

**唯一の外部 web fetch gateway。** 全 App の外部 web fetch/crawl は site.etzhayyim.com 経由必須 (直接 HTTP fetch 禁止)。100B-scale hierarchical DID page archive with topic coordinator routing for selective Follow. WET (Markdown) + WAT (JSON metadata) + WebP (screenshot) output pipeline for LLM embedding.

## CRITICAL: Internet Clone Gateway Role

→ `etzhayyim dodaf tv1 query --id etzhayyim-project-site-internet-clone-gateway-role` / MCP `etzhayyim.dodaf.tv1.query`

## CRITICAL: did:etzhayyim Migration (ADR-0029)

**新規 page DID は `did:etzhayyim:{cidv1}:{cidv1}:{cidv1}` (W3C DID Core + CIDv1) を canonical とする。** 既存の `did:web:site.etzhayyim.com:{domain-slug}:{page-slug}` は legacy として grandfathered。`alsoKnownAs` で双方向 alias 維持、`edge_etzhayyim_federation` で AT Proto 連携継続。

| 旧 (legacy) | 新 (canonical) |
|---|---|
| `did:web:site.etzhayyim.com` | `did:etzhayyim:bafkrei...site` (root genesis) |
| `did:web:site.etzhayyim.com:topic:semiconductor` | `did:etzhayyim:bafkrei...site:bafkrei...topic-sem` |
| `did:web:site.etzhayyim.com:example-com` | `did:etzhayyim:bafkrei...site:bafkrei...example-com` |
| `did:web:site.etzhayyim.com:example-com:docs-api-v2` | `did:etzhayyim:bafkrei...site:bafkrei...example-com:bafkrei...docs-api-v2` |

- Spec: `90-docs/adr/0029-did-etzhayyim-method-specification.md`
- Lib: `orgs/etzhayyim/com-etzhayyim-did-etzhayyim/` (CIDv1 + DAG-CBOR genesis op + W3C DID Doc)
- Resolver: `did.etzhayyim.com` (`orgs/etzhayyim/com-etzhayyim-did-etzhayyim/resolver/`)
- Migration XRPC: `com.etzhayyim.identity.submitOp` (PDS handler)
- 既存 15,283 wikipedia path は **topological-sort で root → leaf 順** に CIDv1 化 (`etzhayyim identity migrate-paths --root did:web:site.etzhayyim.com`、scaffold 予定)

CONTROLS chain は path syntax で自動的に表現される (parent = `did.split(':').slice(0,-1).join(':')`)。新規追加に `:CONTROLS` edge の手動 INSERT は不要 (ADR-0029 §Path-Form DID Resolution)。

## Architecture: 3-Level DID Hierarchy + Topic Routing

```
site.etzhayyim.com (single APP, 1 Worker)
  → 1 primary DID (coordinator, Follow 禁止 at 100B scale)
    → N Topic coordinator DIDs (follower routing layer)
      → did:web:site.etzhayyim.com:topic:{topic-slug}
    → N Domain DIDs (per crawled domain)
      → did:web:site.etzhayyim.com:{domain-slug}
        → N Page DIDs (per crawled page, each page = DID)
          → did:web:site.etzhayyim.com:{domain-slug}:{page-slug}
```

### DID Path Hierarchy

| Level | DID Representation | 例 | Follow 対象 |
|---|---|---|---|
| **APP** | primary DID | `did:web:site.etzhayyim.com` | ❌ (100B fan-out) |
| **Topic** | topic coordinator DID | `did:web:site.etzhayyim.com:topic:semiconductor` | ✅ followers subscribe here |
| **Domain** | domain DID | `did:web:site.etzhayyim.com:example-com` | ✅ domain-level followers |
| **Page** | page DID (under domain) | `did:web:site.etzhayyim.com:example-com:docs-api-v2` | ✅ page-level tracking |

### CONTROLS Chain

```sql
(:DID {id:"did:web:site.etzhayyim.com"})
  -[:CONTROLS]->(:DID {id:"did:web:site.etzhayyim.com:topic:semiconductor"})
  -[:CONTROLS]->(:DID {id:"did:web:site.etzhayyim.com:example-com"})
    -[:CONTROLS]->(:DID {id:"did:web:site.etzhayyim.com:example-com:docs-api-v2"})
```

## Design E 3-Tier Write + 3-Layer Reactive Pipeline

### 3-Layer Architecture

| Layer | Role | Implementation |
|---|---|---|
| **1. Input** | ComAtprotoSyncSubscribeRepos — inbound mentions/URLs from followers | reactive URL extraction → crawl queue |
| **2. Output** | HandleStream — wRPC stream to subscribers + AppBskyFeedPost per topic/domain DID | topic-filtered fan-out |
| **3. Evolution** | joucho 情緒 cadence heartbeat (`resolveHeartbeatCadence`) | mood-driven Follow graph maintenance |

### Write Tiers

| Tier | API | Record | 用途 |
|---|---|---|---|
| **Tier 1 Social** | `AppBskyFeedPost(topicDID, ...)` | `app.bsky.feed.post` | topic/domain DID から social post → followers に ComAtprotoSyncSubscribeRepos |
| **Tier 2 Domain** | `DIDWrite(pageDID, ...)` / `ComAtprotoRepoCreateRecord(...)` | `com.etzhayyim.apps.site.*` | page metadata, topic metadata, follower events |
| **Tier 3 State** | `Preferences()` | — | evolution config |

### Follower Routing (100B Scale)

```
Follower (e.g., handotai.etzhayyim.com):
  1. Heartbeat: G("WebTopic").Match(Eq{"topic":"semiconductor"}) → discover topic DID
  2. Follow(topic DID) → subscribe to semiconductor pages only
  3. ComAtprotoSyncSubscribeRepos: receive AppBskyFeedPost from topic DID → analyze → own domain records
```

Shannon efficiency: R ≈ 0 (topic granularity routing, no 100B fan-out)

## Frontier: Persistent Crawl Queue

Heartbeat-driven crawl frontier stored as Tier 2 domain records in yata graph.

### Lifecycle

```
enqueue-url / enqueue-bulk / ComAtprotoSyncSubscribeRepos (cross-actor URL mention) / link-discovery
  → FrontierEntry {status: "pending", priority: 0-100}
    → handleHeartbeat() dequeues batch (5/heartbeat)
      → cmdCrawlPage() → HTTP fetch + parse + DID create
        → status: "done" | "failed"
        → discovered links → re-enqueue at depth+1, priority+10
```

### Priority Scoring

| Source | Priority | Rationale |
|---|---|---|
| Manual (`enqueue-url`) | 50 (default) | User-specified |
| cross-actor request (ComAtprotoSyncSubscribeRepos) | 20 | Higher: external agent requested |
| Link discovery (child links) | parent + 10 | Lower: auto-discovered, exponential decay |
| Bulk import | 50 (default) | Same as manual |

### Politeness

- Max depth = 3 (link discovery stops after 3 hops)
- Batch size = 20 URLs per heartbeat (60s interval = ~28,800 pages/day)
- robots.txt: cached as `com.etzhayyim.apps.site.robots_txt` record (24h TTL), `User-agent: etzhayyim-bot` + `*`
- Per-domain cooldown via crawl_delay from robots.txt (default 1s)
- Failed entries are marked, not retried immediately

### SQL Node

```sql
(:FrontierEntry {url, domain, status, priority, depth, topics, source, enqueued_at, started_at, finished_at, error})
```

## Public Domain Bulk Ingest

3 bulk catalog ingest commands for copyright-expired full-text books:

| Command | Source | Estimated Scale | Format |
|---|---|---|---|
| `bulk_ingest_aozora` | Aozora Bunko (青空文庫) | ~17,000 works | GitHub CSV index → HTML text |
| `bulk_ingest_gutenberg` | Project Gutenberg | ~70,000 works | Gutendex JSON API → UTF-8 text |
| `bulk_ingest_ndl` | NDL Digital Collection (国会図書館) | ~500,000 PD works | SRU/IIIF API → OCR text |

All use Collection Job pattern. Results flow to isbn.etzhayyim.com via ComAtprotoSyncSubscribeRepos (isbn Follows webpage).

## WET/WAT/WebP Output Pipeline (LLM Embedding Optimized)

General web crawl produces 3 output formats (WARC-alternative):

| Format | Record | Content | LLM Use |
|---|---|---|---|
| **WET** | `com.etzhayyim.apps.site.wet` | Markdown text chunks (512 tokens, sentence boundary) | Text embedding (Murakumo) |
| **WAT** | `com.etzhayyim.apps.site.wat` | JSON metadata (URL, headers, outlinks, OG, language) | Link graph, analytics |
| **WebP** | `com.etzhayyim.apps.site.screenshot` | WebP screenshot blob (1280x720, quality 80) | ColPali visual embedding |

### Pipeline Flow

```
collection_job completed (HTML)
  ├─ htmlToMarkdown() → splitIntoParagraphs(256-512 tokens) → N x site_wet records
  ├─ extractHtmlMeta() + extractOutlinks() → 1 x site_wat record → link discovery → frontier
  ├─ captureScreenshotJob() → browser_screenshot collection_job → site_screenshot record (R2 blob)
  └─ classifyTopics() → postAs(topicDID) social announcement
```

### Topic Coordinators (14 total)

| Slug | Category | Sources |
|---|---|---|
| jp_classics | Japanese Classical Texts | aozora, ndl, wikisource_ja |
| intl_literature | International Literature | gutenberg, wikisource_en |
| academic | Academic & Reference | wikisource, ndl |
| images | Historical Images | colbase, codh, ndl_iiif |
| technology | Technology | general web |
| science | Science & Research | general web |
| business | Business & Finance | general web |
| government | Government | general web (.gov) |
| education | Education | general web (.edu) |
| news_media | News & Media | general web |
| health | Health & Medicine | general web |
| legal | Legal & Regulatory | general web |
| culture | Culture & Arts | general web |
| commerce | E-Commerce | general web |

### Common Crawl Bulk Pipeline (CC-MAIN-2026-12)

site.etzhayyim.com は Common Crawl の月次クロールデータを大規模取り込みし、etzhayyim coverage world (403 world domains) の link graph 構築 + DID 分類に活用する。

#### Data Scale

| Format | Files | Size (compressed) | Retention |
|---|---|---|---|
| **WAT (full)** | 100,000 | ~14.8 TB | `/Volumes/251220/CC/2603/wat-full/` — 全 web link graph |
| **WAT (filtered)** | — | ~数百 GB | `filtered/wat/` — 103 authority domains のみ |
| **WET (filtered)** | — | ~数百 GB | `filtered/wet/` — 103 authority domains のみ |

#### Pipeline (4 phases)

```
Phase 1+2: download_all.py
  WAT 全量ダウンロード (14.8TB) + WET/WAT authority domain フィルタ
  → /Volumes/251220/CC/2603/

Phase 3: phase3_wat_to_cypher.py (60-apps/etzhayyim-project-common-crawl/70-tools/70-tools/70-tools/scripts/)
  WAT parse → CcDomain / CcPage / LINKS_TO / HOSTS SQL graph + topic auto-classification
  Resume checkpoint (.phase3_state.json), 14 topic heuristics (TLD + keyword)
  → graph/batch_*.sql + domains_for_classification.jsonl.gz

Phase 4: phase4_murakumo_classify_did.py
  Murakumo LLM (qwen3-30b) で internet domain → 403 world domain 分類
  → domain_mapping.json → PDS XRPC DID inject (com.etzhayyim.apps.site.classified)

Phase 5: docs update
```

#### Authority Domain Filter (103 domains)

CDX API 不安定のため、全ファイルをストリーミング処理しドメインフィルタを適用。対象: 国際機関 (un.org, who.int, ilo.org 等) + 日本政府 (*.go.jp) + 標準化団体 + セキュリティ Intel + データプラットフォーム。定義: `70-tools/70-tools/70-tools/scripts/domains.txt`。

#### SQL Graph Schema (Common Crawl)

| Node | Properties |
|---|---|
| `:CcDomain` | name, first_seen |
| `:CcPage` | url_hash, url, title, domain, outlink_count, crawl |

| Edge | From → To |
|---|---|
| `:HOSTS` | `:CcDomain` → `:CcPage` |
| `:LINKS_TO` | `:CcPage` → `:CcPage` |

#### Common Crawl Seed Bootstrap (existing)

`seed_from_common_crawl` command fetches CDX index from `data.commoncrawl.org`, parses SURT URLs, filters by domain/status/mime, enqueues to frontier (priority 30, source: `common_crawl`).

#### Project-Driven Seed (cross-actor)

`seed_for_project` command accepts project name + domain list from other apps. For each domain:
1. Checks existing crawl coverage (`WebDomain.pageCount >= 10` → skip)
2. Creates domain DID + frontier entry (priority 40, live crawl)
3. Auto-triggers CommonCrawl CDX seed for historical pages per domain
4. Posts progress to technology topic DID

**Example**: maps.etzhayyim.com invokes `seedForProject({project:"maps", domains:["nlftp.mlit.go.jp","www.gsi.go.jp",...]})` → site crawls 36 geo domains + CC backfill → WET/WAT output → maps subscribes and extracts geo entities via Murakumo NER.

### Embedding Pipeline (Heartbeat Auto-Trigger)

- **Text**: Heartbeat auto-queries `mv_wet_chunk_unembedded` (WetChunk WHERE embedding IS NULL) → cross-actor invoke murakumo.etzhayyim.com `embed-text` (qwen3-vl-8b) → write back to `vertex_wet_chunk.embedding` (REAL[])
- **Visual**: Heartbeat auto-queries unembedded screenshots → cross-actor invoke murakumo.etzhayyim.com `embed-visual` (ColPali)
- **Cadence**: `shouldAnalyze` / `shouldPost` triggers text embedding (batch=30), `shouldPost` triggers visual embedding (batch=10)

### GraphRAG Retrieval (cmdAnswerConvo)

Retrieval cascade (highest fidelity first):
1. **Vector search** on `WetChunk.embedding` (IVF, domain-scoped) — requires Murakumo embedding pipeline active
2. **Keyword search** on `WetChunk.markdown` CONTAINS (new graph schema)
3. **Keyword search** on `WpgWET.markdown` CONTAINS (legacy)
4. **Keyword search** on `Page.text` / `WebPage.text` CONTAINS
5. **Recent content** fallback (no keyword match, chronological)

Graph context enrichment:
- `EdgeChunkOf` traversal: WetChunk → parent Page (version, crawled_at, content_hash)
- `:LINKS_TO` 1-hop expansion: related pages from link graph
- `WebDomain` profile: pageCount, topics

## W Protocol Event Stream Records (DID-scoped)

| Record Kind | Lexicon NSID | Writer DID | Key Fields |
|---|---|---|---|
| `site_topic` | `com.etzhayyim.apps.site.topic` | Primary DID | topic, slug, did |
| `site_domain` | `com.etzhayyim.apps.site.domain` | Primary DID | domain, slug, did, topics |
| `site_page` | `com.etzhayyim.apps.site.page` | Page DID | url, domain, did, title, content_hash, topics (legacy catalog) |
| `site_wet` | `com.etzhayyim.apps.site.wet` | Primary DID | url, domain, chunk_index, total_chunks, markdown, content_hash, language, section, token_count |
| `site_wat` | `com.etzhayyim.apps.site.wat` | Primary DID | url, domain, title, language, mime_type, status_code, outlinks, outlink_count, content_hash |
| `site_screenshot` | `com.etzhayyim.apps.site.screenshot` | Primary DID | url, domain, blob_ref, format, width, height, quality, file_size |
| `site_robots_txt` | `com.etzhayyim.apps.site.robots_txt` | Primary DID | domain, rules, crawl_delay, sitemap_urls, expires_at |
| `site_crawl` | `com.etzhayyim.apps.site.crawl` | Domain DID | session_id, domain, page_count |
| `site_frontier` | `com.etzhayyim.apps.site.frontier` | Primary DID | url, domain, status, priority, depth, topics, source |
| `site_follower_event` | `com.etzhayyim.apps.site.follower_event` | Primary DID | follower_did, action |

## SQL Graph Schema

| Node | Properties |
|---|---|
| `:WebPage` | did, url, domain, title, content_hash, previous_content_hash, version, crawled_at, status_code, content_type, language, topics |
| `:WpgWET` / `:WetChunk` | id, url, domain, chunk_index, total_chunks, markdown, content_hash, language, title, section, topics, token_count, page_did, domain_did, crawled_at, embedding, embedding_norm, ivf_cluster_id |
| `:WpgWAT` | id, url, domain, title, language, mime_type, status_code, outlinks, outlink_count, internal_links, external_links, content_hash |
| `:WpgScreenshot` | id, url, domain, blob_ref, format, width, height, quality, file_size, content_hash |
| `:RobotsTxt` | domain, rules, crawl_delay, sitemap_urls, fetched_at, expires_at |
| `:WebDomain` | domain, did, first_seen, last_crawled, page_count, category, topics, tld |
| `:WebTopic` | topic, slug, did, page_count, created_at |
| `:CrawlSession` | session_id, domain, started_at, page_count, error_count |
| `:FrontierEntry` | url, domain, status, priority, depth, topics, source, enqueued_at, started_at, finished_at, error |

| Edge | From → To |
|---|---|
| `:HOSTED_ON` | `:WebPage` → `:WebDomain` |
| `:LINKS_TO` | `:WebPage` → `:WebPage` |
| `:CHUNK_OF` | `:WetChunk` → `:WebPage` (GraphRAG traversal) |
| `:CRAWLED_IN` | `:WebPage` → `:CrawlSession` |
| `:TAGGED_WITH` | `:WebPage` → `:WebTopic` |
| `:CATEGORIZED_IN` | `:WebDomain` → `:WebTopic` |

## Build & Deploy

```bash
cd 60-apps/etzhayyim-project-site/wasm/etzhayyim-wasm-webpage-w3bpg001
etzhayyim build --no-check && etzhayyim deploy --no-smoke
```
