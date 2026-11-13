(ns awai-oracle.publish-race
  (:require [kotobase.storage.core :as storage]
            [kotobase.engine.contract :as engine]
            [kotobase.engine.prolly.provider :as provider]))
(defn deferred []
  (let [f (atom nil) p (js/Promise. (fn [resolve _] (reset! f resolve)))]
    {:promise p :resolve (fn [v] (@f v))}))
(defn run []
  (let [blocks (atom {}) refs (atom {}) calls (atom 0)
        first-start (deferred) allow-first (deferred) second-built (deferred) allow-second (deferred)
        backend (reify
          storage/IBlockStore
          (-put-blocks! [_ batch]
            (let [n (swap! calls inc) save #(do (swap! blocks into (map (juxt :cid :bytes) batch)) nil)]
              (if (= n 1)
                (do ((:resolve first-start) true) (.then (:promise allow-first) save))
                (js/Promise.resolve (save)))))
          (-get-blocks [_ cids] (js/Promise.resolve (select-keys @blocks cids)))
          storage/IRefStore
          (-read-ref [_ ref] (js/Promise.resolve (when-let [cid (get @refs ref)] {:cid cid :version 1})))
          (-compare-and-set-ref! [_ ref expected cid]
            (let [current (get @refs ref)]
              (if (= expected current)
                (do (swap! refs assoc ref cid) (js/Promise.resolve {:published? true :cid cid}))
                (js/Promise.resolve {:published? false :current current}))))
          storage/IBackendCapabilities
          (-capabilities [_] #{:immutable-blocks :cid-addressed-read :conditional-ref :linearizable-ref}))
        crypto {:blind-fn #(js/Promise.resolve (str "blind:" %)) :encrypt-fn #(js/Promise.resolve %) :decrypt-fn #(js/Promise.resolve %) :digest-fn identity}
        eng (provider/engine-from-backend backend crypto)
        state (engine/empty-state eng "db")
        tx #(hash-map :database-id "db" :request-id % :tx-data [[:db/add % :name %]])
        original engine/transact
        a (provider/transact-and-publish! eng backend "a" state (tx "a"))]
    (-> (:promise first-start)
        (.then (fn [_]
                 (let [b (with-redefs [engine/transact (fn [e s req]
                                                        (.then (original e s req)
                                                               (fn [result]
                                                                 ((:resolve second-built) true)
                                                                 (.then (:promise allow-second) (fn [_] result)))))]
                           (provider/transact-and-publish! eng backend "b" state (tx "b")))]
                   (-> (:promise second-built)
                       (.then (fn [_] ((:resolve allow-first) true) a))
                       (.then (fn [_] ((:resolve allow-second) true) b))))))
        (.then (fn [b-result]
                 (let [root (get-in b-result [:receipt :physical-root])]
                   (when-not (= :published (:publish-status b-result)) (throw (js/Error. "second publish failed")))
                   (when-not (contains? @blocks root) (throw (js/Error. "published root missing from backend")))
                   (let [fresh (provider/engine-from-backend backend crypto)]
                     (-> (provider/restore-head fresh backend "b")
                         (.then (fn [restored]
                                  (-> (engine/scan fresh (engine/open-snapshot fresh restored) ["b" :name nil])
                                      (.then (fn [rows] (when-not (= ["b"] (mapv :v rows)) (throw (js/Error. "scan mismatch")))
                                               (println "concurrent publish restores complete second transaction")))))))))))
        (.catch (fn [e] (.error js/console e) (set! (.-exitCode js/process) 1))))))
(defn failure-check []
  (let [blocks (atom {}) refs (atom {}) fail? (atom true)
        backend (reify
          storage/IBlockStore
          (-put-blocks! [_ batch]
            (if @fail?
              (do (reset! fail? false) (js/Promise.reject (js/Error. "injected upload failure")))
              (do (swap! blocks into (map (juxt :cid :bytes) batch)) (js/Promise.resolve nil))))
          (-get-blocks [_ cids] (js/Promise.resolve (select-keys @blocks cids)))
          storage/IRefStore
          (-read-ref [_ ref] (js/Promise.resolve (when-let [cid (get @refs ref)] {:cid cid :version 1})))
          (-compare-and-set-ref! [_ ref expected cid]
            (swap! refs assoc ref cid) (js/Promise.resolve {:published? true :cid cid}))
          storage/IBackendCapabilities
          (-capabilities [_] #{:immutable-blocks :cid-addressed-read :conditional-ref :linearizable-ref}))
        crypto {:blind-fn #(js/Promise.resolve (str "blind:" %)) :encrypt-fn #(js/Promise.resolve %) :decrypt-fn #(js/Promise.resolve %) :digest-fn identity}
        eng (provider/engine-from-backend backend crypto)
        state (engine/empty-state eng "retry-db")
        request {:database-id "retry-db" :request-id "retry" :tx-data [[:db/add "retry" :name "saved"]]}]
    (-> (provider/transact-and-publish! eng backend "retry" state request)
        (.then (fn [_] (throw (js/Error. "failed upload was published")))
               (fn [e]
                 (when-not (= "injected upload failure" (.-message e)) (throw e))
                 (when (seq @refs) (throw (js/Error. "CAS after failed upload")))
                 (when-not (seq @(-> eng meta :kotobase.provider/runtime :pending))
                   (throw (js/Error. "failed batch was lost")))
                 (provider/transact-and-publish! eng backend "retry" state request)))
        (.then (fn [result]
                 (when-not (= :published (:publish-status result)) (throw (js/Error. "retry failed")))
                 (let [fresh (provider/engine-from-backend backend crypto)]
                   (-> (provider/restore-head fresh backend "retry")
                       (.then (fn [restored]
                                (-> (engine/scan fresh (engine/open-snapshot fresh restored) ["retry" :name nil])
                                    (.then (fn [rows]
                                             (when-not (= ["saved"] (mapv :v rows)) (throw (js/Error. "retry scan mismatch")))
                                             (println "failed upload retained; no CAS; retry restores")))))))))))))
(defn -main []
  (-> (run) (.then (fn [_] (when-not (.-exitCode js/process) (failure-check))))
      (.catch (fn [e] (.error js/console e) (set! (.-exitCode js/process) 1)))))
(set! *main-cli-fn* -main)
