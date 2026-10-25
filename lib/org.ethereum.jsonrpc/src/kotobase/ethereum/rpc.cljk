(ns kotobase.ethereum.rpc
  "Pure JSON-RPC 2.0 request/response shaping + decode logic for the
  Ethereum JSON-RPC API (ethereum.org/en/developers/docs/apis/json-rpc/),
  per ADR-2607172600 in com-junkawasaki/root.

  PERMANENT SAFETY BOUNDARY (not a v0.1-vs-later phasing question — read
  this before extending the whitelist below): this namespace, and every
  namespace in this repo, is a READ-ONLY OBSERVER of public Ethereum chain
  data. It never constructs, signs, or broadcasts a transaction; it never
  handles a private key; it has no wallet functionality. `eth-method-whitelist`
  below is the enforcement point — `build-request` and `decode-result` both
  consult it and throw on anything not listed, so an out-of-scope method
  name cannot reach a real node through this namespace's call sites even by
  accident. Do not add `eth_sendTransaction`, `eth_sendRawTransaction`,
  `eth_sign`, `eth_signTransaction`, `eth_accounts`, any `personal_*`
  method, or any other transaction-constructing/broadcasting/key-touching
  method to this whitelist — that is out of scope for this repo,
  permanently.

  No HTTP/socket concepts live here — `kotobase.ethereum.client` (.cljs
  only) is the transport that actually sends these requests over the
  wire and feeds results back through this namespace's decode fns."
  (:require [kotoba.lang.text :as str]))

;; ------------------------------------------------------------- whitelist

(def eth-method-whitelist
  "The exhaustive set of JSON-RPC methods this repo will ever construct a
  request for. Every entry is read-only: `eth_call` executes a read-only
  contract-call SIMULATION against current or historical state — it does
  NOT execute any state-changing operation and never broadcasts anything."
  #{"eth_blockNumber"
    "eth_getBlockByNumber"
    "eth_getBlockByHash"
    "eth_getTransactionByHash"
    "eth_getBalance"
    "eth_call"
    "eth_getLogs"
    "eth_chainId"})

(defn allowed-method?
  "Is `method` on the permanent read-only whitelist? The single source of
  truth every request-building/decoding entry point below consults."
  [method]
  (contains? eth-method-whitelist method))

(defn- disallowed-method-ex [method]
  (ex-info (str "kotobase.ethereum.rpc: method not on the read-only "
                "whitelist (permanent scope boundary, ADR-2607172600): "
                method)
           {:type ::disallowed-method :method method
            :allowed eth-method-whitelist}))

;; -------------------------------------------------------------- envelope

(defn build-request
  "Build a JSON-RPC 2.0 request map for `method`/`params` (a seqable of
  positional params, per the Ethereum JSON-RPC spec) and integer `id`.
  {\"jsonrpc\" \"2.0\" \"method\" method \"params\" [...] \"id\" id}

  Throws ex-info (`:type ::disallowed-method`) if `method` is not on
  `eth-method-whitelist` — this IS the enforcement, not just a doc note."
  [method params id]
  (when-not (allowed-method? method)
    (throw (disallowed-method-ex method)))
  {"jsonrpc" "2.0" "method" method "params" (vec params) "id" id})

(defn parse-response
  "Raw JSON-RPC response value (a map with string keys, e.g. as produced
  by `kotobase.protocols.json/parse`) -> a normalized result map:
    success: {:ok? true  :id id :result <still-hex-encoded raw result>}
    failure: {:ok? false :id id :error {:code :message :data}}"
  [resp]
  (let [id (get resp "id")]
    (if (contains? resp "error")
      (let [e (get resp "error")]
        {:ok? false :id id
         :error {:code (get e "code") :message (get e "message") :data (get e "data")}})
      {:ok? true :id id :result (get resp "result")})))

;; ------------------------------------------------------------- hex decode

(defn hex-string?
  [s]
  (boolean (and (string? s) (re-matches #"0[xX][0-9a-fA-F]*" s))))

(defn hex->long
  "Decode a JSON-RPC QUANTITY hex string (\"0x1b4\") into a plain integer.
  Used for fields expected to stay well inside the platform's safe-integer
  range for the foreseeable future (block number, timestamp, gas, index,
  chain id, ...) — see `hex->decimal-string` for fields that can genuinely
  need full 256-bit precision (wei amounts)."
  [s]
  (when s
    (when-not (hex-string? s)
      (throw (ex-info (str "kotobase.ethereum.rpc: not a hex quantity: " (pr-str s))
                       {:type ::bad-hex :value s})))
    (let [digits (subs s 2)]
      (if (str/blank? digits)
        0
        #?(:clj (long (BigInteger. digits 16))
           :cljs (js/Number (str "0x" digits)))))))

(defn hex->decimal-string
  "Decode a JSON-RPC QUANTITY hex string into its exact decimal-string
  representation, using arbitrary-precision integer math on both
  platforms — avoids the float64/int64 precision loss `hex->long` accepts
  for smaller fields. Used for wei amounts (balance, value, gasPrice,
  gas fee fields) which can exceed 2^53."
  [s]
  (when s
    (when-not (hex-string? s)
      (throw (ex-info (str "kotobase.ethereum.rpc: not a hex quantity: " (pr-str s))
                       {:type ::bad-hex :value s})))
    (let [digits (subs s 2)]
      (if (str/blank? digits)
        "0"
        #?(:clj (str (BigInteger. digits 16))
           :cljs (str (js/BigInt (str "0x" digits))))))))

;; -------------------------------------------------------- entity decoders
;;
;; Field classification below (QUANTITY -> integer/decimal-string vs DATA
;; -> raw hex passthrough) follows the Ethereum JSON-RPC spec's own
;; QUANTITY/DATA distinction. DATA fields (hashes, addresses, bloom
;; filters, raw calldata/input, signature r/s/v) are opaque byte strings,
;; not numbers to decode — they stay as hex strings. Every decoder is
;; `nil`-safe (nil in -> nil out) so callers can thread a possibly-absent
;; JSON-RPC `result` straight through.

(defn decode-withdrawal
  "A post-Shapella block withdrawal entry."
  [w]
  (when w
    {:index (hex->long (get w "index"))
     :validator-index (hex->long (get w "validatorIndex"))
     :address (get w "address")
     :amount-gwei (hex->long (get w "amount"))}))

(defn decode-transaction
  "A transaction object as embedded in a full block (`eth_getBlockByNumber`/
  `eth_getBlockByHash` with the full-transaction-objects flag) or as
  returned directly by `eth_getTransactionByHash`. `nil` `result` (e.g. an
  unknown/not-yet-mined tx hash) decodes to `nil`."
  [tx]
  (when tx
    {:hash (get tx "hash")
     :block-hash (get tx "blockHash")
     :block-number (some-> (get tx "blockNumber") hex->long)
     :transaction-index (some-> (get tx "transactionIndex") hex->long)
     :from (get tx "from")
     :to (get tx "to")
     :nonce (some-> (get tx "nonce") hex->long)
     :value (some-> (get tx "value") hex->decimal-string)
     :gas (some-> (get tx "gas") hex->long)
     :gas-price (some-> (get tx "gasPrice") hex->decimal-string)
     :max-fee-per-gas (some-> (get tx "maxFeePerGas") hex->decimal-string)
     :max-priority-fee-per-gas (some-> (get tx "maxPriorityFeePerGas") hex->decimal-string)
     :max-fee-per-blob-gas (some-> (get tx "maxFeePerBlobGas") hex->decimal-string)
     :input (get tx "input")
     :type (some-> (get tx "type") hex->long)
     :chain-id (some-> (get tx "chainId") hex->long)
     :access-list (get tx "accessList")
     :blob-versioned-hashes (get tx "blobVersionedHashes")
     :v (get tx "v")
     :r (get tx "r")
     :s (get tx "s")
     :y-parity (some-> (get tx "yParity") hex->long)}))

(defn decode-log
  [l]
  (when l
    {:address (get l "address")
     :topics (get l "topics")
     :data (get l "data")
     :block-number (some-> (get l "blockNumber") hex->long)
     :block-hash (get l "blockHash")
     :transaction-hash (get l "transactionHash")
     :transaction-index (some-> (get l "transactionIndex") hex->long)
     :log-index (some-> (get l "logIndex") hex->long)
     :removed (get l "removed")}))

(defn decode-logs
  [ls]
  (when ls
    (mapv decode-log ls)))

(defn decode-block
  "`eth_getBlockByNumber`/`eth_getBlockByHash` result. `:transactions` is
  decoded per-entry only when the node returned full transaction objects
  (the full-tx-objects request flag was true); when the node returned bare
  tx-hash strings (flag false), those pass through unchanged."
  [b]
  (when b
    {:number (some-> (get b "number") hex->long)
     :hash (get b "hash")
     :parent-hash (get b "parentHash")
     :nonce (get b "nonce")
     :sha3-uncles (get b "sha3Uncles")
     :logs-bloom (get b "logsBloom")
     :transactions-root (get b "transactionsRoot")
     :state-root (get b "stateRoot")
     :receipts-root (get b "receiptsRoot")
     :miner (get b "miner")
     :difficulty (some-> (get b "difficulty") hex->decimal-string)
     :total-difficulty (some-> (get b "totalDifficulty") hex->decimal-string)
     :extra-data (get b "extraData")
     :size (some-> (get b "size") hex->long)
     :gas-limit (some-> (get b "gasLimit") hex->long)
     :gas-used (some-> (get b "gasUsed") hex->long)
     :timestamp (some-> (get b "timestamp") hex->long)
     :base-fee-per-gas (some-> (get b "baseFeePerGas") hex->decimal-string)
     :mix-hash (get b "mixHash")
     :blob-gas-used (some-> (get b "blobGasUsed") hex->long)
     :excess-blob-gas (some-> (get b "excessBlobGas") hex->long)
     :parent-beacon-block-root (get b "parentBeaconBlockRoot")
     :withdrawals-root (get b "withdrawalsRoot")
     :requests-hash (get b "requestsHash")
     :uncles (get b "uncles")
     :withdrawals (some->> (get b "withdrawals") (mapv decode-withdrawal))
     :transactions (some->> (get b "transactions")
                             (mapv (fn [t] (if (map? t) (decode-transaction t) t))))}))

;; ------------------------------------------------------- method dispatch

(defn decode-result
  "Given a whitelisted `method` name and its still-hex-encoded raw
  `:result` value (from `parse-response`'s success branch), decode into
  clean EDN via the method-appropriate decoder above.

  `eth_call`'s result is ABI-encoded contract-return bytes; decoding those
  requires the target contract's ABI, which this repo does not implement
  (out of scope — this repo is a JSON-RPC transport, not an ABI/contract
  library) so it passes through as the raw hex string.

  Throws ex-info (`:type ::disallowed-method`) if `method` is not on the
  whitelist — same enforcement point as `build-request`, so a caller can't
  decode a made-up out-of-scope method's result through this fn either."
  [method result]
  (when-not (allowed-method? method)
    (throw (disallowed-method-ex method)))
  (case method
    "eth_blockNumber" (hex->long result)
    "eth_chainId" (hex->long result)
    "eth_getBalance" (hex->decimal-string result)
    "eth_getBlockByNumber" (decode-block result)
    "eth_getBlockByHash" (decode-block result)
    "eth_getTransactionByHash" (decode-transaction result)
    "eth_getLogs" (decode-logs result)
    "eth_call" result))
