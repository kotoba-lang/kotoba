(ns kotobase.lake.acquire
  "Getting a scannable source for a catalogued object — and the authorization
  gate in front of it.

  `kotobase.lake.reader` decodes bytes a caller already has.
  `kotobase.lake.tabular` scans a file through an engine. Neither asks **who
  is asking**, because neither is handed a tenant. This namespace is where the
  two meet, and therefore the only place the question can be answered.

  ## Authorization happens at acquisition, not at every scan

  A source, once obtained, is scanned many times by a query planner. Checking
  a tenant on every `-scan` would be the wrong shape twice over: it would put
  a policy decision on the hot path, and it would mean a source that is
  sometimes readable — which nothing downstream is built to handle. So the
  check happens once, here, and what a caller receives is either a source it
  may use freely or a refusal.

  ## A tenant with no holding gets the same answer as a nonexistent object

  Exactly the rule `object-grant/decide` applies to reads, for the same
  reason. Objects are keyed globally by CID because dedup is what content
  addressing already did, so tenant scope lives in `:holding/*` and never in
  the key. That makes \"exists, but not yours\" a sentence this system must
  not say: CIDs are guessable for any content a caller can construct, so
  distinguishing the two answers turns the catalog into a membership oracle
  over every tenant's data.

  There is a test asserting the two refusals are `=`, not merely both
  falsey — a difference in a `:reason` key would leak exactly as well as a
  difference in status code.

  ## This gate is about AUTHORIZATION, not confidentiality

  Worth stating plainly here, because the paragraph above is exactly what
  makes a reader believe otherwise: a namespace that works this hard to avoid
  a membership oracle looks like one that keeps tenant data secret. It does
  not, and it cannot.

  What is gated is **the query path**. Whether the bytes themselves are
  readable by someone who never came through this gate depends entirely on
  where the deployment put them, and this namespace never learns that —
  `read-range` is supplied by the caller.

  In the deployment this workspace actually runs, they **are** world-readable:
  `net-kotobase` archives objects at `<prefix>/objects/<cid>` and serves them
  from an unauthenticated `GET /ipfs/<cid>`. That is a documented, smoke-tested
  public surface rather than an oversight — its threat model scopes the 401
  requirement to *write* surfaces, and its data-handling document states that
  content-addressed bytes stay retrievable from archives and gateways by
  anyone holding the CID.

  So the honest boundary is:

  - this gate decides **who may query an object through the lake**
  - it decides **nothing** about who may fetch its bytes by CID
  - **tenant-confidential data must be encrypted before admission**, because
    the CID of anything a caller can reconstruct is computable by that caller,
    and the gateway will serve it

  ## Nothing is fetched before the gate

  `read-range` is a *function*, not bytes, and it is only ever passed to a
  reader after authorization succeeds. An unauthorized caller costs one
  catalog lookup and no transfer — the same discipline
  `parquet.decode/check-readable!` applies to unsupported codecs."
  (:require [kotobase.lake.catalog :as catalog]
            [kotobase.lake.reader :as reader]))

(def ^:private refused
  "One value for every refusal that must not be distinguishable.

  A shared constant rather than two equal literals: two literals drift the
  moment someone adds a `:detail` to one of them, and the leak would be
  invisible in review."
  {:ok? false :reason :no-such-object})

(defn holds?
  "Does `tenant` have a live claim on `cid` in these catalog quads?

  Claims are per ingest event and an object may have many; one is enough.
  Retraction is out of scope here — `:holding/*` tombstones (ADR-2608012600
  D7) are written by the settle path, and this reads claims, so a lake using
  both must filter tombstoned holdings before calling."
  [quads cid tenant]
  (let [oid (catalog/object-id cid)]
    (boolean
     (some (fn [claim]
             (= tenant (get (catalog/entity quads claim) "claim/tenant")))
           (catalog/claims quads oid)))))

(defn- claimed-types
  "Declared and observed media types across this tenant's claims on the object.

  Both, because either may be the one a reader is registered for: the
  producer's declaration knows what magic bytes cannot say, and the
  observation survives a producer that declared wrongly."
  [quads cid tenant]
  (let [oid (catalog/object-id cid)]
    (into []
          (comp (map #(catalog/entity quads %))
                (filter #(= tenant (get % "claim/tenant")))
                (mapcat (juxt #(get % "claim/declared-media-type")
                              #(get % "claim/observed-media-type")))
                (remove nil?)
                (distinct))
          (catalog/claims quads oid))))

(defn source-for
  "A scannable `IPatternSource` for one catalogued object, or a refusal.

  `request` is `{:cid :tenant :read-range :size-bytes}`. `read-range` is
  `(fn [start end] -> bytes)` — a capability the caller already holds, handed
  on only if the gate opens.

  -> `{:ok? true :source s :via media-type}` or `{:ok? false :reason ..}`."
  [registry quads {:keys [cid tenant read-range size-bytes]}]
  (cond
    (not (and cid tenant))
    {:ok? false :reason :incomplete-request}

    ;; The gate. Before any type lookup, and long before any byte.
    (not (holds? quads cid tenant))
    refused

    :else
    (let [types (claimed-types quads cid tenant)
          hit (some (fn [mt] (when-let [f (reader/scan-reader registry mt)] [mt f]))
                    types)]
      (if-not hit
        {:ok? false :reason :no-scan-reader :tried types}
        (let [[mt f] hit]
          {:ok? true
           :via mt
           :source (f {:cid cid
                       :size-bytes size-bytes
                       :read-range read-range
                       :subject-prefix (str (catalog/object-id cid) "#row")})})))))
