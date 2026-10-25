(ns chain.observer
  "Root assembly for the multi-chain observer.

  Consumers require `chain.observer` and call `adapter` + `observer`.
  `adapter` dispatches on `:chain-kind` (default :evm — the only chain
  kind hyakka's chain corpus currently observes) and delegates to the
  chain-specific adapter namespace. `observer` is
  `chain.observer.protocol/observer`."
  (:require [chain.observer.evm :as evm]
            [chain.observer.protocol :as protocol]))

(defn adapter [{:keys [chain-kind] :as configuration}]
  (case (or chain-kind :evm)
    :evm (evm/adapter configuration)))

(def observer protocol/observer)
