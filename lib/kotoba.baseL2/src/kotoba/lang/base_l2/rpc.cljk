(ns kotoba.lang.base-l2.rpc
  "Minimal JSON-RPC-over-HTTP client for the narrow slice of Ethereum
  `eth_*` methods `l2.ts`'s `AnchorClient` actually calls (via viem's
  `PublicClient`/`WalletClient`, transported over `http()`): `eth_call`,
  `eth_sendRawTransaction`, `eth_getTransactionReceipt`,
  `eth_getTransactionCount`, `eth_gasPrice`, `eth_chainId`,
  `eth_estimateGas`. Not a general Ethereum JSON-RPC client -- just these
  seven methods.

  PURE core over an injected `ITransport`, matching the design
  established by `kotoba-lang/ipfs` (`kotoba.lang.ipfs/IHttp`) in this
  same porting wave: this namespace builds every JSON-RPC request
  envelope and parses every response; the host only moves bytes over the
  wire. The library itself performs ZERO network I/O and carries ZERO
  HTTP-client/vendor dep -- `babashka.http-client` (or any other HTTP
  lib) is the HOST's dependency for a reference adapter, not this pure
  core's. JSON is via `json.data-json` (JVM) / `js/JSON` (CLJS) --
  data-only, policy-fine (same split `kotoba.lang.ipfs` makes) -- behind
  the `write-json`/`read-json-kw` reader-conditional shims below.

  Unlike `kotoba.lang.ipfs/IHttp` (3 methods: `-get`/`-post`/`-post-file`,
  because Kubo's REST-ish HTTP API needs those distinct shapes),
  JSON-RPC-over-HTTP has exactly ONE request shape -- POST a JSON body to
  a single endpoint, get a JSON body back -- so `ITransport` below is a
  single method.

  PORTABLE `.cljc` (JVM + CLJS): `rpc-call` and all seven `eth_*` wrappers
  below are platform-uniform pure request-building/response-parsing over
  the injected, synchronous `ITransport` (its own docstring never promised
  a `js/Promise` return the way `kotoba.lang.ipfs/IHttp` explicitly does,
  so there's no sync/async split to carry here).

  The ONE exception is `wait-for-transaction-receipt`: it blocks the
  calling thread between polls via `Thread/sleep`, which has no portable
  equivalent on a single-threaded JS runtime (browser or Node) without
  turning the whole call chain async (`js/setTimeout` + `js/Promise`
  recursion) -- out of scope for this pass, since `ITransport` isn't
  async either. It is therefore `#?(:clj ...)`-gated and simply doesn't
  exist under `:cljs`; a CLJS host should build its own async poll loop
  over `eth-get-transaction-receipt` (already portable) using
  `js/setTimeout`/`js/Promise`."
  (:require #?(:clj [json.data-json :as json])
            [kotoba.lang.text :as str]))

;; ─── capability seam -- host-injected transport ───────────────────────

(defprotocol ITransport
  "Host-injected HTTP transport. Core builds the JSON-RPC request body
  and parses the JSON-RPC response body; the host only moves bytes over
  the wire (e.g. a `babashka.http-client`-backed adapter on the JVM).
  `body` is always a JSON string (JSON-RPC 2.0's wire format is textual,
  never a binary blob), so there is no bytes<->string shim to carry
  here."
  (-post [this url body]
    "POST the JSON string `body` to `url`. => `{:status Int :body String}`."))

(defonce ^:private id-counter (atom 0))

;; ─── JSON (platform shims behind reader conditionals) ─────────────────

(defn- write-json [m]
  #?(:clj  (json/write-str m)
     :cljs (.stringify js/JSON (clj->js m))))

(defn- read-json-kw
  "Parse a JSON object string to a map with KEYWORD keys (uniform clj/cljs)."
  [s]
  #?(:clj  (json/read-str s :key-fn keyword)
     :cljs (js->clj (.parse js/JSON s) :keywordize-keys true)))

(defn rpc-call
  "POST a JSON-RPC 2.0 request `{:method method :params params}` to
  `rpc-url` via `transport` (an `ITransport`) and return the `:result`.
  Throws ex-info on a transport-level HTTP error or a JSON-RPC `:error`
  object."
  [transport rpc-url method params]
  (let [id (swap! id-counter inc)
        body (write-json {:jsonrpc "2.0" :id id :method method :params params})
        resp (-post transport rpc-url body)]
    (when-not (<= 200 (:status resp) 299)
      (throw (ex-info (str "[kotoba.lang.base-l2.rpc] HTTP " (:status resp) " calling " method)
                       {:status (:status resp) :body (:body resp) :method method})))
    (let [parsed (read-json-kw (:body resp))]
      (if-let [err (:error parsed)]
        (throw (ex-info (str "[kotoba.lang.base-l2.rpc] JSON-RPC error calling " method ": " (:message err))
                         {:error err :method method :params params}))
        (:result parsed)))))

(defn- hex->long [hex]
  (let [h (if (str/starts-with? hex "0x") (subs hex 2) hex)]
    #?(:clj  (Long/parseLong h 16)
       :cljs (js/parseInt h 16))))

(defn- ->long [x]
  (cond
    (string? x) (hex->long x)
    (number? x) #?(:clj (long x) :cljs x)
    :else (throw (ex-info "expected hex string or number" {:value x}))))

(defn ->hex
  "Coerce an integral value to its `0x…` JSON-RPC quantity encoding
  (minimal, no leading zeros, `0x0` for zero)."
  [v]
  #?(:clj
     (let [bi (biginteger v)]
       (if (zero? (.signum bi))
         "0x0"
         (str "0x" (.toString bi 16))))
     :cljs
     (let [bi (js/BigInt v)]
       (if (= bi (js/BigInt 0))
         "0x0"
         (str "0x" (.toString bi 16))))))

;; ─── the seven eth_* methods this SDK actually calls ──────────────────
;; Every method takes `transport` first (mirrors `kotoba.lang.ipfs`'s
;; `(pin-blob http api-url content)` convention).

(defn eth-call
  "`eth_call` against `to` with calldata `data` (a `0x…` hex string) at
  block tag `block` (default \"latest\"). Returns the `0x…` return data."
  ([transport rpc-url to data] (eth-call transport rpc-url to data "latest"))
  ([transport rpc-url to data block]
   (rpc-call transport rpc-url "eth_call" [{:to to :data data} block])))

(defn eth-send-raw-transaction
  "`eth_sendRawTransaction` with a `0x…` raw signed tx. Returns the `0x…`
  transaction hash."
  [transport rpc-url raw-tx]
  (rpc-call transport rpc-url "eth_sendRawTransaction" [raw-tx]))

(defn eth-get-transaction-receipt
  "`eth_getTransactionReceipt` for `tx-hash`. Returns nil until mined,
  else the receipt map (keywordized, e.g. `:status` `:blockNumber`)."
  [transport rpc-url tx-hash]
  (rpc-call transport rpc-url "eth_getTransactionReceipt" [tx-hash]))

(defn eth-get-transaction-count
  "`eth_getTransactionCount` (the nonce) for `address` at block tag
  `block` (default \"pending\", matching viem's default nonce source for
  a tx about to be sent). Returns a long."
  ([transport rpc-url address] (eth-get-transaction-count transport rpc-url address "pending"))
  ([transport rpc-url address block]
   (->long (rpc-call transport rpc-url "eth_getTransactionCount" [address block]))))

(defn eth-gas-price
  "`eth_gasPrice`. Returns a long (wei)."
  [transport rpc-url]
  (->long (rpc-call transport rpc-url "eth_gasPrice" [])))

(defn eth-chain-id
  "`eth_chainId`. Returns a long."
  [transport rpc-url]
  (->long (rpc-call transport rpc-url "eth_chainId" [])))

(defn eth-estimate-gas
  "`eth_estimateGas` for a prospective call/tx `{:from :to :data :value}`.
  Returns a long (gas units)."
  [transport rpc-url tx]
  (->long (rpc-call transport rpc-url "eth_estimateGas" [tx])))

;; ─── receipt polling -- JVM-only (blocking Thread/sleep, see ns docstring) ──

#?(:clj
   (defn wait-for-transaction-receipt
     "Poll `eth_getTransactionReceipt` for `tx-hash` every `interval-ms`
     (default 500) until it is non-nil or `timeout-ms` (default 60000)
     elapses. Mirrors viem's `waitForTransactionReceipt`. Throws ex-info on
     timeout.

     JVM-only (`Thread/sleep`-blocking): see the namespace docstring for
     why this one function isn't `:cljs`-portable while the rest of the
     namespace is."
     ([transport rpc-url tx-hash] (wait-for-transaction-receipt transport rpc-url tx-hash {}))
     ([transport rpc-url tx-hash {:keys [interval-ms timeout-ms] :or {interval-ms 500 timeout-ms 60000}}]
      (let [deadline (+ (System/currentTimeMillis) timeout-ms)]
        (loop []
          (if-let [receipt (eth-get-transaction-receipt transport rpc-url tx-hash)]
            receipt
            (if (> (System/currentTimeMillis) deadline)
              (throw (ex-info (str "[kotoba.lang.base-l2.rpc] timed out waiting for receipt: " tx-hash)
                               {:tx-hash tx-hash :timeout-ms timeout-ms}))
              (do (Thread/sleep ^long interval-ms)
                  (recur)))))))))
