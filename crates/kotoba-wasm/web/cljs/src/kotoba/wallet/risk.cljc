(ns kotoba.wallet.risk
  "Pure risk checks before any wallet signature.")

(def risk-rank
  {:risk.level/low 0
   :risk.level/medium 1
   :risk.level/high 2})

(defn max-risk [risks]
  (or (last (sort-by risk-rank risks)) :risk.level/low))

(defn pkh-chain-id [pkh]
  (when-let [[_ chain] (re-matches #"did:pkh:eip155:([0-9]+):0x[0-9a-fA-F]+" (or pkh ""))]
    #?(:clj (Long/parseLong chain) :cljs (js/parseInt chain 10))))

(defn assess [state intent]
  (let [account (get-in state [:accounts (:account-id intent)])
        policy (get-in state [:policies (:origin intent)])
        allowed-chains (set (:chains policy))
        spender (:spender intent)
        risks (cond-> []
                (not= (:chain-id intent) (:selected-chain-id state))
                (conj {:risk :risk/chain-not-selected
                       :level :risk.level/high})

                (not= (:chain-id intent) (pkh-chain-id (:pkh account)))
                (conj {:risk :risk/pkh-chain-mismatch
                       :level :risk.level/high})

                (and (seq allowed-chains) (not (contains? allowed-chains (:chain-id intent))))
                (conj {:risk :risk/origin-chain-not-allowed
                       :level :risk.level/high})

                (:unlimited-approval? intent)
                (conj {:risk :risk/unlimited-approval
                       :level (if (:allow-unlimited-approval? policy)
                                :risk.level/medium
                                :risk.level/high)})

                (and spender
                     (not= (:kind intent) :intent.kind/erc20-revoke-approval)
                     (not (contains? (set (:allowed-spenders policy)) spender)))
                (conj {:risk :risk/unknown-spender
                       :level :risk.level/high})

                (> (or (:slippage-bps intent) 0) (or (:max-slippage-bps policy) 100))
                (conj {:risk :risk/slippage-above-policy
                       :level :risk.level/medium})

                (and (:deadline-ms intent)
                     (:now-ms intent)
                     (> (:now-ms intent) (:deadline-ms intent)))
                (conj {:risk :risk/quote-expired
                       :level :risk.level/high})

                (seq (:quote-mismatch-fields intent))
                (conj {:risk :risk/quote-request-mismatch
                       :level :risk.level/high
                       :fields (:quote-mismatch-fields intent)})

                (:opaque? intent)
                (conj {:risk :risk/opaque-call
                       :level :risk.level/medium}))]
    {:level (max-risk (map :level risks))
     :risks risks}))
