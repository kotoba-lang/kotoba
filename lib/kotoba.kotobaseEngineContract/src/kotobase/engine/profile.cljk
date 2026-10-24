(ns kotobase.engine.profile)

(def known-storage-models
  #{:memory :prolly :merkle-lsm :lsm-prolly-checkpoint})

(def archive-providers #{:s3 :r2 :b2 :ipfs :filecoin})
(def anchor-providers #{:fevm :evm :base-l2})

(defn profile
  ([storage-model format-version capabilities]
   (profile storage-model format-version capabilities {}))
  ([storage-model format-version capabilities extra]
   (merge {:engine/id storage-model
           :engine/format-version format-version
           :engine/storage-model storage-model
           :engine/capabilities (set capabilities)}
          extra)))

(def memory
  (profile :memory 1 #{:transact :snapshot :scan :history :checkpoint
                       :idempotent-request}))

(def prolly
  (profile :prolly 1 #{:transact :snapshot :scan :history :checkpoint :restore
                       :structural-diff :content-addressed}))

(def merkle-lsm
  (profile :merkle-lsm 1 #{:transact :snapshot :scan :history :checkpoint :restore
                           :background-compaction :content-addressed}))

(def lsm-prolly-checkpoint
  (profile :lsm-prolly-checkpoint 1
           #{:transact :snapshot :scan :history :checkpoint :restore
             :background-compaction :structural-diff :content-addressed}))

(defn validate-profile [p]
  (when-not (map? p)
    (throw (ex-info "engine profile must be a map"
                    {:type :kotobase.engine/invalid-profile})))
  (when-not (keyword? (:engine/id p))
    (throw (ex-info "engine profile requires keyword :engine/id"
                    {:type :kotobase.engine/invalid-profile :profile p})))
  (when-not (and (integer? (:engine/format-version p))
                 (pos? (:engine/format-version p)))
    (throw (ex-info "engine profile requires positive :engine/format-version"
                    {:type :kotobase.engine/invalid-profile :profile p})))
  (when-not (or (known-storage-models (:engine/storage-model p))
                (qualified-keyword? (:engine/storage-model p)))
    (throw (ex-info "unknown storage model; extensions must use a qualified keyword"
                    {:type :kotobase.engine/invalid-profile :profile p})))
  (when (or (archive-providers (:engine/storage-model p))
            (anchor-providers (:engine/storage-model p)))
    (throw (ex-info "archive and anchor providers are not storage engines"
                    {:type :kotobase.engine/layer-violation :profile p})))
  (when-not (set? (:engine/capabilities p))
    (throw (ex-info "engine profile requires a capability set"
                    {:type :kotobase.engine/invalid-profile :profile p})))
  p)
