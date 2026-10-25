(ns bitcoin.consensus.sqlite-crash-worker
  "Subprocess worker used to terminate a live SQLite consensus transition."
  (:require [bitcoin.consensus.sqlite-utxo :as sqlite]
            [bitcoin.consensus.utxo :as utxo]))

(def txid-a (vec (repeat 32 1)))
(def txid-b (vec (repeat 32 2)))
(def coin-a {:value 5000 :script-pubkey [0x51]
             :height 1 :coinbase? false})
(def coin-b {:value 3000 :script-pubkey [0x00 0x14 1 2 3]
             :height 2 :coinbase? true})

(defn -main [path fault-name pending-hash]
  (let [backend (sqlite/open {:path path :network :regtest})
        fault (keyword fault-name)]
    (sqlite/call-with-fault-injector!
     (fn [point]
       (when (= fault point)
         (.halt (Runtime/getRuntime) 91)))
     (case (namespace fault)
       "commit-block"
       #(sqlite/commit-block!
         (-> (sqlite/begin backend)
             (utxo/-coin-assoc [txid-a 0] coin-a))
         {:block-hash "old" :parent-hash nil
          :height 0 :previous-height -1
          :undo {:height -1 :spent {}
                 :created #{[txid-a 0]}}})

       "transition"
       #(sqlite/commit-transition!
         (-> (sqlite/begin backend)
             (utxo/-coin-dissoc [txid-a 0])
             (utxo/-coin-assoc [txid-b 0] coin-b))
         {:expected-tip "old" :expected-height 0
          :new-tip "next" :new-height 1
          :detach []
          :attach
          [{:block-hash "next" :parent-hash "old"
            :height 1 :previous-height 0
            :undo {:height 0
                   :spent {[txid-a 0] coin-a}
                   :created #{[txid-b 0]}}}]
          :host-state-bytes (.getBytes "new-host")
          :pending-delete [pending-hash]})

       "host-update"
       #(sqlite/save-host-headers-and-pending!
         backend "old" 0 (.getBytes "new-host") []
         {:delete [pending-hash]})

       (throw (ex-info "Unknown crash operation." {:fault fault}))))))
