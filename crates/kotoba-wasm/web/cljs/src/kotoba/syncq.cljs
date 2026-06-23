(ns kotoba.syncq
  "Offline sync queue in **IndexedDB** (docs/gftd-office), shared with `office-sw.js`
   for **Background Sync**. The page (passkey-unlocked) ENQUEUES *pre-signed* transact
   requests (#js{url body}); the Service Worker DRAINS them on reconnect / background
   sync / page nudge — so edits sync even when the tab is closed (the SW cannot run
   WebAuthn, so signing must happen in the page; only the POST is deferred).

   localStorage is invisible to a SW, so the queue lives in IndexedDB (DB
   \"kotoba-office\", store \"syncq\"), the exact schema office-sw.js reads.")

(def ^:private db-name "kotoba-office")
(def ^:private store "syncq")

(defn- open-db []
  (js/Promise.
    (fn [res rej]
      (let [r (js/indexedDB.open db-name 1)]
        (set! (.-onupgradeneeded r)
              (fn [_]
                (let [db (.-result r)]
                  (when-not (.contains (.-objectStoreNames db) store)
                    (.createObjectStore db store #js {:keyPath "id" :autoIncrement true})))))
        (set! (.-onsuccess r) (fn [_] (res (.-result r))))
        (set! (.-onerror r) (fn [_] (rej (.-error r))))))))

(defn enqueue!
  "Persist a pre-signed request #js{url body}. Returns Promise<true>."
  [req]
  (-> (open-db)
      (.then (fn [db]
               (js/Promise.
                 (fn [res rej]
                   (let [t (.transaction db store "readwrite")]
                     (.add (.objectStore t store) req)
                     (set! (.-oncomplete t) (fn [_] (res true)))
                     (set! (.-onerror t) (fn [_] (rej (.-error t)))))))))))

(defn pending
  "Promise<number of queued requests>."
  []
  (-> (open-db)
      (.then (fn [db]
               (js/Promise.
                 (fn [res rej]
                   (let [rq (.count (.objectStore (.transaction db store "readonly") store))]
                     (set! (.-onsuccess rq) (fn [_] (res (.-result rq))))
                     (set! (.-onerror rq) (fn [_] (rej (.-error rq)))))))))))

(defn register-bg-sync!
  "Register a Background Sync so the SW drains the queue even with the page closed
   (best-effort; the browser schedules the 'sync' event on connectivity)."
  []
  (-> (.-ready js/navigator.serviceWorker)
      (.then (fn [reg] (when-let [s (.-sync reg)] (.register s "office-sync"))))
      (.catch (fn [_] nil))))

(defn nudge-sw!
  "Ask the active SW to drain the queue now (page-open reconnect path)."
  []
  (-> (.-ready js/navigator.serviceWorker)
      (.then (fn [reg] (some-> (.-active reg) (.postMessage #js {:type "office-flush"}))))
      (.catch (fn [_] nil))))
