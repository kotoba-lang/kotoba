(ns chain.observer.substrate
  (:require [chain.observer.contract :as contract]
            [chain.observer.protocol :as observer]))

(defrecord SubstrateAdapter [expected-chain-name expected-genesis-hash
                             trust-level]
  observer/Adapter
  (request-plan [_]
    [{:role :chain-name :method "system_chain" :params []}
     {:role :health :method "system_health" :params []}
     {:role :genesis :method "chain_getBlockHash" :params [0]}
     {:role :best-header :method "chain_getHeader" :params []}
     {:role :finalized-hash :method "chain_getFinalizedHead" :params []}
     {:role :finalized-header :method "chain_getHeader"
      :params [:chain.observer/finalized-hash]}])
  (normalize [_ responses]
    (let [chain-name (:chain-name responses)
          genesis (:genesis responses)
          header->tip
          (fn [header hash finality]
            {:height (long (contract/hex-quantity (:number header)))
             :hash (or hash (:hash header)) :finality finality})]
      (contract/assert-expected!
       "name" expected-chain-name chain-name
       :chain.observer/network-mismatch)
      (contract/assert-expected!
       "genesis" expected-genesis-hash genesis
       :chain.observer/genesis-mismatch)
      (contract/validate-snapshot
       {:schema contract/schema :family :substrate
        :chain-id (str "polkadot:" genesis)
        :identity {:chain-name chain-name :genesis-hash genesis}
        :health {:status (if (:shouldHavePeers (:health responses))
                           (if (pos? (:peers (:health responses)))
                             :ok :degraded)
                           :ok)
                 :peers (:peers (:health responses))}
        :sync {:syncing? (true? (:isSyncing (:health responses)))}
        :tip (header->tip (:best-header responses) nil :best)
        :finalized-tip
        (header->tip (:finalized-header responses)
                     (:finalized-hash responses) :finalized)
        :capabilities #{:chain/identity :chain/health :chain/tip
                        :chain/finalized-tip :account/read}
        :trust {:level (or trust-level :remote-rpc)}}))))

(defn adapter [configuration]
  (map->SubstrateAdapter configuration))
