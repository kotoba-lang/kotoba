(ns kotoba.wasm.re-frame
  "Tiny re-frame-shaped runtime for kotoba WASM.
   The API is intentionally close to re-frame.core for portable app code, but it
   stores everything in plain atoms and computes subscriptions synchronously."
  (:refer-clojure :exclude [subscribe]))

(defonce app-db (atom {}))
(defonce event-db-handlers (atom {}))
(defonce sub-handlers (atom {}))

(defn clear! []
  (reset! app-db {})
  (reset! event-db-handlers {})
  (reset! sub-handlers {})
  nil)

(defn reg-event-db [id f]
  (swap! event-db-handlers assoc id f)
  id)

(defn dispatch-sync [event]
  (let [id (first event)]
    (if-let [f (get @event-db-handlers id)]
      (swap! app-db #(f % event))
      (throw (ex-info "No event-db handler registered" {:event event}))))
  nil)

(defn dispatch [event]
  ;; WASM hosts can later map this to a queued event loop. The minimal runtime is
  ;; synchronous so tests and deterministic renders stay simple.
  (dispatch-sync event))

(defn reg-sub [id f]
  (swap! sub-handlers assoc id f)
  id)

(defn- run-sub [query]
  (let [id (first query)]
    (if-let [f (get @sub-handlers id)]
      (f @app-db query)
      (throw (ex-info "No subscription registered" {:query query})))))

(defn subscribe [query]
  #?(:clj
     (reify clojure.lang.IDeref
       (deref [_] (run-sub query)))
     :cljs
     (reify IDeref
       (-deref [_] (run-sub query)))))
