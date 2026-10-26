(ns kuro.fs-cap-demo
  "Browser entry for the S5 integration E2E: kuro.fs wrote a file (bytes ->
  CID -> OPFS via the block-store Worker); a REAL WASM guest reads it
  through an fs_read host import, gated by a capability check.

  The gate is host-side: the fs_read import is satisfied ONLY when the
  grant covers fs/read on greeting.txt. fs/write is a separate leaf and
  implies nothing. Deny = -1, no bytes moved. This is capability-gated
  guest execution (ADR-2609041240), not kernel isolation."
  (:require [kuro.fs :as fs]))

(defonce worker (js/Worker. "/kuro-opfs-worker.js"))
(defonce pending (atom {}))
(defonce next-id (atom 0))

(defn- call-worker [op payload]
  (js/Promise.
   (fn [resolve _reject]
     (let [id (swap! next-id inc)]
       (swap! pending assoc id resolve)
       (.postMessage worker
                     #js {"kuro.opfs/type" "request"
                          "kuro.opfs/id" id
                          "kuro.opfs/op" (name op)
                          "kuro.opfs/payload" (clj->js payload)})))))

(.addEventListener worker "message"
                   (fn [ev]
                     (let [m (js->clj (.-data ev))
                           id (get m "kuro.opfs/id")
                           resolve (get @pending id)]
                       (when resolve
                         (swap! pending dissoc id)
                         (resolve (get m "kuro.opfs/result"))))))

(defn- bytes->js [s]
  (js/Uint8Array. (.from js/Array (map #(- (.charCodeAt %) 0) s))))

(def grant-read #{"fs/read:cid:greeting.txt"})

(defn- make-imports [grant file-bytes instance-ref]
  #js {:kuro
       #js {:fs_read
            (fn [buf-ptr len]
              (if (contains? grant "fs/read:cid:greeting.txt")
                (do (.set (js/Uint8Array. (.-buffer (.-memory (.-exports (.-instance @instance-ref)))))
                          file-bytes buf-ptr)
                    len)
                -1))}})

(defn- run-guest [grant file-bytes instance-ref]
  (let [g-imports (make-imports grant file-bytes instance-ref)]
    (-> (js/WebAssembly.instantiateStreaming (js/fetch "/guest-fs.wasm") g-imports)
        (.then (fn [obj]
                 (reset! instance-ref obj)
                 (js/Number ((aget (.-exports (.-instance obj)) "run")
                             (.-length file-bytes))))))))

(defn- read-side [st1 cid content]
  (let [[st2 _] (fs/read-file st1 "greeting.txt"
                              (fn [c] (when (= c cid) content)))]
    {:denials (count (filter #(= :kuro.fs/denied (:kuro.fs/type %))
                             (fs/receipts st2)))
     :receipts (count (fs/receipts st2))}))

(defn run-cap-scenario []
  (let [st0 (fs/store "bafyrei-root")
        text-in "guest reads via cap"
        content (bytes->js text-in)
        expected-sum (reduce + 0 (array-seq content))
        instance-ref (atom nil)]
    (-> (call-worker :put {:bytes content})
        (.then (fn [reply]
                 (let [cid (get reply "cid")
                       [st1 _] (fs/write st0 "greeting.txt" content (fn [_b] cid))]
                   (-> (call-worker :get {:cid cid})
                       (.then (fn [getr]
                                (let [file-bytes (get getr "bytes")]
                                  (-> (run-guest grant-read file-bytes instance-ref)
                                      (.then (fn [granted-sum]
                                               (-> (run-guest #{"fs/write:cid:greeting.txt"}
                                                               file-bytes instance-ref)
                                                   (.then (fn [denied-sum]
                                                            (let [side (read-side st1 cid content)]
                                                              #js {"guestRead" (pos? granted-sum)
                                                                   "checksumMatch" (= granted-sum expected-sum)
                                                                   "writeDenied" (zero? denied-sum)
                                                                   "fsDenials" (:denials side)
                                                                   "cid" cid})))))))))))))))))

(set! (.-fsCapE2E js/window)
      (fn [] (-> (run-cap-scenario)
                 (.then (fn [results]
                          (set! (.-__capResults js/window) results)
                          results)))))
