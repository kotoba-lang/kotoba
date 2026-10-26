(ns kuro.fs-browser-demo
  "Browser entry for the kuro.fs E2E (S4 of ADR-2609041240).

  Runs the REAL kuro.fs model (the same pure .cljc that the JVM and nbb
  parity suites run) inside a browser page, with the host seam wired to the
  OPFS block store Worker (kuro-opfs-worker.js from kuro.host.opfs's E2E).

  The seam: kuro.fs's injected put-block / get-block are implemented here as
  postMessage round-trips to the Worker — async at the boundary, bridged
  into kuro.fs's synchronous calls through a pending-request map resolved
  when the Worker replies.

  Exposes window.__fsE2E(results) — the page's test driver calls it with a
  scenario and gets receipts back."
  (:require [kuro.fs :as fs]
))

(defonce worker (js/Worker. "/kuro-opfs-worker.js"))
(defonce pending (atom {}))
(defonce next-id (atom 0))

(defn- call-worker
  "postMessage round-trip returning a JS Promise of the reply."
  [op payload]
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

(defn run-scenario
  "The E2E scenario: put bytes -> cid (Worker mints, OPFS caches); write a
  kuro.fs file node at greeting.txt whose leaf carries that cid; ls the
  root; read the file back through kuro.fs read-file with get-block hitting
  OPFS. All through the REAL kuro.fs model."
  []
  (let [st0 (fs/store "bafyrei-root")
        text-in "hello from kuro.fs"
        content (bytes->js text-in)]
    (-> (call-worker :put {:bytes content})
        (.then (fn [reply]
                 (let [cid (get reply "cid")
                       [st1 _cid] (fs/write st0 "greeting.txt" content (fn [_b] cid))
                       [st2 entries] (fs/ls st1 ".")
                       [st3 bytes] (fs/read-file st2 "greeting.txt"
                                                 (fn [c] (if (= c cid) content nil)))]
                   #js {"wroteCid" cid
                        "readText" (when bytes (.decode (js/TextDecoder.) bytes))
                        "lsEntries" (clj->js entries)
                        "readMatches" (when bytes (= text-in (.decode (js/TextDecoder.) bytes)))
                        "receiptCount" (count (fs/receipts st3))
                        "denials" (count (filter #(= :kuro.fs/denied (:kuro.fs/type %))
                                                 (fs/receipts st3)))}))))))

;; test driver
(set! (.-fsE2E js/window)
      (fn []
        (-> (run-scenario)
            (.then (fn [results]
                     (set! (.-__fsResults js/window) results)
                     results)))))
