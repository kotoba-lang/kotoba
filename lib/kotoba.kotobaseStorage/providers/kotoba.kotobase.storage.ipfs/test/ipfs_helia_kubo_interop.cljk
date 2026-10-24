(ns ipfs-helia-kubo-interop
  (:require [kotobase.storage.ipfs-helia :as helia-client]
            ["multiformats/cid" :refer [CID]]
            ["multiformats/hashes/sha2" :refer [sha256]]
            ["multiformats/codecs/raw" :as raw]
            ["node:child_process" :as child-process]))

(def failures (atom 0))
(defn expect [ok? message]
  (if ok? (println (str "ok  - " message))
      (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defn bytes= [a b]
  (and (= (.-byteLength a) (.-byteLength b))
       (every? true? (map = (array-seq a) (array-seq b)))))

(defn kubo-block-get [cid]
  (js/Promise.
   (fn [resolve reject]
     (child-process/execFile
      "ipfs" #js ["block" "get" cid]
      #js {:env js/process.env :encoding nil :timeout 30000}
      (fn [error stdout _stderr]
        (if error
          (reject error)
          (resolve (js/Uint8Array. stdout))))))))

(defn qualify-client [client kubo-cid kubo-bytes helia-bytes]
  (println (str "Helia peer: " (:peer-id client)))
  (-> ((:get-block client) kubo-cid)
      (.then (fn [bytes]
               (expect (bytes= kubo-bytes bytes)
                       "Helia retrieves a Kubo block over standard Bitswap")))
      (.then (fn [_] (.digest sha256 helia-bytes)))
      (.then (fn [digest]
               (let [cid (.toString (.createV1 CID (.-code raw) digest))]
                 (-> ((:put-block! client) cid helia-bytes)
                     (.then (fn [_]
                              ;; Kubo is already directly connected to this
                              ;; Helia peer, so its block request is answered
                              ;; by Helia's standard Bitswap service.
                              (-> (kubo-block-get cid)
                                  (.then (fn [fetched]
                                           (expect (bytes= helia-bytes fetched)
                                                   "Kubo retrieves a Helia block over standard Bitswap"))))))))))
      (.finally (fn [] ((:close! client))))))

(defn -main []
  (let [peer (aget js/process.env "KUBO_PEER")
        kubo-cid (aget js/process.env "KUBO_BLOCK_CID")
        kubo-bytes (js/Uint8Array. (.from js/Buffer "kubo-to-helia-standard-bitswap" "utf8"))
        helia-bytes (js/Uint8Array. (.from js/Buffer "helia-to-kubo-standard-bitswap" "utf8"))]
    (when-not (and peer kubo-cid)
      (throw (js/Error. "KUBO_PEER and KUBO_BLOCK_CID are required")))
    (-> (helia-client/open!
         {:peers [peer]
          :helia-options {:libp2p {:addresses {:listen ["/ip4/127.0.0.1/tcp/0"]}}}})
        (.then (fn [client]
                 (qualify-client client kubo-cid kubo-bytes helia-bytes)))
        (.catch (fn [error]
                  (js/console.error error)
                  (swap! failures inc)))
        (.then (fn [_]
                 (println (if (zero? @failures)
                            "ipfs-helia-kubo-interop: all green"
                            (str "ipfs-helia-kubo-interop: " @failures " FAILURE(S)")))
                 (.exit js/process (if (zero? @failures) 0 1)))))))

(-main)
