(ns chain.observer.evm
  (:require [chain.observer.contract :as contract]
            [chain.observer.protocol :as observer]))

(defrecord EvmAdapter [expected-chain-id expected-genesis-hash trust-level]
  observer/Adapter
  (request-plan [_]
    [{:role :chain-id :method "eth_chainId" :params []}
     {:role :syncing :method "eth_syncing" :params []}
     {:role :genesis :method "eth_getBlockByNumber" :params ["0x0" false]}
     {:role :latest :method "eth_getBlockByNumber" :params ["latest" false]}
     {:role :safe :method "eth_getBlockByNumber" :params ["safe" false]}
     {:role :finalized :method "eth_getBlockByNumber"
      :params ["finalized" false]}
     {:role :peers :method "net_peerCount" :params []}])
  (normalize [_ responses]
    (let [chain-id (long (contract/hex-quantity (:chain-id responses)))
          genesis-hash (get-in responses [:genesis :hash])
          block->tip
          (fn [block finality]
            (when block
              {:height (long (contract/hex-quantity (:number block)))
               :hash (:hash block) :finality finality}))]
      (contract/assert-expected!
       "id" expected-chain-id chain-id :chain.observer/network-mismatch)
      (contract/assert-expected!
       "genesis" expected-genesis-hash genesis-hash
       :chain.observer/genesis-mismatch)
      (contract/validate-snapshot
       {:schema contract/schema :family :evm
        :chain-id (str "eip155:" chain-id)
        :identity {:chain-id chain-id :genesis-hash genesis-hash}
        :health {:status :ok
                 :peers (long (contract/hex-quantity (:peers responses)))}
        :sync {:syncing? (not (false? (:syncing responses)))
               :detail (:syncing responses)}
        :tip (block->tip (:latest responses) :latest)
        :safe-tip (block->tip (:safe responses) :safe)
        :finalized-tip (block->tip (:finalized responses) :finalized)
        :capabilities #{:chain/identity :chain/health :chain/tip
                        :chain/finalized-tip :account/read :history/read}
        :trust {:level (or trust-level :remote-rpc)}}))))

(defn adapter [configuration]
  (map->EvmAdapter configuration))
