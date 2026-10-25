(ns commoncrawl.iceberg
  "Row-shaping for a SECOND, read-optimized copy of this actor's committed
  pages: an Apache Iceberg table in Cloudflare R2 Data Catalog
  (`net_kotobase.commoncrawl_page`, bucket `net-kotobase-datalake`).

  net-kotobase (`commoncrawl.kotobase/ingest!`) stays the premise — it is
  where a page becomes searchable, and it is the only write `:commit`
  performs inside the governed graph (`commoncrawl.operation`). This table
  is a PROJECTION: delete it and it can be rebuilt by re-walking this
  actor's own ledger (`commoncrawl.store/ledger`) plus a re-fetch from
  Common Crawl, so it never becomes a second place a page's existence is
  decided (superproject ADR-2608039700's D1/premise 'delete and rebuild'
  test, applied to Iceberg instead of D1).

  This is the mirror image of `cloud-itonami/otent`'s `otent.catalog`,
  which keeps bulk observations OUT of the kotobase datom plane and IN
  Iceberg. Here the datom-shaped write already happened (`web.ingest`);
  Iceberg is the one that is additive and optional.

  Pure `.cljc` — no IO. `commoncrawl.live-iceberg` (nbb-only) does the
  actual catalog commit; a `:iceberg-sync-fn` is injected into
  `commoncrawl.loop/tick!` exactly like every other capability in this
  repo (default: disabled, see `default-sync-fn`).")

(def dataset "commoncrawl")
(def namespace-name "net_kotobase")
(def table "commoncrawl_page")

(def ^{:doc "Column order for the Iceberg table. Fixed and explicit — the
  underlying writer (`scripts/iceberg_append.py`) pins the schema from the
  first batch, and a map's iteration order is not a promise (same
  discipline `otent.observation/columns` documents)."}
  columns
  ["url" "domain" "title" "text" "extracted_category" "extracted_summary"
   "extracted_entities_json" "confidence" "embedding_json" "ingest_ok"
   "collection_id" "committed_at"])

(defn- json-encode
  "Same reader-conditional split `otent.observation/->row` uses: real JSON
  under nbb/cljs (the runtime `commoncrawl.live-iceberg` actually ships
  from), `pr-str` under JVM `clojure.test` (parity only — no JVM process
  ever calls the real writer)."
  [v]
  #?(:clj (pr-str v)
     :cljs (js/JSON.stringify (clj->js v))))

(defn ->row
  "A committed page's full data -> the flat, ALL-STRING map the NDJSON
  writer takes, keyed by `columns`. Everything is text for the same reason
  `otent.observation/->row` gives: a numeric/struct column would make this
  layer decide per-page whether a missing confidence is null or zero,
  whether entities is a list or a string — decisions that belong to
  whoever queries the table, not to whoever appends to it."
  [{:keys [url domain title text extracted-category extracted-summary
           extracted-entities confidence embedding ingest-ok? collection-id
           committed-at]}]
  {"url" url
   "domain" domain
   "title" (or title "")
   "text" (or text "")
   "extracted_category" (or extracted-category "")
   "extracted_summary" (or extracted-summary "")
   "extracted_entities_json" (json-encode (or extracted-entities []))
   "confidence" (some-> confidence str)
   "embedding_json" (when (seq embedding) (json-encode embedding))
   "ingest_ok" (some-> ingest-ok? str)
   "collection_id" collection-id
   "committed_at" (some-> committed-at str)})

(defn- commit-fact
  "The `:t :committed` ledger fact `commoncrawl.operation/commit-fact`
  appends to `:audit` for this run, or nil if this run never reached
  `:commit` (should not happen when called for a `:commit` disposition,
  but never assume — `ingest-ok?` degrading to nil rather than throwing
  matches every other optional field here)."
  [audit]
  (last (filter #(= :committed (:t %)) audit)))

(defn row-for-result
  "One `commoncrawl.loop/tick!` seed result
  ({:seed :disposition :state {:page :proposal :embedding :audit ...}}) ->
  an Iceberg row, or nil when this result is not a COMMIT. A HELD or
  fetch-missed seed never reached net-kotobase, so it must not reach this
  projection either — the same 'nothing not admitted may leak in' posture
  `otent.catalog/leaked-keys` asserts in the other direction."
  [{:keys [seed disposition state]} committed-at collection-id]
  (when (= :commit disposition)
    (let [{:keys [page proposal embedding audit]} state]
      (->row {:url (:url seed)
              :domain (:domain seed)
              :title (:title page)
              :text (:text page)
              :extracted-category (:category proposal)
              :extracted-summary (:summary proposal)
              :extracted-entities (:entities proposal)
              :confidence (:confidence proposal)
              :embedding embedding
              :ingest-ok? (:ingest-ok? (commit-fact audit))
              :collection-id collection-id
              :committed-at committed-at}))))

(defn rows-for-tick
  "Every committed result in one tick's raw results -> the Iceberg rows to
  append this tick, in order. Empty when nothing committed — a tick that
  held every seed has nothing new for either target."
  [raw-results committed-at collection-id]
  (->> raw-results
       (keep #(row-for-result % committed-at collection-id))
       vec))

(defn default-sync-fn
  "The default `:iceberg-sync-fn` — Iceberg sync is OFF unless
  `commoncrawl.live-iceberg/sync-fn` (or an equivalent) is explicitly
  injected. Returns a value distinguishable from 'attempted and appended
  zero rows': `:disabled? true` is not the same claim as `:appended 0`,
  per this workspace's rule that an unmeasured question and a measured
  empty answer must never share a shape."
  [_rows]
  {:ok? true :disabled? true :appended 0})
