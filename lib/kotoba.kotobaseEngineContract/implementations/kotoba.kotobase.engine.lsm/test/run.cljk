(ns run
  (:require [kotobase.engine.contract :as engine]
            [kotobase.engine.lsm.provider :as provider]
            [kotobase.storage.core :as storage]))

(defrecord AsyncStore [blocks refs]
  storage/IBlockStore
  (-put-blocks! [_ values]
    (doseq [{:keys [cid bytes]} values] (swap! blocks assoc cid bytes))
    (js/Promise.resolve nil))
  (-get-blocks [_ cids]
    (js/Promise.resolve
     (into {} (keep (fn [cid]
                      (when-let [bytes (get @blocks cid)] [cid bytes]))) cids)))
  storage/IRefStore
  (-read-ref [_ name]
    (js/Promise.resolve
     (when-let [cid (get @refs name)] {:cid cid :version cid})))
  (-compare-and-set-ref! [_ name expected next]
    (let [current (get @refs name)]
      (if (= expected current)
        (do (swap! refs assoc name next)
            (js/Promise.resolve {:published? true :current next}))
        (js/Promise.resolve {:published? false :current current}))))
  storage/IBackendCapabilities
  (-capabilities [_]
    (conj storage/required-capabilities :linearizable-ref)))

(defn check [truth message]
  (when-not truth (throw (js/Error. message)))
  (println "ok -" message))

(def options
  {:digest-fn #(str "digest:" (hash %))
   :encrypt-fn #(js/Promise.resolve %)
   :decrypt-fn #(js/Promise.resolve %)
   :metadata-key-fn #(js/Promise.resolve (str "key:" (hash %)))
   :target-run-rows 8
   :l0-compaction-threshold 1000})

(defn- cold-write! [backend database-id]
  (let [writer (provider/engine-from-backend backend options)]
    (-> (provider/restore-head writer backend "main")
        (.then
         (fn [state]
           (provider/transact-and-publish!
            writer backend "main" state
            {:database-id database-id :request-id "mixed"
             :tx-data [[:db/retract "entity-64" :metric/value 64]
                       [:db/add "entity-new" :metric/value 999]]})))
        (.then
         (fn [result]
           (check (= :published (:publish-status result))
                  "cold mixed write publishes"))))))

(defn- verify-conflict! [backend database-id]
  (let [winner (provider/engine-from-backend backend options)
        loser (provider/engine-from-backend backend options)]
    (-> (js/Promise.all
         #js [(provider/restore-head winner backend "main")
              (provider/restore-head loser backend "main")])
        (.then
         (fn [states]
           (-> (provider/transact-and-publish!
                winner backend "main" (aget states 0)
                {:database-id database-id :request-id "winner"
                 :tx-data [[:db/add "winner" :status :committed]]})
               (.then
                (fn [published]
                  (let [winner-root (get-in published [:receipt :physical-root])]
                    (-> (provider/transact-and-publish!
                         loser backend "main" (aget states 1)
                         {:database-id database-id :request-id "loser"
                          :tx-data [[:db/add "loser" :status :stale]]})
                        (.then
                         (fn [conflict]
                           (check (= :conflict (:publish-status conflict))
                                  "stale LSM writer loses CAS")
                           (check (= winner-root (:winner-root conflict))
                                  "CAS loser observes the authoritative root")))))))))))))

(defn- verify-corruption-rejected! [backend]
  (let [head (get @(:refs backend) "main")
        replacement (some (fn [[cid bytes]] (when-not (= cid head) bytes))
                          @(:blocks backend))
        corrupted-blocks (atom (assoc @(:blocks backend) head replacement))
        corrupted (->AsyncStore corrupted-blocks (atom @(:refs backend)))
        reader (provider/engine-from-backend corrupted options)]
    (-> (provider/restore-head reader corrupted "main")
        (.then (fn [_]
                 (throw (js/Error. "corrupted CID unexpectedly restored"))))
        (.catch
         (fn [error]
           (check (= "content-addressed block CID mismatch" (.-message error))
                  "corrupted object-store block fails closed"))))))

(defn- verify-maintenance! [backend]
  (let [maintainer (provider/engine-from-backend backend options)]
    (-> (provider/restore-head maintainer backend "main")
        (.then
         (fn [state]
           (provider/maintain-and-publish! maintainer backend "main" state {})))
        (.then
         (fn [result]
           (check (= :published (:publish-status result))
                  "physical maintenance publishes by CAS")
           (check (= :completed (get-in result [:receipt :status]))
                  "maintenance is real compaction, not checkpoint")
           (let [reader (provider/engine-from-backend backend options)]
             (-> (provider/restore-head reader backend "main")
                 (.then
                  (fn [restored]
                    (check (= (get-in result [:receipt :after-physical-root])
                              (:physical-root restored))
                           "published maintenance root restores"))))))))))

(defn- verify-reader! [backend database-id]
  (let [reader (provider/engine-from-backend backend options)
        stored-blocks (count @(:blocks backend))]
    (-> (provider/restore-head reader backend "main")
        (.then
         (fn [restored]
           (check (nil? (:runs restored)) "cold restore is manifest-only")
           (let [requests (provider/request-count reader)]
             (check (= 3 requests)
                    (str "restore fetches two manifests plus the current-request index"
                         " (requests=" requests ")")))
           (provider/scan! reader (engine/open-snapshot reader restored)
                           ["entity-64" :metric/value nil] {})))
        (.then
         (fn [rows]
           (check (= [64] (mapv :v rows))
                  "point scan reads the selected run range")
           (let [requests (provider/request-count reader)]
             (check (< requests stored-blocks)
                    (str "point scan requests=" requests
                         " stored-blocks=" stored-blocks)))
           (-> (cold-write! backend database-id)
               (.then (fn [_] (verify-conflict! backend database-id)))
               (.then (fn [_] (verify-maintenance! backend)))
               (.then (fn [_] (verify-corruption-rejected! backend)))))))))

(defn main []
  (let [backend (->AsyncStore (atom {}) (atom {}))
        writer (provider/engine-from-backend backend options)
        database-id "lsm/cljs"
        s0 (engine/empty-state writer database-id)
        seed {:database-id database-id :request-id "seed"
              :tx-data (mapv (fn [n]
                               [:db/add (str "entity-" n) :metric/value n])
                             (range 128))}]
    (-> (provider/transact-and-publish! writer backend "main" s0 seed)
        (.then (fn [published]
                 (check (= :published (:publish-status published))
                        "immutable LSM blocks publish before CAS")
                 (verify-reader! backend database-id)))
        (.then (fn [_] (println "kotobase-engine-lsm cljs: all green")))
        (.catch (fn [error]
                  (js/console.error error)
                  (js/process.exit 1))))))

(main)
