(ns chain.observer.cosmos
  (:require [chain.observer.contract :as contract]
            [chain.observer.protocol :as observer]))

(defrecord CosmosAdapter [expected-chain-id trust-level]
  observer/Adapter
  (request-plan [_]
    [{:role :status :method "status" :params []}
     {:role :block :method "block" :params []}
     {:role :health :method "health" :params []}])
  (normalize [_ responses]
    (let [status (:status responses)
          sync-info (:sync_info status)
          header (get-in responses [:block :block :header])
          chain-id (or (:chain_id header)
                       (get-in status [:node_info :network]))
          height (parse-long (or (:height header)
                                 (:latest_block_height sync-info)))
          hash (or (get-in responses [:block :block_id :hash])
                   (:latest_block_hash sync-info))]
      (contract/assert-expected!
       "id" expected-chain-id chain-id :chain.observer/network-mismatch)
      (contract/validate-snapshot
       {:schema contract/schema :family :cosmos
        :chain-id (str "cosmos:" chain-id)
        :identity {:chain-id chain-id
                   :node-id (get-in status [:node_info :id])}
        :health {:status (if (nil? (:error (:health responses)))
                           :ok :degraded)}
        :sync {:syncing? (true? (:catching_up sync-info))}
        :tip {:height height :hash hash :finality :committed}
        :finalized-tip {:height height :hash hash :finality :committed}
        :capabilities #{:chain/identity :chain/health :chain/tip
                        :chain/finalized-tip :account/read :history/read}
        :trust {:level (or trust-level :remote-rpc)}}))))

(defn adapter [configuration]
  (map->CosmosAdapter configuration))
