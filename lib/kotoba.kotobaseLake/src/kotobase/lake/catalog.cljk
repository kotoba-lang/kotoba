(ns kotobase.lake.catalog
  "The catalog: what a lake records about an object it accepted.

  The object plane (`kotobase-storage`'s `IObjectStore`) already accepts any
  bytes -- format-agnosticism is free down there, because bytes are opaque to
  a store keyed by digest. What is *not* free is finding the object again.
  A store you can only read by CID you already hold is not a lake; it is a
  cache with good manners. This namespace is the metadata face that makes
  landed bytes discoverable, and it lives on the datom plane so that every
  query surface over that plane (Datalog, SQL, SPARQL, openCypher, GraphQL,
  Gremlin) reaches it without a second index.

  ## Two entities, and the cut between them is the whole design

  | entity | id | holds | true for |
  |---|---|---|---|
  | object | `obj:<cid>` | `cid`, `size` | ever, for everyone |
  | claim  | `claim:<tenant>\\|<cid>\\|<ingested-at>` | declared type, filename, source, tenant, actor, **and what a sniffer observed** | one ingest event, by one observer |

  `cid` and `size` are functions of the bytes alone. Nothing can ever change
  them, and two tenants landing the same PDF land the *same object* -- dedup
  is not a feature here, it is what content addressing already did.

  Everything else is a function of the bytes **and an observer**. A declared
  media type is a producer's assertion and may be false. A sniff result is
  this library's assertion and changes when `sniff/rules` changes. Putting
  either on the object entity would state as timeless something that is not,
  and would make a classifier upgrade silently rewrite history. So they sit
  on the claim, next to who claimed it and when, with
  `:claim/sniffer-version` recording which classifier spoke.

  ## Format is recorded, never enforced

  `admit` refuses an object for exactly four reasons -- no CID, no size, no
  tenant, no ingest timestamp -- and every one of them is *the record would
  be meaningless*, not *we dislike these bytes*. There is no format on the
  refusal list and there is no allowlist to add one to. Unknown format,
  zero-length body, absent filename, absent media type, and a declared type
  that flatly contradicts the magic bytes all admit successfully.

  The contradiction in particular is recorded as
  `:claim/declared-vs-observed :conflict` and left for the reader to judge.
  Rejecting it would mean the lake refuses precisely the objects most worth
  investigating."
  (:require [kotoba.lang.text :as str]
            [kotobase.lake.sniff :as sniff]))

(def ^:private id-separator "|")

(def envelope-formats
  "Formats that describe a container or a compression envelope rather than the
  payload inside it.

  When a sniff says `:gzip` and the claim says `text/csv`, the two are not in
  conflict -- they are talking about different layers, and a lake that scored
  that as a mismatch would flag most of the compressed data it ever receives."
  #{:gzip :zstd :bzip2 :xz :zip :sevenzip :tar})

;; ── refusal ────────────────────────────────────────────────────────────────

(defn- blank-string? [v]
  (or (nil? v) (not (string? v)) (str/blank? v)))

(defn- valid-size? [v]
  (and (number? v) (== v (long v)) (>= (long v) 0)))

(defn refusals
  "Why this descriptor cannot be recorded, as a vector of maps. Empty means
  admissible.

  Read the list rather than the count: every entry is about the *record*
  being unusable, never about the bytes being unwelcome."
  [{:keys [cid size tenant ingested-at]}]
  (cond-> []
    (blank-string? cid)
    (conj {:field :cid :reason :missing
           :explain "an object with no content address cannot be found again"})

    (not (valid-size? size))
    (conj {:field :size :reason (if (nil? size) :missing :not-a-non-negative-integer)
           :explain "size is a function of the bytes; absent or negative means the caller did not measure them"})

    (blank-string? tenant)
    (conj {:field :tenant :reason :missing
           :explain "claims are per-tenant; an unscoped claim cannot be authorized or retracted"})

    (blank-string? ingested-at)
    (conj {:field :ingested-at :reason :missing
           :explain "a claim without a time is not an event, and claim identity is derived from it"})

    (some #(and (string? %) (str/includes? % id-separator)) [cid tenant ingested-at])
    (conj {:field :id-components :reason :contains-separator
           :explain (str "cid/tenant/ingested-at must not contain " (pr-str id-separator))})))

;; ── identity ───────────────────────────────────────────────────────────────

(defn object-id
  "Global, content-addressed. The same bytes are the same object for everyone."
  [cid]
  (str "obj:" cid))

(defn claim-id
  "Identity of one ingest event.

  Derived rather than generated, so re-running an ingest with the same
  (tenant, cid, timestamp) produces byte-identical quads instead of a second
  indistinguishable claim. Idempotent replay is the common case in a lake --
  a retried upload, a re-run backfill -- and it should not accumulate rows."
  [tenant cid ingested-at]
  (str "claim:" tenant id-separator cid id-separator ingested-at))

;; ── classification comparison ──────────────────────────────────────────────

(defn declared-vs-observed
  "How a declared media type stands against an observation. Never a rejection.

  - `:undetermined` -- one side has nothing to say. This is the majority
    verdict in any real lake: CSV, JSON, EDN, YAML, NDJSON and every log
    format carry no magic bytes at all, so the observer is silent about them
    no matter how good it gets.
  - `:enveloped` -- the observation names a container or compression layer
    (`envelope-formats`) and the claim names something else. Different layers,
    not disagreement.
  - `:agree`
  - `:conflict` -- both spoke, about the same layer, and differed. Recorded,
    not refused."
  [declared observed]
  (let [d (sniff/normalize-media-type declared)
        o (sniff/normalize-media-type (:media-type observed))]
    (cond
      (or (nil? d) (nil? o))                      :undetermined
      (= d o)                                     :agree
      (contains? envelope-formats (:format observed)) :enveloped
      :else                                       :conflict)))

;; ── admission ──────────────────────────────────────────────────────────────

(defn- assoc-some [m k v]
  (if (or (nil? v) (and (string? v) (str/blank? v))) m (assoc m k v)))

(defn admit
  "Turn an ingest descriptor into catalog quads.

  Required: `:cid` `:size` `:tenant` `:ingested-at`.
  Optional, all of it: `:declared-media-type` `:filename` `:source-uri`
  `:ingest-actor` `:prefix` (leading bytes, or an already-computed
  `:observed`).

  Returns `{:admitted? true :object-id .. :claim-id .. :quads #{..}
  :observed .. :declared-vs-observed ..}`, or `{:admitted? false :refusals
  [..]}`.

  Quads are `{:s :p :o}` -- the shape `datom-source` scans and `datalog.index`
  indexes. Values are left as natural EDN; encoding them for a physical tree
  is the engine's boundary, not this library's."
  [{:keys [cid size tenant ingested-at declared-media-type filename source-uri
           ingest-actor prefix observed]
    :as descriptor}]
  (let [refused (refusals descriptor)]
    (if (seq refused)
      {:admitted? false :refusals refused}
      (let [observed (or observed (some-> prefix sniff/classify))
            verdict  (declared-vs-observed declared-media-type observed)
            oid      (object-id cid)
            clid     (claim-id tenant cid ingested-at)
            object-quads
            #{{:s oid :p "object/cid"  :o cid}
              {:s oid :p "object/size" :o (long size)}}
            claim-quads
            (cond-> #{{:s clid :p "claim/object"      :o oid}
                      {:s clid :p "claim/tenant"      :o tenant}
                      {:s clid :p "claim/ingested-at" :o ingested-at}
                      {:s clid :p "claim/declared-vs-observed" :o (name verdict)}
                      ;; Recorded even when the observer said nothing, so a
                      ;; later reclassification is a comparison rather than a
                      ;; guess about which classifier produced the silence.
                      {:s clid :p "claim/sniffer-version" :o sniff/sniffer-version}}
              (not (blank-string? declared-media-type))
              (conj {:s clid :p "claim/declared-media-type" :o declared-media-type})
              (not (blank-string? filename))
              (conj {:s clid :p "claim/filename" :o filename})
              (not (blank-string? source-uri))
              (conj {:s clid :p "claim/source-uri" :o source-uri})
              (not (blank-string? ingest-actor))
              (conj {:s clid :p "claim/ingest-actor" :o ingest-actor})
              (some? observed)
              (conj {:s clid :p "claim/observed-format" :o (name (:format observed))}
                    {:s clid :p "claim/observed-media-type" :o (:media-type observed)}))]
        (-> {:admitted? true
             :object-id oid
             :claim-id clid
             :declared-vs-observed verdict
             :quads (into object-quads claim-quads)}
            (assoc-some :observed observed))))))

;; ── reading the catalog back ───────────────────────────────────────────────
;;
;; Deliberately small and dependency-free: enough to test this library and to
;; use it at hand-scale. At lake scale you hand `:quads` to `datalog.index`
;; and query it with whichever surface the caller already speaks -- that is
;; the entire reason the catalog is quads and not a bespoke record type.

(defn- o-of [quads s p]
  (some (fn [q] (when (and (= (:s q) s) (= (:p q) p)) (:o q))) quads))

(defn objects
  "Every object id in `quads`."
  [quads]
  (into #{} (comp (filter #(= "object/cid" (:p %))) (map :s)) quads))

(defn claims
  "Every claim id in `quads`, optionally narrowed to one object."
  ([quads]
   (into #{} (comp (filter #(= "claim/object" (:p %))) (map :s)) quads))
  ([quads oid]
   (into #{} (comp (filter #(and (= "claim/object" (:p %)) (= oid (:o %)))) (map :s)) quads)))

(defn entity
  "All facts about `s` as a map of attribute string -> value."
  [quads s]
  (reduce (fn [m q] (if (= s (:s q)) (assoc m (:p q) (:o q)) m)) {} quads))

(defn conflicting-claims
  "Claims whose declared type contradicted the observation.

  A lake's most interesting query, and the reason the contradiction is a fact
  rather than a refusal: mislabelled objects are found by asking, not by
  having been turned away at the door."
  [quads]
  (into #{}
        (comp (filter #(and (= "claim/declared-vs-observed" (:p %))
                            (= "conflict" (:o %))))
              (map :s))
        quads))

(defn object-size
  "Size in bytes of `oid`, or nil."
  [quads oid]
  (o-of quads oid "object/size"))
