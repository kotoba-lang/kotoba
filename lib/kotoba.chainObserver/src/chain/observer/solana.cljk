(ns chain.observer.solana
  (:require [chain.observer.contract :as contract]
            [chain.observer.protocol :as observer]))

(defrecord SolanaAdapter [expected-genesis-hash cluster trust-level]
  observer/Adapter
  (request-plan [_]
    [{:role :genesis :method "getGenesisHash" :params []}
     {:role :health :method "getHealth" :params []}
     {:role :version :method "getVersion" :params []}
     {:role :confirmed-slot :method "getSlot"
      :params [{:commitment "confirmed"}]}
     {:role :finalized-slot :method "getSlot"
      :params [{:commitment "finalized"}]}])
  (normalize [_ responses]
    (let [genesis (:genesis responses)
          cluster-name (or cluster genesis)]
      (contract/assert-expected!
       "genesis" expected-genesis-hash genesis
       :chain.observer/genesis-mismatch)
      (contract/validate-snapshot
       {:schema contract/schema :family :solana
        :chain-id (str "solana:" cluster-name)
        :identity {:genesis-hash genesis :version (:version responses)}
        :health {:status (if (= "ok" (:health responses)) :ok :degraded)}
        :sync {:syncing? (> (- (:confirmed-slot responses)
                              (:finalized-slot responses))
                           256)
               :confirmed-slot (:confirmed-slot responses)
               :finalized-slot (:finalized-slot responses)}
        :tip {:height (:confirmed-slot responses) :finality :confirmed}
        :finalized-tip {:height (:finalized-slot responses)
                        :finality :finalized}
        :capabilities #{:chain/identity :chain/health :chain/tip
                        :chain/finalized-tip :account/read :history/read}
        :trust {:level (or trust-level :remote-rpc)}}))))

(defn adapter [configuration]
  (map->SolanaAdapter configuration))
