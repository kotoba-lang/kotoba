(ns kotobase.ethereum.client
  "HTTP JSON-RPC transport for kotobase.ethereum.rpc — POSTs a JSON-RPC 2.0
  request to a configured node/provider URL and returns decoded results,
  caching observed data into a `kotobase.store/IStore`.

  .cljs, NOT .cljc — this namespace needs real HTTP I/O (Node's built-in
  `fetch`), so it only runs under a Node.js-hosted ClojureScript runtime
  (nbb in this repo). It is a pure CONSUMER of `kotobase.ethereum.rpc`
  (unmodified, .cljc, zero I/O) — every protocol decision (which methods
  are allowed, how a result decodes) still happens there; this namespace
  only moves bytes and owns the caching policy below.

  ENDPOINT: the target node/provider URL is always caller-supplied
  (`:endpoint` in `create-client`'s opts) — this namespace hardcodes no
  provider hostname and bundles no API key/credential of any kind. The
  deploy shell (or, for local dev/tests, the caller) owns that
  configuration entirely.

  SAFETY BOUNDARY: same as `kotobase.ethereum.rpc` — read-only observer,
  no transaction construction/signing/broadcast, no private keys, no
  wallet functionality. `call!` below routes every request through
  `kotobase.ethereum.rpc/build-request`, so the whitelist enforcement
  there applies here too; this namespace adds no method of its own.

  CACHING POLICY (kept deliberately simple — v0.1, not over-engineered):
    - `eth_chainId`               -> cached forever per :cache-scope. A
      network's chain id is a constant for the life of the chain.
    - `eth_getBlockByNumber` /
      `eth_getBlockByHash`        -> cached forever, but ONLY when the
      request identifies a CONCRETE block (a numeric hex tag or a 32-byte
      block hash) — never for the mutable tags \"latest\"/\"earliest\"/
      \"pending\"/\"safe\"/\"finalized\". Caveat: a block within roughly
      the last ~2 epochs of the real chain tip could in principle still be
      reorged out even though it was returned for a concrete number/hash
      at fetch time; treat this cache as a \"confirmed data\" cache, not a
      canonical-chain guarantee for the most recent handful of blocks.
    - `eth_getTransactionByHash`  -> cached ONLY once the transaction has
      actually been mined (decoded result is non-nil and has a
      `:block-hash`). A pending tx (result nil, or a tx object with no
      block yet) is never cached, so a later call can observe it land.
    - `eth_getLogs`                -> cached forever, but ONLY when both
      `fromBlock` and `toBlock` in the filter are concrete numeric hex
      tags (not \"latest\"/\"pending\"/etc) — an already-finalized
      historical log range doesn't change.
    - `eth_blockNumber`, `eth_getBalance`, `eth_call` -> NEVER cached.
      These are current/mutable-state reads; `eth_getBalance`/`eth_call`
      do accept a block-tag parameter and a per-(address,block) cache
      could in principle be correct, but that's more machinery than this
      v0.1 needs — always live keeps the policy easy to reason about."
  (:require [kotobase.ethereum.rpc :as rpc]
            [kotobase.local :as local]
            [kotobase.protocols.json :as json]
            [kotobase.store :as st]))

(def default-timeout-ms 15000)

(defn create-client
  "opts:
    :endpoint     required. The JSON-RPC HTTP endpoint URL — caller/deploy
                  shell supplied, never hardcoded here.
    :store        optional `kotobase.store/IStore`; defaults to a fresh
                  `kotobase.local/local-store`.
    :cache-scope  optional string used to namespace cache keys so multiple
                  networks/endpoints can safely share one IStore; defaults
                  to `:endpoint` itself.
    :fetch-fn     optional override of the (url, init) -> Promise<Response>
                  function; defaults to the Node global `fetch`. Tests
                  inject a fake here instead of hitting the network.
    :timeout-ms   optional per-request abort timeout; default 15000."
  [{:keys [endpoint store cache-scope fetch-fn timeout-ms]}]
  (when-not (and (string? endpoint) (seq endpoint))
    (throw (ex-info "kotobase.ethereum.client: :endpoint is required" {})))
  {:endpoint endpoint
   :store (or store (local/local-store))
   :cache-scope (or cache-scope endpoint)
   :fetch-fn (or fetch-fn js/fetch)
   :timeout-ms (or timeout-ms default-timeout-ms)
   :next-id (atom 0)})

(defn- next-id! [client] (swap! (:next-id client) inc))

(defn- post-json!
  "POST `req` (a JSON-RPC request map) to the client's endpoint. Returns a
  Promise of the parsed JSON response (string-keyed map, via
  kotobase.protocols.json/parse — the dependency-zero JSON this repo
  reuses from kotobase-protocols rather than re-implementing)."
  [{:keys [endpoint fetch-fn timeout-ms]} req]
  (-> (fetch-fn endpoint
                #js {:method "POST"
                     :headers #js {"content-type" "application/json"}
                     :body (json/encode req)
                     :signal (when timeout-ms (js/AbortSignal.timeout timeout-ms))})
      (.then (fn [resp] (.text resp)))
      (.then (fn [text] (json/parse text)))))

(defn call!
  "Low-level: send exactly one JSON-RPC call, bypassing any cache. Returns
  a Promise of `kotobase.ethereum.rpc/parse-response`'s normalized map
  ({:ok? true :result ...} or {:ok? false :error {...}}).

  Throws synchronously (before any network I/O) if `method` is not on the
  whitelist — `rpc/build-request` is the enforcement point."
  [client method params]
  (let [req (rpc/build-request method params (next-id! client))]
    (.then (post-json! client req) rpc/parse-response)))

(defn- rpc-fail
  "NOTE: under nbb (SCI), an ex-info thrown from inside a Promise callback
  and caught on the other side of that Promise boundary reliably keeps its
  `.message` string but does NOT reliably keep custom `ex-data` keys (SCI
  re-wraps the exception when it crosses back out of interpreted code at
  the JS Promise machinery boundary) — so callers that need to distinguish
  failure reasons programmatically should match on `.-message` /
  `ex-message`, not `(:type (ex-data err))`, for errors raised here.
  `error` (the JSON-RPC {:code :message :data} map) is still folded into
  the message string below so it's visible even after that re-wrap."
  [method error]
  (ex-info (str "kotobase.ethereum.client: " method " failed: " (pr-str error))
           {:type ::rpc-error :method method :error error}))

(defn- call-decoded!
  "call! + decode-result, or throw on a JSON-RPC error response."
  [client method params]
  (.then (call! client method params)
         (fn [{:keys [ok? result error]}]
           (if ok?
             (rpc/decode-result method result)
             (throw (rpc-fail method error))))))

(defn- concrete-block-tag?
  "Is `tag` a concrete 32-byte hash or numeric quantity (0x-prefixed hex),
  as opposed to one of the mutable tag keywords (\"latest\"/\"earliest\"/
  \"pending\"/\"safe\"/\"finalized\", none of which are hex strings)?"
  [tag]
  (rpc/hex-string? tag))

;; -------------------------------------------------------- cache helpers

(defn- cache-get [client coll k] (st/-get (:store client) coll k))
(defn- cache-put! [client coll k v] (st/-put (:store client) coll k v) v)

;; ----------------------------------------------------------- public API

(defn block-number!
  "eth_blockNumber -> Promise<int>. Never cached (current chain tip)."
  [client]
  (call-decoded! client "eth_blockNumber" []))

(defn chain-id!
  "eth_chainId -> Promise<int>. Cached forever per :cache-scope (a
  network's chain id never changes)."
  [client]
  (let [coll [:kotobase.ethereum/chain-id]
        k (:cache-scope client)]
    (if-let [cached (cache-get client coll k)]
      (js/Promise.resolve cached)
      (.then (call-decoded! client "eth_chainId" [])
             (fn [decoded] (cache-put! client coll k decoded))))))

(defn get-block-by-number!
  "eth_getBlockByNumber(block-tag, full-tx?) -> Promise<decoded block or
  nil>. `block-tag` is a hex quantity string (\"0xac4938\") or one of
  \"latest\"/\"earliest\"/\"pending\"/\"safe\"/\"finalized\". Cached
  forever when `block-tag` is concrete — see namespace docstring."
  [client block-tag full-tx?]
  (let [cacheable? (concrete-block-tag? block-tag)
        coll [:kotobase.ethereum/blocks-by-number (:cache-scope client)]
        k (str block-tag ":" (boolean full-tx?))
        cached (and cacheable? (cache-get client coll k))]
    (if cached
      (js/Promise.resolve cached)
      (.then (call-decoded! client "eth_getBlockByNumber" [block-tag (boolean full-tx?)])
             (fn [decoded]
               (when (and cacheable? decoded)
                 (cache-put! client coll k decoded)
                 (cache-put! client [:kotobase.ethereum/blocks-by-hash (:cache-scope client)]
                             (str (:hash decoded) ":" (boolean full-tx?)) decoded))
               decoded)))))

(defn get-block-by-hash!
  "eth_getBlockByHash(block-hash, full-tx?) -> Promise<decoded block or
  nil>. A block hash is always concrete (there is no mutable-tag form for
  this method), so results are always cached forever — same caveat as
  `get-block-by-number!` about very-recent blocks."
  [client block-hash full-tx?]
  (let [coll [:kotobase.ethereum/blocks-by-hash (:cache-scope client)]
        k (str block-hash ":" (boolean full-tx?))
        cached (cache-get client coll k)]
    (if cached
      (js/Promise.resolve cached)
      (.then (call-decoded! client "eth_getBlockByHash" [block-hash (boolean full-tx?)])
             (fn [decoded]
               (when decoded
                 (cache-put! client coll k decoded)
                 (cache-put! client [:kotobase.ethereum/blocks-by-number (:cache-scope client)]
                             (str (get decoded :number) ":" (boolean full-tx?)) decoded))
               decoded)))))

(defn get-transaction-by-hash!
  "eth_getTransactionByHash(tx-hash) -> Promise<decoded tx or nil>. Cached
  only once mined (decoded result has a non-nil :block-hash); a pending
  tx is never cached."
  [client tx-hash]
  (let [coll [:kotobase.ethereum/transactions (:cache-scope client)]
        cached (cache-get client coll tx-hash)]
    (if cached
      (js/Promise.resolve cached)
      (.then (call-decoded! client "eth_getTransactionByHash" [tx-hash])
             (fn [decoded]
               (when (and decoded (:block-hash decoded))
                 (cache-put! client coll tx-hash decoded))
               decoded)))))

(defn get-balance!
  "eth_getBalance(address, block-tag) -> Promise<decimal-string wei
  amount>. Never cached — see namespace docstring."
  [client address block-tag]
  (call-decoded! client "eth_getBalance" [address (or block-tag "latest")]))

(defn call-contract!
  "eth_call(call-object, block-tag) -> Promise<raw hex return data>.

  READ-ONLY SIMULATION ONLY: this executes the call against node state
  without creating a transaction on chain — it never broadcasts, never
  spends gas from a real signer, and this repo has no code path that
  could turn a call-object into a signed/sent transaction. `call-object`
  is a plain map with JSON-RPC's own string field names, e.g.
  {\"to\" \"0x...\" \"data\" \"0x...\"} (optionally \"from\"/\"gas\"/
  \"gasPrice\"/\"value\") — passed straight through as JSON-RPC params.
  Never cached — see namespace docstring."
  [client call-object block-tag]
  (call-decoded! client "eth_call" [call-object (or block-tag "latest")]))

(defn- concrete-log-range? [filter]
  (and (concrete-block-tag? (get filter "fromBlock"))
       (concrete-block-tag? (get filter "toBlock"))))

(defn- log-cache-key [filter]
  (str (get filter "address") "|" (get filter "fromBlock") "|"
       (get filter "toBlock") "|" (json/encode (get filter "topics"))))

(defn get-logs!
  "eth_getLogs(filter) -> Promise<vector of decoded logs>. `filter` is a
  plain map with JSON-RPC's own string field names (\"address\"/
  \"fromBlock\"/\"toBlock\"/\"topics\"), passed straight through as
  JSON-RPC params. Cached forever only when both \"fromBlock\" and
  \"toBlock\" are concrete (not a mutable tag) — see namespace docstring."
  [client filter]
  (let [cacheable? (concrete-log-range? filter)
        coll [:kotobase.ethereum/logs (:cache-scope client)]
        k (log-cache-key filter)
        cached (and cacheable? (cache-get client coll k))]
    (if cached
      (js/Promise.resolve cached)
      (.then (call-decoded! client "eth_getLogs" [filter])
             (fn [decoded]
               (when cacheable? (cache-put! client coll k decoded))
               decoded)))))
