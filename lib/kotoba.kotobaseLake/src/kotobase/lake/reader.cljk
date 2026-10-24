(ns kotobase.lake.reader
  "Schema-on-read: the seam where an object's bytes finally get parsed, long
  after they were accepted.

  Nothing in `kotobase.lake.catalog` parses. That is what lets the write path
  take anything. The cost is paid here instead, and this namespace exists to
  make sure the cost stays *bounded to one object*:

  - **No reader is not a failure.** An object with no registered decoder is
    still landed, still catalogued, still retrievable by CID, and still
    joins against every other fact in the plane. `decode` returns
    `{:decoded? false :reason :no-reader}` and the caller carries on. A lake
    where an unparseable object is a hole in the query is a schema-on-write
    system that has not admitted it yet.
  - **A decoder that throws does not fail the query.** Malformed input is the
    normal state of real data. `decode` catches, records `:decoder-threw`
    with the message, and the surrounding scan keeps going over the objects
    that did parse.
  - **The type is a hypothesis, not a fact.** `candidate-types` yields the
    declared type first and the observed one second, and `decode` tries them
    in order. Neither was authoritative at write time and neither becomes
    authoritative here: what settles it is which decoder actually succeeded,
    reported as `:via`.

  Decoders are `(fn [bytes ctx] -> seq-of-quads)`. `ctx` carries the claim
  and object ids so a decoder can attach the rows it produces to the object
  they came from.

  Decoding is synchronous over bytes the caller already holds. Fetching them
  is deliberately not this library's job -- on a Worker that read is a
  Promise, on the JVM it is not, and a portable zero-dep library that tried
  to own both would force one shape on the other."
  (:require [datom.source :as source]
            [kotobase.lake.sniff :as sniff]))

(defn registry
  "An empty reader registry."
  []
  {})

(defn register
  "Register a **materializing** decoder for `media-type`: `(fn [bytes ctx] ->
  quads)`. Type is normalised, so `text/csv; charset=utf-8` and `TEXT/CSV`
  register the same decoder."
  [reg media-type decoder]
  (assoc reg (sniff/normalize-media-type media-type) {::access :materialize
                                                     ::fn decoder}))

(defn register-scan
  "Register a **scanning** reader for `media-type`: `(fn [handle] -> an
  IPatternSource)`, where handle is
  `{:cid :size-bytes :read-range :subject-prefix}`.

  The two profiles are declared rather than inferred, for the same reason
  `kotobase-storage` makes a backend declare its ref profile: a caller cannot
  discover by trying, and the failure of guessing is silent. A format with a
  footer and per-chunk statistics — Parquet, ORC, Arrow IPC — can answer a
  pattern by reading byte ranges and belongs here. CSV, JSON, NDJSON, EDN and
  every log format must be read whole to answer anything at all and belong in
  `register`; that is a property of those formats, not a gap to close later."
  [reg media-type f]
  (assoc reg (sniff/normalize-media-type media-type) {::access :scan ::fn f}))

(defn access
  "`:scan`, `:materialize`, or nil when nothing is registered for this type."
  [reg media-type]
  (::access (get reg (sniff/normalize-media-type media-type))))

(defn scan-reader
  "The scanning reader for `media-type`, or nil. A materializing decoder is
  deliberately not returned here: it cannot answer a pattern without reading
  the whole object, and silently substituting one would turn a range read into
  a full download at the moment the file got big enough to matter."
  [reg media-type]
  (let [e (get reg (sniff/normalize-media-type media-type))]
    (when (= :scan (::access e)) (::fn e))))

(defn- decoder-for [reg media-type]
  (let [e (get reg (sniff/normalize-media-type media-type))]
    (when (= :materialize (::access e)) (::fn e))))

(defn candidate-types
  "Ordered, de-duplicated hypotheses about what this claim holds.

  Declared first: a producer that bothered to name the type usually knows
  something the bytes do not say -- `text/csv` and `application/json` have no
  magic to observe. Observed second: it is what survives a producer that
  named the type wrongly."
  [{:keys [declared-media-type observed]}]
  (into []
        (comp (map sniff/normalize-media-type)
              (remove nil?)
              (distinct))
        [declared-media-type (:media-type observed)]))

(defn decode
  "Decode `bytes` for one claim. Never throws.

  Returns `{:decoded? true :quads [..] :via \"text/csv\"}` or
  `{:decoded? false :reason :no-reader :tried [..]}` or
  `{:decoded? false :reason :decoder-threw :via .. :message ..}`."
  [reg {:keys [claim-id object-id] :as claim} bytes]
  (let [tried (candidate-types claim)]
    (or (some (fn [mt]
                (when-let [decoder (decoder-for reg mt)]
                  (try
                    {:decoded? true
                     :via mt
                     :quads (vec (decoder bytes {:claim-id claim-id
                                                 :object-id object-id
                                                 :media-type mt}))}
                    (catch #?(:clj Throwable :cljs :default) e
                      {:decoded? false
                       :reason :decoder-threw
                       :via mt
                       :message #?(:clj (.getMessage ^Throwable e)
                                   :cljs (or (.-message e) (str e)))}))))
              tried)
        {:decoded? false :reason :no-reader :tried tried})))

(defn source
  "A `datom.source/IPatternSource` over catalog quads plus whatever decoded.

  This is the join that makes the lake queryable as one thing: the catalog
  facts (who landed what, when, how big) and the decoded rows sit in the same
  scannable plane, so a single query can ask for rows *and* their provenance.
  Objects that did not decode contribute their catalog facts and nothing
  else -- they stay visible as objects rather than vanishing."
  [catalog-quads decoded-quads]
  (source/of-quads (into (set catalog-quads) decoded-quads)))
