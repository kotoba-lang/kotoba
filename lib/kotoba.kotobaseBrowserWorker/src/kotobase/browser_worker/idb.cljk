(ns kotobase.browser-worker.idb
  "IndexedDB-backed block/head store for kotobase-peer -- the browser
  counterpart to kotobase.cljc-worker.r2 (ADR-2607051700, app-aozora). One
  IndexedDB database, two object stores: `blocks` (cid -> Uint8Array) and
  `heads` (graph -> chain-cid string).

  Head writes are compare-and-swap, emulated with IndexedDB's transaction
  atomicity (re-read the current value + conditional put, inside ONE
  readwrite transaction) instead of R2's native onlyIf.etagMatches -- there
  is no cross-tab CAS primitive in IndexedDB, so this closes the same race
  R2's CAS closes only for callers sharing one connection (one tab). Multi-
  tab / multi-peer contention is deferred with the rest of the P2P/
  availability layer, same as R2's own documented first-write race note
  (kotobase.cljc-worker.r2/r2-put-head-if-match)."
  (:require [kotobase.cljc-worker.r2 :as r2]))

(def ^:private blocks-store "blocks")
(def ^:private heads-store "heads")

(defn- ->clj-or-nil
  "IndexedDB .get returns JS `undefined` (not `null`) for an absent key;
  ClojureScript's nil? does NOT treat js/undefined as nil, so every read
  must normalize it or CAS-against-absence (see put-head-if-match!) breaks
  silently."
  [v]
  (if (undefined? v) nil v))

(defn open-db
  "→ Promise<IDBDatabase>. Creates the two object stores on first open."
  [db-name]
  (js/Promise.
   (fn [resolve reject]
     (let [req (.open js/indexedDB db-name 1)]
       (set! (.-onupgradeneeded req)
             (fn [_]
               (let [db (.-result req)]
                 (when-not (.contains (.-objectStoreNames db) blocks-store)
                   (.createObjectStore db blocks-store))
                 (when-not (.contains (.-objectStoreNames db) heads-store)
                   (.createObjectStore db heads-store)))))
       (set! (.-onsuccess req) (fn [_] (resolve (.-result req))))
       (set! (.-onerror req) (fn [_] (reject (.-error req))))))))

(defn- store-get [^js db store-name k]
  (js/Promise.
   (fn [resolve reject]
     (let [tx (.transaction db #js [store-name] "readonly")
           os (.objectStore tx store-name)
           req (.get os k)]
       (set! (.-onsuccess req) (fn [_] (resolve (->clj-or-nil (.-result req)))))
       (set! (.-onerror req) (fn [_] (reject (.-error req))))))))

(defn get-bytes
  "→ Promise<Uint8Array|nil>, same shape as kotobase.cljc-worker.r2/r2-get-bytes."
  [db cid]
  (store-get db blocks-store cid))

(defn put-bytes!
  "→ Promise<nil>."
  [^js db cid bytes]
  (js/Promise.
   (fn [resolve reject]
     (let [tx (.transaction db #js [blocks-store] "readwrite")
           os (.objectStore tx blocks-store)
           req (.put os bytes cid)]
       (set! (.-onsuccess req) (fn [_] (resolve nil)))
       (set! (.-onerror req) (fn [_] (reject (.-error req))))))))

(defn get-head
  "→ Promise<{:chain string|nil :etag string|nil}>, same shape as
  kotobase.cljc-worker.r2/r2-get-head. `:etag` here is just the current
  chain value itself (nil = absent) -- put-head-if-match! re-reads and
  compares against it inside one atomic transaction, so the comparison is
  race-free even though this read and that write are separate calls."
  [db graph]
  (-> (store-get db heads-store graph)
      (.then (fn [v] {:chain v :etag v}))))

(defn put-head-if-match!
  "→ Promise<boolean>. true = written; false = another writer's head
  update landed first (caller re-reads and retries, same protocol as
  kotobase.cljc-worker.r2/r2-put-head-if-match)."
  [^js db graph chain etag]
  (js/Promise.
   (fn [resolve reject]
     (let [tx (.transaction db #js [heads-store] "readwrite")
           os (.objectStore tx heads-store)
           get-req (.get os graph)]
       (set! (.-onsuccess get-req)
             (fn [_]
               (if (= (->clj-or-nil (.-result get-req)) etag)
                 (let [put-req (.put os chain graph)]
                   (set! (.-onsuccess put-req) (fn [_] (resolve true)))
                   (set! (.-onerror put-req) (fn [_] (reject (.-error put-req)))))
                 (resolve false))))
       (set! (.-onerror get-req) (fn [_] (reject (.-error get-req))))))))
