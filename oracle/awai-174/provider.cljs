(ns awai-oracle.provider
  (:require [ipld.core :as ipld]
            [kotobase.storage.core :as storage]
            [kotobase.engine.prolly.provider :as provider]))
(defn backend [head blocks reads]
  (reify
    storage/IBlockStore
    (-put-blocks! [_ _] (js/Promise.resolve nil))
    (-get-blocks [_ cids] (swap! reads into cids) (js/Promise.resolve (select-keys blocks cids)))
    storage/IRefStore
    (-read-ref [_ _] (js/Promise.resolve {:cid head :version 1}))
    (-compare-and-set-ref! [_ _ _ _] (js/Promise.resolve nil))
    storage/IBackendCapabilities
    (-capabilities [_] #{:immutable-blocks :cid-addressed-read :conditional-ref :linearizable-ref})))
(defn fail-test [head blocks expected-reads]
  (let [reads (atom []) b (backend head blocks reads)
        eng (provider/engine-from-backend b {:blind-fn identity :encrypt-fn identity :decrypt-fn identity :digest-fn identity})]
    (-> (provider/restore-head eng b "main")
        (.then (fn [_] (throw (js/Error. "corrupt block was accepted")))
               (fn [e]
                 (when-not (= :ipld/cid-mismatch (:type (ex-data e))) (throw e))
                 (when (contains? @(-> eng meta :kotobase.provider/runtime :cache) (last expected-reads)) (throw (js/Error. "corrupt block was cached")))
                 (when-not (= expected-reads @reads) (throw (js/Error. (str "unexpected reads " @reads)))))))))
(defn -main []
  (let [metadata (ipld/node->block {"previous" nil})
        trap (ipld/node->block {"unexpected" true})
        corrupted (ipld/node->block {"previous" (ipld/link (:cid trap))})
        root (ipld/node->block {"format-version" 2 "metadata-head" (ipld/link (:cid metadata))})
        wrong-root (ipld/node->block {"format-version" 2 "metadata-head" (ipld/link (:cid trap))})]
    (-> (js/Promise.all
         #js [(fail-test (:cid root) {(:cid root) (:bytes wrong-root)} [(:cid root)])
              (fail-test (:cid root) {(:cid root) (:bytes root) (:cid metadata) (:bytes corrupted)} [(:cid root) (:cid metadata)])])
        (.then (fn [_] (println "provider corrupt head and metadata rejected before following links")))
        (.catch (fn [e] (.error js/console e) (set! (.-exitCode js/process) 1))))))
(set! *main-cli-fn* -main)
