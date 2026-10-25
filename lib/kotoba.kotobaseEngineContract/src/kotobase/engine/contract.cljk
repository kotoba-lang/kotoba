(ns kotobase.engine.contract
  (:require [kotoba.lang.text :as str]
            [kotobase.engine.completion :as completion]
            [kotobase.engine.profile :as profile]))

(defprotocol IEngine
  "Logical database engine seam. State and snapshots are opaque to callers.
  Operations may return an immediate value, JVM CompletionStage, or JavaScript
  Promise."
  (-engine-profile [engine])
  (-empty-state [engine opts])
  (-restore-state [engine physical-root opts])
  (-transact [engine state request])
  (-open-snapshot [engine state selector])
  (-scan [engine snapshot pattern opts])
  (-history [engine snapshot opts])
  (-checkpoint [engine snapshot opts]))

(defprotocol IMaintenance
  "Optional physical-layout maintenance. Kept separate from IEngine because
  checkpoint proves logical state; it does not imply compaction, folding, or
  publication of a new physical root."
  (-maintain [engine state opts]))

(defn nonblank-string? [x]
  (and (string? x) (not (str/blank? x))))

(defn validate-receipt [receipt]
  (when-not (map? receipt)
    (throw (ex-info "engine receipt must be a map"
                    {:type :kotobase.engine/invalid-receipt})))
  (when-not (nonblank-string? (:database-id receipt))
    (throw (ex-info "receipt requires :database-id"
                    {:type :kotobase.engine/invalid-receipt :receipt receipt})))
  (when-not (and (integer? (:epoch receipt)) (not (neg? (:epoch receipt))))
    (throw (ex-info "receipt requires a non-negative :epoch"
                    {:type :kotobase.engine/invalid-receipt :receipt receipt})))
  (when-not (nonblank-string? (:tx-root receipt))
    (throw (ex-info "receipt requires :tx-root"
                    {:type :kotobase.engine/invalid-receipt :receipt receipt})))
  (when-not (nonblank-string? (:physical-root receipt))
    (throw (ex-info "receipt requires engine-specific :physical-root"
                    {:type :kotobase.engine/invalid-receipt :receipt receipt})))
  (when-not (#{:committed :replayed} (:status receipt))
    (throw (ex-info "receipt status must be :committed or :replayed"
                    {:type :kotobase.engine/invalid-receipt :receipt receipt})))
  (profile/validate-profile (:engine receipt))
  receipt)

(defn validate-checkpoint [checkpoint]
  (when-not (and (map? checkpoint)
                 (nonblank-string? (:database-id checkpoint))
                 (integer? (:epoch checkpoint))
                 (not (neg? (:epoch checkpoint)))
                 (nonblank-string? (:logical-checkpoint-root checkpoint))
                 (nonblank-string? (:physical-root checkpoint)))
    (throw (ex-info "invalid checkpoint receipt"
                    {:type :kotobase.engine/invalid-checkpoint
                     :checkpoint checkpoint})))
  (profile/validate-profile (:engine checkpoint))
  checkpoint)

(defn engine-profile [engine]
  (profile/validate-profile (-engine-profile engine)))

(defn empty-state
  [engine database-id-or-opts]
  (let [opts (if (string? database-id-or-opts)
               {:database-id database-id-or-opts}
               database-id-or-opts)]
    (when-not (nonblank-string? (:database-id opts))
      (throw (ex-info "empty-state requires :database-id"
                      {:type :kotobase.engine/invalid-database-id})))
    (-empty-state engine opts)))

(defn- validate-transact-result [result]
  (when-not (and (map? result) (contains? result :state))
    (throw (ex-info "engine transact result requires :state"
                    {:type :kotobase.engine/invalid-result})))
  (validate-receipt (:receipt result))
  result)

(defn restore-state
  ([engine physical-root] (restore-state engine physical-root {}))
  ([engine physical-root opts]
   (when-not (nonblank-string? physical-root)
     (throw (ex-info "restore-state requires a physical root"
                     {:type :kotobase.engine/invalid-physical-root})))
   (-restore-state engine physical-root opts)))

(defn transact [engine state request]
  (when-not (and (map? request)
                 (nonblank-string? (:database-id request))
                 (nonblank-string? (:request-id request))
                 (sequential? (:tx-data request)))
    (throw (ex-info "transact requires database-id, request-id and tx-data"
                    {:type :kotobase.engine/invalid-transaction-request})))
  (completion/then-result (-transact engine state request)
                          validate-transact-result))

(defn open-snapshot
  ([engine state] (open-snapshot engine state {}))
  ([engine state selector]
   (-open-snapshot engine state (or selector {}))))

(defn scan
  ([engine snapshot pattern] (scan engine snapshot pattern {}))
  ([engine snapshot pattern opts]
   (when-not (and (vector? pattern) (= 3 (count pattern)))
     (throw (ex-info "scan pattern must be [e a v] with nil wildcards"
                     {:type :kotobase.engine/invalid-pattern :pattern pattern})))
   (-scan engine snapshot pattern opts)))

(defn history
  ([engine snapshot] (history engine snapshot {}))
  ([engine snapshot opts] (-history engine snapshot opts)))

(defn checkpoint
  ([engine snapshot] (checkpoint engine snapshot {}))
  ([engine snapshot opts]
   (completion/then-result (-checkpoint engine snapshot opts)
                           validate-checkpoint)))

(defn validate-maintenance-result [result]
  (let [{:keys [state receipt]} result]
    (when-not (and (map? result) (map? state) (map? receipt)
                   (nonblank-string? (:database-id receipt))
                   (nonblank-string? (:before-physical-root receipt))
                   (nonblank-string? (:after-physical-root receipt))
                   (integer? (:work-units receipt))
                   (not (neg? (:work-units receipt)))
                   (#{:completed :noop} (:status receipt)))
      (throw (ex-info "invalid maintenance result"
                      {:type :kotobase.engine/invalid-maintenance-result
                       :result result})))
    (profile/validate-profile (:engine receipt))
    result))

(defn maintain
  "Run real physical maintenance and return {:state :receipt}. This is not an
  alias for checkpoint: a successful receipt names both physical roots and
  the performed work. Engines without IMaintenance fail explicitly."
  ([engine state] (maintain engine state {}))
  ([engine state opts]
   (when-not (satisfies? IMaintenance engine)
     (throw (ex-info "engine does not implement physical maintenance"
                     {:type :kotobase.engine/maintenance-unsupported})))
   (completion/then-result (-maintain engine state (or opts {}))
                           validate-maintenance-result)))
