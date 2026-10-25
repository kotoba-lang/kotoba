(ns ipfs-native-test
  "Qualification for `kotobase.storage.ipfs-native` -- the kubo-independent,
  no-daemon, no-npm-SDK peer-to-peer client. Uses REAL TCP sockets on
  distinct loopback ports (127.0.0.1), not a mock/fake transport: the two
  node handles below are exactly what a caller gets from `open`, wired to
  each other exactly the way two independent processes would be."
  (:require [kotobase.storage.core :as storage]
            [kotobase.storage.async-contract :as contract]
            [kotobase.storage.ipfs :as ipfs]
            [kotobase.storage.ipfs-native :as native]))

(def ^:private failures (atom 0))

(defn- expect [ok? message]
  (if ok?
    (println (str "ok  - " message))
    (do (js/console.error (str "FAIL: " message)) (swap! failures inc))))

(defrecord LinearRefs [heads]
  storage/IRefStore
  (-read-ref [_ name]
    (js/Promise.resolve (get @heads name)))
  (-compare-and-set-ref! [_ name expected next]
    (let [answer (atom nil)]
      (swap! heads
             (fn [state]
               (let [{current :cid version :version} (get state name)
                     version (or version 0)]
                 (if (= expected current)
                   (let [next-record {:cid next :version (inc version)}]
                     (reset! answer {:published? true :current next :version (:version next-record)})
                     (assoc state name next-record))
                   (do (reset! answer {:published? false :current current :version version})
                       state)))))
      (js/Promise.resolve @answer)))

  storage/IBackendCapabilities
  (-capabilities [_] #{:conditional-ref :linearizable-ref}))

(defn- bytes-of [& vs] (js/Uint8Array.from (clj->js (vec vs))))

(defn- test-local-round-trip []
  (let [node (native/open {:node-id "solo" :port 15801})
        cid "cid-local"
        b (bytes-of 1 2 3)]
    (-> ((:put-block! node) cid b)
        (.then (fn [stored] (expect (= cid stored) "put-block! resolves to the given cid")))
        (.then (fn [_] ((:get-block node) cid)))
        (.then (fn [got]
                 (expect (some? got) "get-block finds a block this node put itself, with no peers")
                 (expect (= (vec b) (vec got)) "the bytes round-trip byte-for-byte")))
        (.then (fn [_] ((:get-block node) "cid-never-put")))
        (.then (fn [got] (expect (nil? got) "get-block on an unknown cid, no peers, resolves to nil")))
        (.then (fn [_] ((:close! node)))))))

(defn- test-real-two-port-fetch []
  ;; Node A holds the block. Node B has never seen it, is configured with A
  ;; as its only peer, and must fetch it over a REAL TCP round trip -- two
  ;; separate `net.Server`s on two separate ports, two separate outbound
  ;; `net.createConnection`s (:block-want then :block-get), not a shared
  ;; in-memory structure.
  (let [a (native/open {:node-id "a" :port 15802})
        b (native/open {:node-id "b" :port 15803 :peers [{:id "a" :host "127.0.0.1" :port 15802}]})
        cid "cid-remote"
        payload (bytes-of 9 8 7 6 5)]
    (-> ((:put-block! a) cid payload)
        (.then (fn [_] ((:get-block b) cid)))
        (.then (fn [got]
                 (expect (some? got) "node B fetched a block it never had, over a real socket to node A")
                 (expect (= (vec payload) (vec got)) "the fetched bytes are byte-identical to what A stored")
                 (expect (= (vec payload) (vec (get @(:store b) cid)))
                         "node B cached the fetched block in its own local store")))
        (.then (fn [_] ((:get-block b) "cid-a-does-not-have")))
        (.then (fn [got]
                 (expect (nil? got)
                         "asking B for a cid that A ALSO doesn't have resolves nil, not an error")))
        (.then (fn [_]
                 (js/Promise.all #js [((:close! a)) ((:close! b))]))))))

(defn- test-unreachable-peer-is-not-fatal []
  ;; b2's configured peer (port 1) refuses the connection outright. get-block
  ;; must still resolve (to nil), not reject -- an unreachable/misconfigured
  ;; peer is not a caller-visible error, the same way a 404 from ipfs-kubo's
  ;; gateway is not.
  (let [b2 (native/open {:node-id "b2" :port 15804
                          :peers [{:id "ghost" :host "127.0.0.1" :port 1}]})]
    (-> ((:get-block b2) "cid-anything")
        (.then (fn [got] (expect (nil? got) "an unreachable peer resolves nil, not a rejection")))
        (.then (fn [_] ((:close! b2)))))))

(defn- test-missing-config-rejected []
  (try
    (native/open {:port 15805})
    (expect false "missing :node-id is rejected")
    (catch :default e
      (expect (= :node-id (:missing (ex-data e))) "missing :node-id identifies itself")))
  (try
    (native/open {:node-id "x"})
    (expect false "missing :port is rejected")
    (catch :default e
      (expect (= :port (:missing (ex-data e))) "missing :port identifies itself"))))

(defn- test-composes-and-passes-contract []
  (let [node (native/open {:node-id "contract" :port 15806})
        adapter (ipfs/open {:client node})
        backend (storage/compose {:blocks adapter :refs (->LinearRefs (atom {}))})]
    (expect (storage/block-store? adapter) "wrapped in ipfs/open, the native client is a valid IBlockStore")
    (expect (not (storage/ref-store? adapter)) "the composed adapter still declares no ref capability")
    (-> (contract/verify backend)
        (.then (fn [result]
                 (println (str "ipfs-native composed backend contract: " (pr-str result)))
                 (expect (= :verified (:concurrency result))
                         "concurrency is supplied and verified by the ref plane")))
        (.catch (fn [error]
                  (js/console.error (str "FAIL: contract -- " (.-message error)))
                  (when-let [data (ex-data error)] (js/console.error (pr-str data)))
                  (swap! failures inc)))
        (.then (fn [_] ((:close! node)))))))

(defn -main [& _]
  (-> (test-local-round-trip)
      (.then (fn [_] (test-real-two-port-fetch)))
      (.then (fn [_] (test-unreachable-peer-is-not-fatal)))
      (.then (fn [_]
               (test-missing-config-rejected)
               (test-composes-and-passes-contract)))
      (.then (fn [_]
               (if (zero? @failures)
                 (println "ipfs-native-test: all green")
                 (println (str "ipfs-native-test: " @failures " FAILURE(S) above")))
               (.exit js/process (if (zero? @failures) 0 1))))
      (.catch (fn [e]
                (js/console.error (str "FAIL (uncaught): " (or (.-message e) (str e))))
                (when-let [d (ex-data e)] (js/console.error (pr-str d)))
                (.exit js/process 1)))))

(-main)
