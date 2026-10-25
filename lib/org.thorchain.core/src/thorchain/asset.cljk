(ns thorchain.asset
  "THORChain asset notation: `CHAIN.SYMBOL` / `CHAIN.SYMBOL-CONTRACT`, plus the
  synth (`/`) and trade-account (`~`) variants. Pure `.cljc`, no dependencies.

  Asset notation is load-bearing, not cosmetic: it is the only thing in a swap
  memo that says WHICH asset the user gets. `ETH.USDC-0X…` and `AVAX.USDC-0X…`
  differ by one field and are different tokens on different chains, so this
  namespace parses and re-renders rather than doing string surgery at call
  sites."
  (:require [kotoba.lang.text :as str]))

;; Native gas assets of chains THORChain supports for BTC<->ETH-class flows.
;; Not an exhaustive registry — deliberately: a hard-coded \"supported assets\"
;; list goes stale silently as pools are added and churned. Ask the node
;; (`/thorchain/pools`) for what is actually tradeable right now; this map only
;; names the handful of gas assets whose spelling is worth pinning.
(def gas-assets
  {:btc  "BTC.BTC"
   :eth  "ETH.ETH"
   :bch  "BCH.BCH"
   :ltc  "LTC.LTC"
   :doge "DOGE.DOGE"
   :avax "AVAX.AVAX"
   :bsc  "BSC.BNB"
   :atom "GAIA.ATOM"
   :rune "THOR.RUNE"})

(def ^:private separators
  {\. :layer1     ; ETH.ETH        — the real asset on its native chain
   \/ :synth      ; ETH/ETH        — a synthetic backed by the pool
   \~ :trade})    ; ETH~ETH        — a trade-account balance

(defn parse
  "\"ETH.USDC-0X A0B8…\" -> {:chain \"ETH\" :symbol \"USDC\" :contract \"0XA0B8…\"
  :kind :layer1 :asset \"ETH.USDC-0XA0B8…\"}. Returns nil for anything that is
  not asset notation, so callers can distinguish \"absent\" from \"malformed\"."
  [s]
  (when (string? s)
    (let [s (str/trim s)
          idx (first (keep-indexed (fn [i c] (when (separators c) i)) s))]
      (when (and idx (pos? idx) (< (inc idx) (count s)))
        (let [chain (str/upper (subs s 0 idx))
              kind (separators (nth s idx))
              rest-part (subs s (inc idx))
              [sym contract] (str/split rest-part #"-" 2)]
          {:chain chain
           :symbol (str/upper sym)
           :contract (some-> contract str/upper)
           :kind kind
           :asset (str chain (nth s idx) (str/upper rest-part))})))))

(defn format-asset
  "{:chain :symbol :contract :kind} -> asset notation string."
  [{:keys [chain symbol contract kind] :or {kind :layer1}}]
  (let [sep (case kind :layer1 "." :synth "/" :trade "~")]
    (str (str/upper chain) sep (str/upper symbol)
         (when (seq contract) (str "-" (str/upper contract))))))

(defn valid?
  "Is `s` parseable asset notation?"
  [s]
  (some? (parse s)))

(defn evm-chain?
  "Does this asset live on an EVM chain (so a swap out of it needs an ERC-20
  allowance / router call rather than a plain transfer)?"
  [asset]
  (contains? #{"ETH" "AVAX" "BSC" "BASE"} (:chain (parse asset))))

(defn token?
  "Is this a contract token rather than a chain's gas asset?"
  [asset]
  (some? (:contract (parse asset))))

(def verified-abbreviations
  "Single-token asset abbreviations THORNode ACTUALLY emits in the memos it
  returns, measured against a live node on 2026-07-26 by requesting a quote per
  asset and reading back `memo`:

    ETH.ETH   -> \"e\"        AVAX.AVAX -> \"a\"        DOGE.DOGE -> \"d\"
    BTC.BTC   -> \"b\"        THOR.RUNE -> \"r\"        BCH.BCH   -> \"c\"
                                                   LTC.LTC   -> \"l\"

  NOT measurable on 2026-07-26 and therefore ABSENT: `BSC.BNB` and `BASE.ETH`.
  Both chains were `halted: true` / `chain_trading_paused: true`, so a quote
  answers \"trading is halted\" and never reaches the point of emitting a memo.
  Omitted rather than guessed — re-measure when the halt lifts. (`SOL.SOL` was
  halted too, for the record.)

  Each Tier-2 address FORMAT was validated the same way: the network accepted a
  derived address as a destination for that chain. It rejects a malformed one
  (\"unable to parse address\"), which makes it a usable independent oracle — an
  early LTC attempt that reused Bitcoin's bech32 checksum was caught exactly that
  way.

  This table exists because a quote's memo is the thing that decides WHICH ASSET
  the user receives, and the node writes it in its own abbreviated dialect — so a
  verifier that only understands `CHAIN.SYMBOL` rejects every legitimate live
  memo. That was a real defect here until a live call exposed it.

  Only measured entries are listed. Other chains' shorthands are NOT guessed:
  `expand` returns nil for an unknown single token and the caller reports it
  loudly, because silently treating an unrecognized abbreviation as a match would
  mean accepting a memo that pays out a different asset. To extend it, request a
  quote for that asset against a node and read the abbreviation out of the memo —
  the same way these four were obtained.

  Contract tokens are abbreviated differently: the node drops the contract part
  entirely (`ETH.USDC-0XA0B8…EB48` -> `ETH.USDC`), which the chain+symbol
  comparison already tolerates without needing a table."
  {"e" "ETH.ETH"
   "b" "BTC.BTC"
   "r" "THOR.RUNE"
   "a" "AVAX.AVAX"
   "d" "DOGE.DOGE"
   "c" "BCH.BCH"
   "l" "LTC.LTC"})

(defn expand
  "Asset notation OR a verified single-token abbreviation -> a parsed asset map.
  Returns nil for an unrecognized single token — deliberately, so the caller
  fails closed rather than accepting an asset it cannot identify."
  [s]
  (or (parse s)
      (when-let [full (get verified-abbreviations (str/lower (str/trim (str s))))]
        (assoc (parse full) :abbreviated-from (str s)))))

(defn short-form
  "Shorten an asset for a memo: THORChain accepts abbreviated notation, and a
  Bitcoin memo must fit in an 80-byte OP_RETURN, so `ETH.USDC-0X A0B8…EB48` ->
  `ETH.USDC-EB48` (chain + symbol + last 4 of the contract) buys ~35 bytes.

  Returns the asset unchanged when it has no contract part."
  [asset]
  (if-let [{:keys [chain symbol contract kind]} (parse asset)]
    (if contract
      (format-asset {:chain chain :symbol symbol :kind kind
                     :contract (subs contract (max 0 (- (count contract) 4)))})
      (format-asset {:chain chain :symbol symbol :kind kind}))
    asset))
