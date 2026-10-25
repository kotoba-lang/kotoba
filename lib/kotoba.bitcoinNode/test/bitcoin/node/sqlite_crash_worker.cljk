(ns bitcoin.node.sqlite-crash-worker
  "Subprocess worker that hard-stops a live node-owned SQLite transition."
  (:require [bitcoin.consensus.sqlite-utxo :as sqlite]
            [bitcoin.node.consensus-test :as fixture]
            [bitcoin.node.disk-consensus :as disk]))

(defn -main [path fault-name raw-block-hex]
  (let [node (disk/open {:path path :network :regtest})
        fault (keyword fault-name)
        raw-block (fixture/hex->bytes raw-block-hex)]
    (sqlite/call-with-fault-injector!
     (fn [point]
       (when (= fault point)
         (.halt (Runtime/getRuntime) 91)))
     #(disk/accept-block! node raw-block 2000000000))
    (throw
     (ex-info "Requested SQLite fault point was not reached."
              {:type :bitcoin.node/crash-fault-not-reached
               :fault fault}))))
