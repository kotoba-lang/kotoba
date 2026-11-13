(ns awai-oracle.provider-disk
  (:require [kotobase.storage.core :as storage]
            [kotobase.engine.contract :as engine]
            [kotobase.engine.prolly.provider :as provider]))
(def fs (js/require "fs"))
(def root "bafyreiakmttcp6otxvnyqmdjpzlschlskibp7enadlvkguw3nnp47f5wqm")
(def dir ".agent-output/prolly-disk-20261113")
(defn backend [reads]
  (reify
    storage/IBlockStore
    (-put-blocks! [_ _] (throw (js/Error. "read-only oracle")))
    (-get-blocks [_ cids]
      (swap! reads into cids)
      (js/Promise.resolve
       (into {} (keep (fn [cid]
                        (let [path (str dir "/" cid ".block")]
                          (when (.existsSync fs path)
                            [cid (js/Uint8Array. (.readFileSync fs path))]))) cids))))
    storage/IRefStore
    (-read-ref [_ _] (js/Promise.resolve {:cid root :version 1}))
    (-compare-and-set-ref! [_ _ _ _] (throw (js/Error. "read-only oracle")))
    storage/IBackendCapabilities
    (-capabilities [_] #{:immutable-blocks :cid-addressed-read :conditional-ref :linearizable-ref})))
(defn -main []
  (let [reads (atom []) b (backend reads)
        e (provider/engine-from-backend b {:blind-fn #(js/Promise.resolve (str "blind-fixture:" %))
                                          :encrypt-fn #(js/Promise.resolve %)
                                          :decrypt-fn #(js/Promise.resolve %)
                                          :digest-fn identity})]
    (-> (provider/restore-head e b "main")
        (.then (fn [s]
                 (when-not (= root (:physical-root s)) (throw (js/Error. "wrong root")))
                 (-> (js/Promise.all #js [(js/Promise.resolve (engine/open-snapshot e s))
                                          (js/Promise.resolve (engine/open-snapshot e s {:as-of 1}))])
                     (.then (fn [snaps]
                              (js/Promise.all #js [(engine/scan e (aget snaps 0) ["file" :file/name nil])
                                                   (engine/scan e (aget snaps 1) ["file" :file/name nil])]))))))
        (.then (fn [results]
                 (when-not (and (= ["after"] (mapv :v (aget results 0)))
                                (= ["before"] (mapv :v (aget results 1))))
                   (throw (js/Error. (str "unexpected rows " (pr-str results)))))
                 (println "disk provider restore and current/as-of scans passed; block reads" (count @reads))))
        (.catch (fn [e] (.error js/console e) (set! (.-exitCode js/process) 1))))))
(set! *main-cli-fn* -main)
