(ns chain.observer.lightning
  (:require [chain.observer.contract :as contract]
            [chain.observer.protocol :as observer]))

(defrecord LightningAdapter [expected-network trust-level]
  observer/Adapter
  (request-plan [_]
    [{:role :info :method "lnrpc.Lightning/GetInfo" :params []}])
  (normalize [_ responses]
    (let [info (:info responses)
          network (or (get-in info [:chains 0 :network]) (:network info))]
      (contract/assert-expected!
       "network" expected-network network :chain.observer/network-mismatch)
      (contract/validate-snapshot
       {:schema contract/schema :family :lightning
        :chain-id (str "lightning:" network)
        :identity {:network network
                   :identity-pubkey (:identity_pubkey info)
                   :alias (:alias info)}
        :health {:status (if (:synced_to_chain info) :ok :degraded)
                 :peers (:num_peers info)
                 :active-channels (:num_active_channels info)}
        :sync {:syncing? (not (and (:synced_to_chain info)
                                   (:synced_to_graph info)))
               :chain-synced? (true? (:synced_to_chain info))
               :graph-synced? (true? (:synced_to_graph info))}
        :tip {:height (:block_height info)
              :hash (:block_hash info) :finality :best}
        :finalized-tip nil
        :capabilities #{:chain/identity :chain/health :chain/tip}
        :trust {:level (or trust-level :local-rpc)
                :credential :readonly-macaroon}}))))

(defn adapter [configuration]
  (map->LightningAdapter configuration))
