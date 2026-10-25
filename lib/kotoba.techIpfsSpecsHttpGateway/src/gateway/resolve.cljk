(ns gateway.resolve
  "Turning an `/ipns/{name}` into a CID, with the cache in front of it.

  This is the namespace that moves a deployment off a single naming plane, and
  the shape it takes is **not** a fallback chain. That distinction is the point.

  ## Two planes, discriminated by the name — not ordered by preference

  A `k51…` name is a *key*: holding the Ed25519 private key is the entire
  authority over it, and a record for it is only genuine if it verifies against
  the key the name is derived from. Any other identifier — kotobase.net's graph
  names, a DNSLink label — belongs to whichever plane defines it.

  So the router picks a plane by **what kind of name it is**, and a plane that
  does not own a name never answers for it. Writing this as \"try the DHT, fall
  back to the local registry\" would be a security bug wearing the clothes of a
  reliability feature: a `k51…` name that the DHT cannot answer would fall
  through to a plane that can assert any value it likes for a name whose
  authority is supposed to be a private key nobody else holds. A DHT miss for a
  key-derived name is a **miss**, and the correct answer is 404.

  The legacy plane keeps answering for the names it actually owns, which is
  what makes this a migration rather than a cutover: nothing that resolves
  today stops resolving, and nothing that should be key-authoritative becomes
  registry-authoritative.

  ## The cache is the speed

  Resolution is the expensive step — a DHT round trip, or in kotobase.net's
  case a B2 head GET its own source calls \"the serving floor\" at p50 176ms.
  Everything under a name shares one resolution, so the cache is keyed on the
  name and not the URL, and a stale entry is served while the fresh one is
  fetched rather than making one request per TTL pay the full cost."
  (:require [kotoba.lang.text :as str]
            [gateway.cache :as cache]))

(defn key-derived-name?
  "Is this an IPNS name whose authority is a key? `k51…` (Ed25519, base36
  CIDv1 libp2p-key) and `bafzaa…` (the base32 spelling of the same thing).

  Everything else is a name some registry defines, and this predicate is what
  keeps the two from being confused."
  [name]
  (boolean (and name
                (or (re-matches #"k51[a-z0-9]{55,}" name)
                    (re-matches #"bafz[a-z2-7]{50,}" name)))))

(defn dnslink-name?
  "A DNSLink name is a domain — it has a dot and is not a CID."
  [name]
  (boolean (and name (str/includes? name ".") (not (key-derived-name? name)))))

(defn plane-for
  "Which plane owns this name. Returns `:dht`, `:dnslink`, or `:registry`."
  [name]
  (cond
    (key-derived-name? name) :dht
    (dnslink-name? name) :dnslink
    :else :registry))

(defn route
  "Resolve `name` through exactly the plane that owns it.

  `planes` is `{:dht f :dnslink f :registry f}` where each `f` is
  `(fn [name] -> {:cid … :ttl-ns … :sequence …} or nil)`. Every one is
  injected: this library holds no DHT client, no DNS resolver and no registry
  credentials.

  Returns `{:ok? true :cid … :plane …}` or `{:ok? false :reason :no-such-name
  :plane …}` — and the plane is reported either way, because an operator
  debugging a name needs to know *which* plane was asked before anything else
  is useful."
  [planes name]
  (let [p (plane-for name)
        f (get planes p)]
    (cond
      (nil? f)
      {:ok? false :reason :plane-not-configured :plane p
       :detail (str "no resolver configured for the " (clojure.core/name p) " plane")}

      :else
      (if-let [r (f name)]
        (assoc r :ok? true :plane p)
        {:ok? false :reason :no-such-name :plane p}))))

;; ── cached resolution ─────────────────────────────────────────────────────

(defn lookup
  "Resolve with a cache, returning what to serve *and* what to do next.

  `cache-get` / `cache-put!` are injected — a Cloudflare Worker's `caches`, a
  `js/Map`, a Durable Object, whatever the deployment has.

  The three outcomes are distinguished because a caller must act differently:

  - `:hit` — serve it, do nothing else
  - `:stale` — **serve it now** and refresh in the background. This is the case
    that removes the once-per-TTL latency spike; treating it as a miss puts one
    unlucky request per name per TTL back on the full resolution path
  - `:miss` — resolve before answering

  A resolution that comes back with a *lower* sequence than what is cached is
  rejected: a stale-but-valid record from some peer would otherwise walk the
  name backwards for a whole TTL, which is the failure that makes a gateway
  look like it is losing updates."
  [{:keys [planes cache-get cache-put! now-ms]} request]
  (let [k (cache/cache-key request)
        name (:id request)
        entry (when cache-get (cache-get k))]
    (cond
      (cache/fresh? entry now-ms)
      {:status :hit :cid (:cache/cid entry) :entry entry
       :ttl-ns nil :max-age-source :cache}

      :else
      (let [stale? (cache/usable-while-revalidating? entry now-ms)
            r (route planes name)]
        (cond
          (:ok? r)
          (let [accept? (cache/accept-resolution? entry r)
                entry' (cache/resolution-entry (assoc r :now-ms now-ms))]
            (when (and cache-put! accept?) (cache-put! k entry'))
            {:status (if stale? :refreshed :miss)
             :cid (if accept? (:cid r) (:cache/cid entry))
             :ttl-ns (:ttl-ns r)
             :plane (:plane r)
             :sequence (:sequence r)
             :regression? (not accept?)
             :entry (if accept? entry' entry)})

          ;; Resolution failed but we still hold something recent enough to
          ;; serve. Serving it is right: the publisher's last statement is a
          ;; better answer than a 502, and it is still inside the window the
          ;; Cache-Control header already promised.
          stale?
          {:status :stale :cid (:cache/cid entry) :entry entry
           :error (dissoc r :ok?)}

          :else
          {:status :error :error (dissoc r :ok?) :plane (:plane r)})))))

(defn response-for
  "Assemble the gateway response headers for a resolution outcome, so the
  `Cache-Control` a client sees is derived from the same TTL the cache used."
  [request outcome]
  (cache/headers {:request request
                  :cid (:cid outcome)
                  :ttl-ns (:ttl-ns outcome)}))
