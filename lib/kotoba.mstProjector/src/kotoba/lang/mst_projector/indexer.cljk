(ns kotoba.lang.mst-projector.indexer
  "Indexed-view writer for AT Protocol MST commit records -- PURE core over
  an injected `IIndex` storage protocol. Ported from
  `mst_projector/indexer.py` (LanceDB-backed) per the org-taxonomy
  library-placement rule; see this repo's README for the full provenance
  and for why the storage backend itself is NOT LanceDB here.

  This namespace models the row shape, the record-flattening rule, and the
  per-collection upsert/delete/query/count/list operations as pure
  functions/orchestration over `IIndex` -- it performs ZERO storage I/O
  itself, mirroring `kotoba.lang.ipfs`'s `IHttp` seam (this ecosystem's
  established injected-capability pattern): the host supplies a concrete
  `IIndex` (this repo ships one reference implementation,
  `kotoba.lang.mst-projector.mem-index`), and this namespace never talks to
  a specific database directly.

  Row shape (string-keyed map, JSON-response-ready as-is):
    \"did\"         : String  -- repo DID that authored the record
    \"rkey\"        : String  -- record key within the collection
    \"record_cid\"  : String  -- CID of the record in the AT Protocol commit
    \"indexed_at\"  : String  -- ISO-8601 UTC timestamp (Z suffix) of indexing time
    \"record_json\" : String  -- full record value as a JSON blob
    + flattened top-level fields from the record value: primitives (string/
      number/boolean/nil) keep their type; nested maps/vectors are
      JSON-stringified into string columns (never modeled as real nested
      columns) -- matching python's `_flatten_record`.

  Deliberate simplification vs. the LanceDB original: `indexer.py` mapped
  collection NSIDs (e.g. \"app.bsky.feed.post\") to LanceDB table names by
  replacing \".\" with \"_\" (LanceDB rejects dots in table names), and
  `list_collections` did a lossy reverse mapping (\"_\" -> \".\") back to a
  guess at the original NSID. Since `IIndex` does not commit to any
  particular storage engine's naming restrictions, this port drops that
  translation entirely -- collections are keyed by the exact NSID string
  throughout, so `list-collections` here is *exactly* correct (an
  improvement over the original's lossy diagnostic-only reverse mapping)."
  (:require [json.data-json :as json])
  (:import (java.time Instant)))

;; ---------------------------------------------------------------------------
;; Capability seam -- host-injected storage. Core never touches a database.
;; ---------------------------------------------------------------------------

(defprotocol IIndex
  "Host-injected storage backend for the MST-projector index. Core (this
  namespace) builds every row and every filter description; the host only
  persists and retrieves rows for a named collection. Mirrors
  `kotoba.lang.ipfs/IHttp`'s seam shape/spirit.

  A `filter-map` (accepted by `-query`) is either `nil` (no filter) or
  `{:field <String> :value <String>}`, an equality predicate against one
  flattened row field, string-compared (both sides coerced to `str`) -- this
  is exactly the shape of every filter `query_api.py` ever builds (a single
  `field = value` predicate; the python original expressed this as a raw
  SQL where-clause string, which this protocol replaces with plain data so
  no backend need parse or interpret SQL)."
  (-upsert! [this collection row]
    "Upsert `row` (a map with, at minimum, string keys \"did\"/\"rkey\") into
    `collection`. `collection` is created lazily on its first upsert. Because
    (did, rkey) is the logical primary key, an upsert for a key that already
    exists in `collection` REPLACES the existing row (this is the one place
    the delete-then-add mechanics the python original spells out explicitly
    live -- pushed down into the backend, which is best placed to do it
    efficiently for its own storage engine). Returns nil.")
  (-delete! [this collection did rkey]
    "Delete the row keyed by (`did`, `rkey`) from `collection`. A no-op --
    and must NOT create `collection` -- if `collection` does not exist yet
    (a delete can legitimately arrive before any create for a fresh
    collection) or if no row with that key exists in it. Returns nil.")
  (-query [this collection filter-map limit]
    "Return up to `limit` rows from `collection` (a vector, oldest-inserted
    first; an upsert that replaces an existing key moves that row to the
    end, matching the delete-then-add re-ordering `index_op` produces)
    matching `filter-map` (see above; `nil` matches every row). An empty
    vector if `collection` does not exist.")
  (-count-rows [this collection]
    "Return the row count for `collection`; 0 if it does not exist.")
  (-list-collections [this]
    "Return the seq of every collection name that has ever received an
    upsert (even if every row in it has since been deleted -- a collection,
    once created, is never implicitly dropped; matches LanceDB's
    delete-rows-not-drop-table behaviour).")
  (-describe [this]
    "Return a short, human-readable String describing this backend for
    diagnostics (e.g. /healthz's \"data_dir\" field) -- NOT a dump of the
    data itself (a naive `pr-str` of an in-memory backend would leak every
    indexed row into a liveness-probe response). e.g. \"in-memory\" or
    \"in-memory (persisted: /path/to/file.edn)\"."))

;; ---------------------------------------------------------------------------
;; Pure: record flattening + row assembly + timestamps
;; ---------------------------------------------------------------------------

(defn now-iso
  "Current UTC instant as an ISO-8601 string with a literal Z suffix (no
  '+00:00', matching python's `datetime.now(timezone.utc).isoformat()`
  post-processing)."
  []
  (str (Instant/now)))

(defn- flat-scalar?
  [v]
  (or (string? v) (number? v) (boolean? v) (nil? v)))

(defn flatten-record
  "Flatten a record map for row storage: top-level scalars (string/number/
  boolean/nil) stay typed; nested maps/vectors are JSON-stringified into
  string values. Mirrors python's `_flatten_record`."
  [record]
  (into {}
        (map (fn [[k v]]
               [k (if (flat-scalar? v) v (json/write-str v))]))
        record))

(defn build-row
  "Assemble the full row map for one record op: base columns
  (did/rkey/record_cid/indexed_at/record_json) merged with the flattened
  record fields. Faithful to python's `{**base, **flat}` spread order: a
  flattened field with the same name as a base column (e.g. a record that
  happens to have a top-level \"did\" field of its own) WINS -- this is a
  quirk of the original `index_op`, preserved here rather than silently
  fixed, since it is externally observable behaviour."
  [did rkey record-cid record-value]
  (merge {"did" did
          "rkey" rkey
          "record_cid" record-cid
          "indexed_at" (now-iso)
          "record_json" (json/write-str record-value)}
         (flatten-record record-value)))

;; ---------------------------------------------------------------------------
;; Orchestration -- thin wrappers over IIndex, mirroring Indexer's public API
;; ---------------------------------------------------------------------------

(defn index-op!
  "Write a single record op into the index. Upserts by (did, rkey): if a row
  with the same (did, rkey) already exists in `collection` it is replaced
  (covers update ops). Delete ops should call `delete-op!` instead. Mirrors
  python's `Indexer.index_op`."
  [index collection did rkey record-cid record-value]
  (-upsert! index collection (build-row did rkey record-cid record-value))
  nil)

(defn delete-op!
  "Remove a record from the index (MST tombstone / delete op). No-op if
  `collection` has not been indexed yet. Mirrors python's
  `Indexer.delete_op`."
  [index collection did rkey]
  (-delete! index collection did rkey)
  nil)

(defn count-rows
  "Total row count for `collection`; 0 if not yet indexed. Mirrors python's
  `Indexer.count_rows`."
  [index collection]
  (-count-rows index collection))

(defn list-collections
  "Every indexed collection name. Mirrors python's
  `Indexer.list_collections` (see namespace docstring re: the dropped
  underscore/dot table-name translation)."
  [index]
  (vec (-list-collections index)))

(defn describe
  "Short diagnostic description of the backend (see `IIndex/-describe`).
  Used by the query-api's /healthz handler for the wire-compatible
  \"data_dir\" field."
  [index]
  (-describe index))

(defn query
  "Query records in `collection`, optionally filtered by `filter-map` (see
  `IIndex/-query`), up to `limit` rows (default 100). Mirrors python's
  `Indexer.query`."
  ([index collection] (query index collection nil 100))
  ([index collection filter-map] (query index collection filter-map 100))
  ([index collection filter-map limit]
   (vec (-query index collection filter-map limit))))
