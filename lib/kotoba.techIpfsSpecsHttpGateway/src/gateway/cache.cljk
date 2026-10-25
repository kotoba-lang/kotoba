(ns gateway.cache
  "Caching policy for an IPFS gateway — where the speed actually comes from.

  A gateway is not fast because it is close to the user. It is fast because
  **content addressing gives it the strongest cache key that exists**, and
  because the one part that does change says exactly how long it is good for.

  Two regimes, and conflating them is the whole game:

  **`/ipfs/{cid}` is immutable, forever.** The identifier is a hash of the
  bytes; the bytes cannot change without changing the identifier. So the
  response is cacheable for as long as anything can be cached, and revalidation
  is pure waste — there is nothing that could have changed. The spec's value is
  `public, max-age=29030400, immutable` (a year), and `immutable` is what stops
  a browser revalidating on reload.

  **`/ipns/{name}` is mutable, and the record says for how long.** The IPNS
  record carries a `ttl`, and that is not a suggestion the publisher makes to
  be polite — it is the publisher stating how stale an answer may be. Caching
  longer than the TTL serves content the publisher has already replaced;
  caching for a fixed short time instead ignores a publisher who told you it is
  stable for a day, and puts every request back on the resolution path.

  That resolution path is the slow part. Measured on this workspace's own
  kotobase.net (`kotobase-cf-wasm.head`, live probe 2026-07-29): every read pays
  a head lookup **it cannot cache**, p50 176ms, and that is documented in the
  source as \"the serving floor\". A gateway that caches the *resolution* for
  the record's TTL removes that floor for every request after the first, which
  is a larger win than anything done to the content path.

  ## Why `stale-while-revalidate` matters more here than usual

  When an IPNS TTL expires the gateway must resolve again — a DHT round trip,
  hundreds of milliseconds. `stale-while-revalidate` lets the cache serve the
  slightly-stale answer *immediately* and refresh behind it, so the expiry is
  invisible to the request that happens to land on it. Without it, one unlucky
  request per TTL per name pays the full resolution cost."
  (:require [kotoba.lang.text :as str]
            [gateway.request :as req]))

(def ^:const immutable-max-age
  "One year, the spec's value. Not \"forever\" because `max-age` is capped at a
  year by convention, and `immutable` carries the rest of the meaning."
  29030400)

(def ^:const min-mutable-max-age
  "Never cache a mutable name for less than a minute, even if the record says
  so. A publisher that sets a one-second TTL has made every request a
  resolution, and at gateway scale that is a self-inflicted denial of service
  against the routing layer rather than a freshness guarantee anyone benefits
  from."
  60)

(def ^:const max-mutable-max-age
  "Cap a mutable name at an hour regardless of the record. A record with a
  30-day TTL is asking a gateway to keep serving a name for a month after the
  publisher moved it — the publisher cannot revoke a cache entry, so the
  gateway bounds the damage."
  3600)

(defn ns->seconds
  "IPNS TTLs are in **nanoseconds** (specs.ipfs.tech/ipns/ipns-record). Reading
  the number as seconds gives a cache lifetime a billion times too long, which
  looks like a gateway that never updates."
  [ttl-ns]
  (when (and ttl-ns (pos? ttl-ns))
    (quot ttl-ns 1000000000)))

(defn mutable-max-age
  "The `max-age` for a resolved IPNS name: the record's TTL, clamped.

  Returns `min-mutable-max-age` when the record carries no TTL — an absent TTL
  is not \"cache forever\", and treating it as one is how a gateway pins a name
  to a value the publisher has replaced."
  [ttl-ns]
  (let [s (ns->seconds ttl-ns)]
    (cond
      (nil? s) min-mutable-max-age
      (< s min-mutable-max-age) min-mutable-max-age
      (> s max-mutable-max-age) max-mutable-max-age
      :else s)))

(defn cache-control
  "The `Cache-Control` header for a request.

  For `/ipns/`, `stale-while-revalidate` is set to the same span as `max-age`:
  a name that is good for an hour is one whose hour-old answer is a reasonable
  thing to serve for a moment while the real one is fetched."
  [{:keys [immutable? ttl-ns]}]
  (if immutable?
    (str "public, max-age=" immutable-max-age ", immutable")
    (let [a (mutable-max-age ttl-ns)]
      (str "public, max-age=" a ", stale-while-revalidate=" a))))

(defn etag
  "The `Etag` for a response.

  A **strong** etag (`\"cid\"`) is correct only when the body is exactly the
  addressed bytes — a raw block or a CAR. A deserialized response is a *render*
  of the DAG: the same CID can produce a different body across gateway versions
  (directory listing HTML, `index.html` selection, UnixFS traversal), so it
  takes a **weak** etag. Marking a deserialized response strong tells caches
  and `If-None-Match` clients that two byte-different responses are identical,
  which is how a client ends up unable to fetch the corrected one."
  [cid {:keys [format]}]
  (when cid
    (if (#{"application/vnd.ipld.raw" "application/vnd.ipld.car"} format)
      (str "\"" cid "\"")
      (str "W/\"" cid "\""))))

(defn cache-key
  "The key a resolution should be cached under.

  Deliberately **not** the whole URL. The expensive thing is turning a name
  into a CID, and that answer is shared by every path under the name — caching
  it per-URL means `/ipns/x/a` and `/ipns/x/b` each pay their own resolution
  for the same record."
  [{:keys [namespace id]}]
  (str namespace "/" id))

(defn resolution-entry
  "A cache entry for a resolved name: the CID it resolved to, when that expires,
  and the record's sequence.

  `sequence` is kept so a later resolution that returns an *older* record can be
  recognized and dropped. Without it a gateway can be walked backwards: a peer
  serves a stale-but-valid record, the cache accepts it as fresh, and the name
  regresses for a whole TTL."
  [{:keys [cid ttl-ns sequence now-ms]}]
  {:cache/cid cid
   :cache/sequence sequence
   :cache/stored-at now-ms
   :cache/expires-at (+ now-ms (* 1000 (mutable-max-age ttl-ns)))})

(defn fresh?
  [entry now-ms]
  (boolean (and entry (< now-ms (:cache/expires-at entry)))))

(defn usable-while-revalidating?
  "May a stale entry be served while a fresh one is fetched? Yes, up to the
  same span again — matching the `stale-while-revalidate` the header promises,
  so the cache and the header cannot disagree."
  [entry now-ms]
  (boolean
   (and entry
        (< now-ms (+ (:cache/expires-at entry)
                     (- (:cache/expires-at entry) (:cache/stored-at entry)))))))

(defn accept-resolution?
  "Should a newly resolved record replace what is cached?

  Only if it is at least as new. A record with a *lower* sequence is a stale
  answer from some peer, and accepting it walks the name backwards for a full
  TTL — the failure that makes a gateway look like it is losing updates."
  [entry {:keys [sequence]}]
  (or (nil? entry)
      (nil? (:cache/sequence entry))
      (nil? sequence)
      (>= sequence (:cache/sequence entry))))

(defn headers
  "The full response header map for a gateway response.

  `X-Ipfs-Path` and `X-Ipfs-Roots` are not decoration: the first tells a client
  what it actually asked for after any redirect, and the second lists the CIDs
  of every path segment, which is what lets a client verify a deserialized
  response it would otherwise have to trust."
  [{:keys [request cid roots ttl-ns format content-type filename]}]
  ;; Immutability is a property of the *namespace*, derived by
  ;; `gateway.request/immutable?`. Reading a `:immutable?` key off the parsed
  ;; request looks right and is always nil — which silently gives every /ipfs/
  ;; response the short mutable max-age, throwing away the entire reason a
  ;; content-addressed gateway is fast.
  (cond-> {"Cache-Control" (cache-control {:immutable? (req/immutable? request)
                                           :ttl-ns ttl-ns})
           "X-Ipfs-Path" (str "/" (:namespace request) "/" (:id request)
                              (when (seq (:path request)) (str "/" (:path request))))
           "Accept-Ranges" "bytes"}
    cid (assoc "Etag" (etag cid {:format format}))
    (seq roots) (assoc "X-Ipfs-Roots" (str/join "," roots))
    (or format content-type) (assoc "Content-Type" (or format content-type))
    filename (assoc "Content-Disposition" (str "inline; filename=\"" filename "\""))))
