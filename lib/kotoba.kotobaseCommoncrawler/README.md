# net-kotobase-commoncrawler

CommonCrawl data ingestion (WARC, HTML, images) to kotoba Datom-log (EAVT) representation, persisted to **kotobase.net** through the `kotobase.store/IStore` seam.

## Purpose

This project processes CommonCrawl data (webpages, documents, images) from WARC files, extracts structured content, converts to EDN/Datom-log format, and makes it searchable via Datomic on kotobase.net.

## Key Components

- **`core.cljc`** — Kotoba Datom-log representation (EAVT, Datomic-isomorphic) for CommonCrawl data
- **`warc.cljc`** — WARC (Web ARChive) format parsing and range-fetch utilities
- **`html.cljc`** — HTML document extraction and text normalization
- **`images.cljc`** — Image URL extraction and metadata capture
- **`ingest.cljc`** — CommonCrawl CDX index querying and WARC capture fetching
- **`store.cljc`** — kotobase.net `IStore` integration for persistence

## Usage

```clojure
(require '[net-kotobase.commoncrawler.core :as cc-core]
         '[net-kotobase.commoncrawler.ingest :as ingest]
         '[net-kotobase.commoncrawler.store :as store])

;; Query CommonCrawl index and extract data
(def caps {:http-fn http-fn :json-read json-read})
(def captures (ingest/index-query caps "CC-MAIN-2024-51" "example.com/*" 10))

;; Process WARC records and create datom-log entities
(def entities (map cc-core/warc-to-entity captures))
(def datoms (cc-core/log entities))

;; Persist to kotobase.net
(def k-store (store/kotobase-store xrpc-fn))
(store/-put k-store "commoncrawl" "domains" "example.com" datoms)
```

## Dependencies

- `datom-clj` — Kotoba Datom-log representation (EAVT)
- `kotobase-clj` — IStore protocol for kotobase.net persistence

## Testing

```bash
kbb -M:dev:test
```

## License

Part of the com-junkawasaki monorepo. See root LICENSE for details.

## Repository ownership

This repository is owned by the GitHub organization `net-kotobase` as `net-kotobase/commoncrawler`. Reusable language and storage contracts remain in `kotoba-lang`.