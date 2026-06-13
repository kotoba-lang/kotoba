(ns kotoba.idb
  "IndexedDB persistence for the browser kotoba node — ClojureScript port of
   kotoba-idb.js + the rawblocks store from kotoba-blocks.js (ADR-2606013600 P1/D5).

   One database `kotoba-node` (v2) with two object stores:
     - `snapshots`  (keyPath \"graph\")  — one canonical snapshot row per graph
     - `rawblocks`  (key = CID multibase) — content-addressed Prolly blocks

   Content-addressing makes the rawblocks store trustless: callers re-verify the
   CID on ingest (`kotoba.blocks`), so a tampered block never reaches the read
   engine. A cold start replays the tree from `rawblocks` with zero network.

   Zero external deps — raw `js/Promise` interop, same style as kotoba.node.")

(def ^:private db-name "kotoba-node")
(def ^:private db-version 2)
(def ^:private snap-store "snapshots")
(def ^:private block-store "rawblocks")

(defonce ^:private db-promise (atom nil))

(defn- open-db []
  (or @db-promise
      (reset! db-promise
              (js/Promise.
               (fn [resolve reject]
                 (let [req (.open js/indexedDB db-name db-version)]
                   (set! (.-onupgradeneeded req)
                         (fn [_]
                           (let [db    (.-result req)
                                 names (.-objectStoreNames db)]
                             (when-not (.contains names snap-store)
                               (.createObjectStore db snap-store #js {:keyPath "graph"}))
                             (when-not (.contains names block-store)
                               (.createObjectStore db block-store)))))
                   (set! (.-onsuccess req) (fn [_] (resolve (.-result req))))
                   (set! (.-onerror req) (fn [_] (reject (.-error req))))))))))

(defn- request->promise [^js req]
  (js/Promise.
   (fn [resolve reject]
     (set! (.-onsuccess req) (fn [_] (resolve (.-result req))))
     (set! (.-onerror req) (fn [_] (reject (.-error req)))))))

(defn- store [^js db name mode]
  (-> db (.transaction name mode) (.objectStore name)))

;; ── snapshots (one row per graph) ────────────────────────────────────────────

(defn get-snapshot
  "Load the persisted snapshot row for `graph`, or nil. Returns Promise."
  [graph]
  (-> (open-db)
      (.then (fn [^js db] (request->promise (.get (store db snap-store "readonly") graph))))
      (.then (fn [r] (or r nil)))))

(defn put-snapshot
  "Persist `{:datomsJson :cid :count}` (JS object) for `graph`. Returns Promise<row>."
  [graph ^js snap]
  (-> (open-db)
      (.then (fn [^js db]
               (let [row #js {:graph      graph
                              :datomsJson (.-datomsJson snap)
                              :cid        (.-cid snap)
                              :count      (.-count snap)
                              :ts         (js/Date.now)}]
                 (-> (request->promise (.put (store db snap-store "readwrite") row))
                     (.then (fn [_] row))))))))

(defn clear-snapshot
  "Drop the persisted snapshot for `graph` (debug / forced reseed). Returns Promise."
  [graph]
  (-> (open-db)
      (.then (fn [^js db]
               (request->promise (.delete (store db snap-store "readwrite") graph))))
      (.then (fn [_] nil))))

;; ── raw blocks (CID → bytes) ─────────────────────────────────────────────────

(defn get-block
  "Fetch a raw block by CID multibase, or nil. Returns Promise<Uint8Array|nil>."
  [cid]
  (-> (open-db)
      (.then (fn [^js db] (request->promise (.get (store db block-store "readonly") cid))))
      (.then (fn [r] (when r (js/Uint8Array. r))))))

(defn put-block
  "Persist raw `bytes` (Uint8Array) under `cid` (durable for cold start). Returns Promise."
  [cid ^js bytes]
  (-> (open-db)
      (.then (fn [^js db]
               (request->promise (.put (store db block-store "readwrite") bytes cid))))
      (.then (fn [_] nil))))
