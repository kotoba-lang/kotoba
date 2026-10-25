(ns swap.chains
  "Chain and token metadata, so callers stop hand-constructing the `{:chain
  :chain-id :asset :symbol :decimals :address}` maps `swap.core/intent` wants.

  WHY A REGISTRY IS A SAFETY FEATURE AND NOT A CONVENIENCE: those maps carry a
  token's contract address and its decimals. A wrong address sends funds to a
  different token; a wrong `:decimals` mis-scales every amount by a power of ten.
  Both are silent. Hand-typing them per call site is the highest-risk thing a
  caller of this library does.

  EVERY VALUE HERE WAS VERIFIED FROM TWO INDEPENDENT SOURCES (2026-07-26):

  1. LI.FI's own token API (`/v1/tokens`) supplied the candidate addresses and
     decimals — the vendor we actually route through, not a memory of a docs page.
  2. Each address was then confirmed ON-CHAIN by calling `symbol()`, `decimals()`
     and `name()` through `erc20`'s own calldata and decoders against the deployed
     contract. 7/7 matched.

  That second step earned its keep immediately: **BSC's USDC has 18 decimals, not
  the 6 that USDC has on every other chain here.** Assuming 6 would have
  mis-scaled every BSC amount by 10^12 — the kind of error that produces a
  successful-looking transaction for a thousand times the intended value.

  THORChain halt state is deliberately NOT recorded here. It changes (BSC, BASE and
  SOL were all halted when this was written) and a stale flag is worse than none —
  read it at runtime from `thorchain.quote/parse-inbound-addresses` and
  `chain-sendable?`."
  (:require [kotoba.lang.text :as str]))

(def chains
  "Keyed by our own chain keyword. `:chain` is the code THORChain uses and the one
  `swap.core` compares on; `:chain-id` is the EVM chain id (absent for non-EVM).
  `:rails` records which rails can actually reach the chain."
  {;; ── EVM ──
   :ethereum
   {:chain "ETH" :chain-id 1 :evm? true
    :native {:symbol "ETH" :decimals 18 :asset "ETH.ETH"}
    :thorchain-gas-asset "ETH.ETH"
    :rails #{:aggregator :thorchain}
    :tokens {:usdc {:symbol "USDC" :decimals 6
                    :address "0xA0b86991c6218b36c1d19D4a2e9Eb0cE3606eB48"}}}

   :bsc
   {:chain "BSC" :chain-id 56 :evm? true
    :native {:symbol "BNB" :decimals 18 :asset "BSC.BNB"}
    :thorchain-gas-asset "BSC.BNB"
    :rails #{:aggregator :thorchain}
    ;; 18 decimals — NOT 6. Verified on-chain; see the ns docstring.
    :tokens {:usdc {:symbol "USDC" :decimals 18
                    :address "0x8AC76a51cc950d9822D68b83fE1Ad97B32Cd580d"}}}

   :avalanche
   {:chain "AVAX" :chain-id 43114 :evm? true
    :native {:symbol "AVAX" :decimals 18 :asset "AVAX.AVAX"}
    :thorchain-gas-asset "AVAX.AVAX"
    :rails #{:aggregator :thorchain}
    :tokens {:usdc {:symbol "USDC" :decimals 6
                    :address "0xB97EF9Ef8734C71904D8002F8b6Bc66Dd9c48a6E"}}}

   :base
   {:chain "BASE" :chain-id 8453 :evm? true
    :native {:symbol "ETH" :decimals 18 :asset "BASE.ETH"}
    :thorchain-gas-asset "BASE.ETH"
    :rails #{:aggregator :thorchain}
    :tokens {:usdc {:symbol "USDC" :decimals 6
                    :address "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"}}}

   ;; Reachable by the aggregator rail only — THORChain has no vaults for these.
   :polygon
   {:chain "POL" :chain-id 137 :evm? true
    :native {:symbol "POL" :decimals 18}
    :rails #{:aggregator}
    :tokens {:usdc {:symbol "USDC" :decimals 6
                    :address "0x3c499c542cEF5E3811e1192ce70d8cC03d5c3359"}}}

   :arbitrum
   {:chain "ARB" :chain-id 42161 :evm? true
    :native {:symbol "ETH" :decimals 18}
    :rails #{:aggregator}
    :tokens {:usdc {:symbol "USDC" :decimals 6
                    :address "0xaf88d065e77c8cC2239327C5EDb3A432268e5831"}}}

   :optimism
   {:chain "OP" :chain-id 10 :evm? true
    :native {:symbol "ETH" :decimals 18}
    :rails #{:aggregator}
    :tokens {:usdc {:symbol "USDC" :decimals 6
                    :address "0x0b2C639c533813f4Aa9D7837CAf62653d097Ff85"}}}

   ;; ── UTXO / Bitcoin family (native rail only; no contracts, so no tokens) ──
   ;; `:btc-network` is the key btc-crypto/networks uses, so a caller can derive a
   ;; receive address without a second lookup table.
   :bitcoin
   {:chain "BTC" :evm? false :btc-network :mainnet
    :native {:symbol "BTC" :decimals 8 :asset "BTC.BTC"}
    :thorchain-gas-asset "BTC.BTC"
    :rails #{:thorchain}}

   :litecoin
   {:chain "LTC" :evm? false :btc-network :litecoin
    :native {:symbol "LTC" :decimals 8 :asset "LTC.LTC"}
    :thorchain-gas-asset "LTC.LTC"
    :rails #{:thorchain}}

   :dogecoin
   {:chain "DOGE" :evm? false :btc-network :dogecoin
    :native {:symbol "DOGE" :decimals 8 :asset "DOGE.DOGE"}
    :thorchain-gas-asset "DOGE.DOGE"
    :rails #{:thorchain}}

   :bitcoin-cash
   {:chain "BCH" :evm? false :btc-network :bitcoin-cash
    ;; btc-crypto cannot SIGN for BCH (it needs SIGHASH_FORKID), so this chain can
    ;; be swapped INTO but not out of. Stated as data so a caller can check.
    :spendable? false
    :native {:symbol "BCH" :decimals 8 :asset "BCH.BCH"}
    :thorchain-gas-asset "BCH.BCH"
    :rails #{:thorchain}}})

(defn chain
  "Look up a chain, refusing an unknown one rather than returning nil and letting a
  nil `:decimals` silently mis-scale an amount downstream."
  [k]
  (or (get chains k)
      (throw (ex-info (str "swap: unknown chain " (pr-str k))
                      {:known (sort (keys chains))}))))

(defn native
  "The `swap.core/intent` side map for a chain's native asset.

    (native :bsc) ;=> {:chain \"BSC\" :chain-id 56 :symbol \"BNB\" :decimals 18
                  ;    :asset \"BSC.BNB\"}"
  [k]
  (let [c (chain k)
        n (:native c)]
    (cond-> {:chain (:chain c) :symbol (:symbol n) :decimals (:decimals n)}
      (:chain-id c) (assoc :chain-id (:chain-id c))
      (:asset n) (assoc :asset (:asset n)))))

(defn token
  "The `swap.core/intent` side map for a token on a chain. Throws when the chain has
  no such token registered — better than a nil address, which an aggregator would
  interpret as the native asset."
  [k token-key]
  (let [c (chain k)
        t (get-in c [:tokens token-key])]
    (when-not t
      (throw (ex-info (str "swap: no " (name token-key) " registered on " (name k))
                      {:chain k :token token-key
                       :available (sort (keys (:tokens c)))})))
    (cond-> {:chain (:chain c) :symbol (:symbol t) :decimals (:decimals t)
             :address (:address t)}
      (:chain-id c) (assoc :chain-id (:chain-id c))
      ;; THORChain names a token as CHAIN.SYMBOL-CONTRACT
      (:thorchain-gas-asset c)
      (assoc :asset (str (:chain c) "." (:symbol t) "-" (str/upper (:address t)))))))

(defn on-rail
  "Chain keys reachable by `rail` (`:aggregator` or `:thorchain`)."
  [rail]
  (sort (keep (fn [[k v]] (when (contains? (:rails v) rail) k)) chains)))

(defn spendable?
  "Can we sign a transaction FROM this chain? False for Bitcoin Cash, which needs
  SIGHASH_FORKID that btc-crypto does not implement — so BCH is swap-INTO only."
  [k]
  (not (false? (:spendable? (chain k)))))
