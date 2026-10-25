(ns kotobase.engine.lsm.provider
  "Asynchronous block/ref coordinator for Worker and R2-style hosts."
  (:require [ipld.core :as ipld]
            [kotobase.blockcodec.node :as bcn]
            [kotobase.engine.contract :as engine]
            [kotobase.engine.lsm :as lsm]
            [kotobase.storage.core :as storage]))

(defn- runtime-of [eng]
  (or (:kotobase.provider/runtime (meta eng))
      (throw (ex-info "engine was not created by engine-from-backend"
                      {:type :kotobase.engine/missing-provider-runtime}))))

(defn engine-from-backend [backend options]
  (storage/validate-backend! backend)
  (let [cache (atom {})
        pending (atom {})
        requests (atom 0)
        put! (fn [cid bytes]
               (swap! cache assoc cid bytes)
               (swap! pending assoc cid bytes))
        get-fn (fn [cid]
                 (or (get @cache cid)
                     (throw (ex-info "block is not in the synchronous cache"
                                     {:type :kotobase.engine/missing-block
                                      :missing-cid cid}))))
        commit-get-fn
        (fn [cid]
          (if-some [bytes (get @cache cid)]
            (js/Promise.resolve bytes)
            (do
              (swap! requests inc)
              (-> (storage/-get-blocks backend [cid])
                  (.then
                   (fn [blocks]
                     (if-some [bytes (get blocks cid)]
                       (let [actual (ipld/cid bytes)]
                         (when-not (= cid actual)
                           (throw (ex-info "content-addressed block CID mismatch"
                                           {:type :ipld/cid-mismatch
                                            :expected-cid cid
                                            :actual-cid actual})))
                         (swap! cache assoc cid bytes)
                         bytes)
                       (throw (ex-info "content-addressed block was not found"
                                       {:type :kotobase.engine/block-not-found
                                        :cid cid})))))))))
        eng (lsm/lsm-engine
             (merge options {:put! put! :get-fn get-fn
                             :commit-get-fn commit-get-fn}))]
    (with-meta eng
      {:kotobase.provider/runtime
       {:backend backend :cache cache :pending pending :requests requests}})))

(defn request-count [eng]
  @(-> eng runtime-of :requests))

(defn- fetch-cids! [eng cids]
  (let [{:keys [backend cache requests]} (runtime-of eng)
        missing (vec (distinct (remove #(contains? @cache %) cids)))]
    (if (empty? missing)
      (js/Promise.resolve nil)
      (do
        (swap! requests + (count missing))
        (-> (storage/-get-blocks backend missing)
            (.then
             (fn [blocks]
               (when-let [absent (seq (remove #(contains? blocks %) missing))]
                 (throw (ex-info "content-addressed blocks were not found"
                                 {:type :kotobase.engine/block-not-found
                                  :cids (vec absent)})))
               (doseq [cid missing
                       :let [actual (ipld/cid (get blocks cid))]]
                 (when-not (= cid actual)
                   (throw (ex-info "content-addressed block CID mismatch"
                                   {:type :ipld/cid-mismatch
                                    :expected-cid cid :actual-cid actual}))))
               (swap! cache merge blocks)
               nil)))))))

(defn- ref-cids [refs]
  (mapv (comp ipld/link-cid #(get % "cid")) refs))

(defn- hydrate-run-refs! [eng refs]
  (let [cids (ref-cids refs)]
    (-> (fetch-cids! eng cids)
        (.then
         (fn [_]
           (let [cache (:cache (runtime-of eng))
                 children (mapcat (fn [cid]
                                    (lsm/run-node-child-cids
                                     (bcn/decode-node (get @cache cid))))
                                  cids)]
             (fetch-cids! eng children)))))))

(defn- all-run-refs [state]
  (vec (mapcat val (:run-refs state))))

(defn- prefetch-metadata! [eng head]
  (letfn [(step [cid]
            (if-not cid
              (js/Promise.resolve nil)
              (-> (fetch-cids! eng [cid])
                  (.then
                   (fn [_]
                     (let [cache (:cache (runtime-of eng))
                           node (bcn/decode-node (get @cache cid))
                           previous (some-> (get node "previous")
                                            ipld/link-cid)]
                       (step previous)))))))]
    (step head)))

(defn restore-head [eng backend ref-name]
  (storage/validate-backend! backend)
  (-> (storage/-read-ref backend ref-name)
      (.then
       (fn [head]
         (when head
           (let [cid (:cid head)]
             (-> (fetch-cids! eng [cid])
                 (.then
                  (fn [_]
                    (let [cache (:cache (runtime-of eng))
                          node (bcn/decode-node (get @cache cid))
                          lsm-cid (ipld/link-cid (get node "lsm-manifest"))
                          metadata-head (some-> (get node "metadata-head")
                                                ipld/link-cid)
                          format-version (get node "format-version")]
                      (-> (fetch-cids! eng [lsm-cid])
                          (.then (fn [_]
                                   (if (= 2 format-version)
                                     (prefetch-metadata! eng metadata-head)
                                     nil)))
                          (.then (fn [_]
                                   (engine/restore-state eng cid
                                                         {:lazy? true}))))))))))))))

(defn scan! [eng snapshot pattern opts]
  (if (:history? snapshot)
    (js/Promise.resolve (engine/scan eng snapshot pattern opts))
    (let [[_ refs] (lsm/scan-run-refs (:run-refs snapshot) pattern)]
      (-> (hydrate-run-refs! eng refs)
          (.then (fn [_] (engine/scan eng snapshot pattern opts)))))))

(defn checkpoint! [eng snapshot opts]
  (-> (hydrate-run-refs! eng (all-run-refs snapshot))
      (.then (fn [_] (engine/checkpoint eng snapshot opts)))))

(declare flush-pending!)

(defn maintain-and-publish! [eng backend ref-name state opts]
  (storage/validate-backend! backend)
  (let [expected (:physical-root state)]
    (-> (hydrate-run-refs! eng (all-run-refs state))
        (.then (fn [_] (engine/maintain eng state opts)))
        (.then
         (fn [result]
           (-> (flush-pending! eng)
               (.then
                (fn [_]
                  (let [next-root (get-in result [:receipt :after-physical-root])]
                    (if (= expected next-root)
                      (assoc result :publish-status :noop)
                      (-> (storage/-compare-and-set-ref!
                           backend ref-name expected next-root)
                          (.then
                           (fn [publication]
                             (if (:published? publication)
                               (assoc result :publication publication
                                      :publish-status :published)
                               {:publish-status :conflict
                                :publication publication
                                :expected-root expected
                                :candidate-root next-root
                                :winner-root (:current publication)}))))))))))))))

(defn- flush-pending! [eng]
  (let [{:keys [backend pending]} (runtime-of eng)
        blocks (mapv (fn [[cid bytes]] {:cid cid :bytes bytes}) @pending)]
    (-> (if (seq blocks)
          (storage/-put-blocks! backend blocks)
          (js/Promise.resolve nil))
        (.then (fn [result]
                 (reset! pending {})
                 result)))))

(defn transact-and-publish! [eng backend ref-name state request]
  (storage/validate-backend! backend)
  (let [expected (:physical-root state)]
    (-> (hydrate-run-refs! eng (all-run-refs state))
        (.then (fn [_] (engine/transact eng state request)))
        (.then
         (fn [result]
           (-> (flush-pending! eng)
               (.then
                (fn [_]
                  (let [next-root (get-in result [:receipt :physical-root])]
                    (-> (storage/-compare-and-set-ref!
                         backend ref-name expected next-root)
                        (.then
                         (fn [publication]
                           (if (:published? publication)
                             (assoc result :publication publication
                                    :publish-status :published)
                             {:publish-status :conflict
                              :publication publication
                              :expected-root expected
                              :candidate-root next-root
                              :winner-root (:current publication)})))))))))))))
