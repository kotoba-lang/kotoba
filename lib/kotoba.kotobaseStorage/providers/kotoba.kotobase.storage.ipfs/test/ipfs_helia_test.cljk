(ns ipfs-helia-test
  (:require [kotobase.storage.ipfs :as ipfs]
            [kotobase.storage.ipfs-helia :as helia-client]
            [kotobase.storage.core :as storage]
            ["multiformats/cid" :refer [CID]]))

(def failures (atom 0))
(defn expect [ok? message]
  (if ok? (println (str "ok  - " message))
      (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(def test-cid "bafkreibm6jg3ux5quy7hfwi5vbdxilbtjtu3lgubxypyi2y5muqr6bts7i")

(defn async-block [chunks]
  (let [remaining (atom chunks)]
    #js {:next (fn []
                 (if-let [chunk (first @remaining)]
                   (do (swap! remaining next)
                       (js/Promise.resolve #js {:done false :value chunk}))
                   (js/Promise.resolve #js {:done true}))) }))

(defn fake-node []
  (let [stored (atom nil)
        stopped (atom false)
        dialed (atom [])]
    {:stored stored :stopped stopped :dialed dialed
     :node #js {:blockstore
                #js {:put (fn [cid bytes]
                            (reset! stored bytes)
                            (js/Promise.resolve cid))
                     :get (fn [_]
                            (async-block [(js/Uint8Array. #js [1 2])
                                          (js/Uint8Array. #js [3 4])]))}
                :libp2p #js {:peerId #js {:toString (fn [] "12D3KooWtest")}
                              :dial (fn [address]
                                      (swap! dialed conj (.toString address))
                                      (js/Promise.resolve true))}
                :start (fn [] (js/Promise.resolve nil))
                :stop (fn [] (reset! stopped true) (js/Promise.resolve nil))}}))

(defn -main []
  (let [{:keys [node stored stopped dialed]} (fake-node)
        peer "/ip4/127.0.0.1/tcp/4001/p2p/12D3KooWQkcQvQY6x9P8QBH1vJ1DR8V8MCqEMNSfQirZfvqAGrQ7"]
    (-> (helia-client/open! {:helia node :peers [peer]})
        (.then (fn [client]
                 (expect (= "12D3KooWtest" (:peer-id client)) "peer identity is exposed")
                 (expect (= [peer] @dialed) "configured peers are dialed as multiaddrs")
                 (let [backend (ipfs/open {:client client})]
                   (storage/validate-block-store! backend)
                   (expect (storage/block-store? backend) "Helia client composes with neutral storage")
                   (-> ((:put-block! client) test-cid (js/Uint8Array. #js [1 2 3 4]))
                       (.then (fn [cid]
                                (expect (= test-cid cid) "put preserves the caller CID")
                                (expect (= [1 2 3 4] (vec (array-seq @stored))) "put forwards bytes")))
                       (.then (fn [_] ((:get-block client) test-cid)))
                       (.then (fn [bytes]
                                (expect (= [1 2 3 4] (vec (array-seq bytes)))
                                        "async block chunks are drained and concatenated")))
                       (.then (fn [_] ((:close! client))))
                       (.then (fn [_] (expect @stopped "close stops the embedded node")))))))
        (.catch (fn [error]
                  (js/console.error error)
                  (swap! failures inc)))
        (.then (fn [_]
                 (println (if (zero? @failures)
                            "ipfs-helia-test: all green"
                            (str "ipfs-helia-test: " @failures " FAILURE(S)")))
                 (.exit js/process (if (zero? @failures) 0 1)))))))

(-main)
