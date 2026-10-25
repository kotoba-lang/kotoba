(ns code-graph.async-node
  (:require [code-graph.core :as code]
            [code-graph.async :as async]
            [kotobase.local :as local]
            [kotobase.store :as store]))

(deftype PromiseStore [delegate]
  store/IStore
  (-put [_ coll key value]
    (js/Promise.resolve (store/-put delegate coll key value)))
  (-get [_ coll key]
    (js/Promise.resolve (store/-get delegate coll key)))
  (-list [_ coll]
    (js/Promise.resolve (store/-list delegate coll)))
  (-append [_ stream event]
    (js/Promise.resolve (store/-append delegate stream event)))
  (-read [_ stream since]
    (js/Promise.resolve (store/-read delegate stream since)))
  store/ITransactionalStore
  (-snapshot [_ scope]
    (js/Promise.resolve (store/-snapshot delegate scope)))
  (-transact [_ request]
    (js/Promise.resolve (store/-transact delegate request))))

(defn fail! [error]
  (js/console.error error)
  (set! (.-exitCode js/process) 1))

(defn -main []
  (let [delegate (local/local-store)
        remote (->PromiseStore delegate)
        record {:cid "cid-async" :block {:cid "cid-async"}
                :dependency-cids [] :effects ["graph-read"]}]
    (-> (async/run! async/promise-runtime remote
                    #(code/put-definition! %
                                           (fn [cid block] (= cid (:cid block)))
                                           record))
        (.then (fn [result]
                 (when-not (= "cid-async" (:code.definition/cid result))
                   (throw (js/Error. "async result mismatch")))
                 (async/run! async/promise-runtime remote
                             #(code/transitive-effects % "cid-async"))))
        (.then (fn [effects]
                 (when-not (= #{"graph-read"} effects)
                   (throw (js/Error. "async materialized read mismatch")))
                 (js/console.log "ok - Promise IStore runs the complete code-graph API")))
        (.catch fail!))))

(set! *main-cli-fn* -main)
