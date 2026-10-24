(ns kotobase.engine.prolly.provider
  "ClojureScript/R2 coordinator. Blocks are constructed into a synchronous
  local batch, uploaded durably, and only then exposed by CAS. Reads and cold
  writes use direct asynchronous, CID-checked block fetches."
  (:require [ipld.core :as ipld]
            [kotobase.engine.contract :as engine]
            [kotobase.engine.prolly :as prolly]
            [kotobase.engine.prolly.cursor :as cursor]
            [kotobase.storage.core :as storage]))

(defn- runtime-of [eng]
  (or (:kotobase.provider/runtime (meta eng))
      (throw (ex-info "engine was not created by engine-from-backend"
                      {:type :kotobase.engine/missing-provider-runtime}))))

(defn engine-from-backend
  "Create a Prolly engine whose block writes are buffered for one atomic
  publish attempt. CRYPTO functions keep the normal Promise-based CLJS shape."
  [backend crypto]
  (storage/validate-block-store! backend)
  (let [cache (atom {})
        pending (atom {})
        requests (atom 0)
        put! (fn [cid bytes]
               (swap! cache assoc cid bytes)
               (swap! pending assoc cid bytes)
               nil)
        get-fn (fn [cid]
                 (if-some [bytes (get @cache cid)]
                   bytes
                   (throw (ex-info "block is not in the synchronous read cache"
                                   {:type :kotobase.engine/missing-block
                                    :missing-cid cid}))))
        async-get-fn
        (fn [cid]
          (swap! requests inc)
          (-> (storage/-get-blocks backend [cid])
              (.then (fn [blocks]
                       (if-some [bytes (get blocks cid)]
                         bytes
                         (throw
                          (ex-info "content-addressed block was not found"
                                   {:type :kotobase.engine/block-not-found
                                    :cid cid})))))))
        commit-get-fn
        (fn [cid]
          (if-some [bytes (get @cache cid)]
            (js/Promise.resolve bytes)
            (-> (async-get-fn cid)
                (.then (fn [bytes]
                         (when bytes (swap! cache assoc cid bytes))
                         bytes)))))
        scan-snapshot-fn
        (fn [snapshot-root history metadata-root basis-t pattern opts]
          (cursor/scan async-get-fn (:blind-fn crypto) (:decrypt-fn crypto)
                       snapshot-root history metadata-root basis-t pattern opts))
        eng (prolly/prolly-engine
             (merge {:put! put! :get-fn get-fn
                     :commit-get-fn commit-get-fn
                     :scan-snapshot-fn scan-snapshot-fn}
                    crypto))]
    (with-meta eng
      {:kotobase.provider/runtime
       {:backend backend :cache cache :pending pending :requests requests
        :async-get-fn async-get-fn}})))

(defn request-count [eng]
  @(-> eng runtime-of :requests))

(defn- flush-pending! [eng]
  (let [{:keys [backend pending]} (runtime-of eng)
        blocks (mapv (fn [[cid bytes]] {:cid cid :bytes bytes}) @pending)]
    (-> (if (seq blocks)
          (storage/-put-blocks! backend blocks)
          (js/Promise.resolve nil))
        (.then (fn [result]
                 (reset! pending {})
                 result)))))

(defn- prefetch-metadata! [cache async-get-fn head]
  (letfn [(step [cid]
            (if-not cid
              (js/Promise.resolve nil)
              (-> (async-get-fn cid)
                  (.then (fn [bytes]
                           (swap! cache assoc cid bytes)
                           (let [node (ipld/decode bytes)
                                 previous (some-> (get node "previous")
                                                  ipld/link-cid)]
                             (step previous)))))))]
    (step head)))

(defn restore-head [eng backend ref-name]
  (storage/validate-backend! backend)
  (-> (storage/-read-ref backend ref-name)
      (.then (fn [head]
               (if head
                 (let [{:keys [cache async-get-fn]} (runtime-of eng)
                       cid (:cid head)]
                   (-> (async-get-fn cid)
                       (.then (fn [bytes]
                                (swap! cache assoc cid bytes)
                                (let [node (ipld/decode bytes)
                                      metadata-head
                                      (some-> (get node "metadata-head")
                                              ipld/link-cid)
                                      format-version (get node "format-version")]
                                  (-> (if (= 2 format-version)
                                        (prefetch-metadata! cache async-get-fn
                                                            metadata-head)
                                        (js/Promise.resolve nil))
                                      (.then
                                       (fn [_]
                                         (engine/restore-state eng cid
                                                               {:lazy? true})))))))))
                 nil)))))

(defn transact-and-publish!
  "Upload all immutable blocks before conditional head publication. A CAS
  loser returns :conflict and never rewrites the winner."
  [eng backend ref-name state request]
  (storage/validate-backend! backend)
  (let [expected (:physical-root state)]
    (-> (engine/transact eng state request)
        (.then (fn [result]
                 (-> (flush-pending! eng)
                     (.then (fn [_]
                              (let [next-root (get-in result
                                                      [:receipt :physical-root])]
                                (-> (storage/-compare-and-set-ref!
                                     backend ref-name expected next-root)
                                    (.then
                                     (fn [publication]
                                       (if (:published? publication)
                                         (assoc result
                                                :publication publication
                                                :publish-status :published)
                                         {:publish-status :conflict
                                          :publication publication
                                          :expected-root expected
                                          :candidate-root next-root
                                          :winner-root (:current publication)})))))))))))))
