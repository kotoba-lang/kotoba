(ns kotobase.engine.memory
  "Zero-dependency correctness oracle for the engine contract."
  (:require [kotobase.engine.canonical :as canonical]
            [kotobase.engine.contract :as contract]
            [kotobase.engine.profile :as profile]))

(defn- digest [engine x]
  ((:digest-fn engine) (canonical/canonical-string x)))

(defn- digest-canonical-string [engine canonical-string]
  ((:digest-fn engine) canonical-string))

(defn- rows-at [state basis-t]
  (->> (:history state)
       (filter #(<= (:t %) basis-t))
       (reduce (fn [rows {:keys [e a v added] :as d}]
                 (let [k (canonical/logical-datom-key d)]
                   (if added
                     (assoc rows k {:e e :a a :v v :t (:t d) :added true})
                     (dissoc rows k))))
               {})
       vals
       canonical/canonical-datoms))

(defn- physical-root [engine state]
  (str "memory:" (digest engine (:history state))))

(defn- matches? [[pe pa pv] {:keys [e a v]}]
  (and (or (nil? pe) (= pe e))
       (or (nil? pa) (= pa a))
       (or (nil? pv) (= pv v))))

(defrecord MemoryEngine [digest-fn]
  contract/IEngine
  (-engine-profile [_] profile/memory)

  (-empty-state [_ {:keys [database-id]}]
    {:database-id database-id :basis-t 0 :history [] :requests {}})

  (-restore-state [_ _ _]
    (throw (ex-info "memory oracle has no durable physical store"
                    {:type :kotobase.engine/unsupported-operation
                     :operation :restore-state})))

  (-transact [this state {:keys [database-id request-id tx-data]}]
    (when-not (= database-id (:database-id state))
      (throw (ex-info "transaction database does not match state"
                      {:type :kotobase.engine/database-mismatch})))
    (let [tx (canonical/normalize-tx tx-data)
          tx-root (digest-canonical-string
                   this (canonical/transaction-string tx))]
      (if-let [prior (get-in state [:requests request-id])]
        (if (= tx-root (:tx-root prior))
          {:state state :receipt (assoc (:receipt prior) :status :replayed)}
          (throw (ex-info "request-id was already used for different transaction bytes"
                          {:type :kotobase.engine/idempotency-conflict
                           :request-id request-id})))
        (let [t (inc (:basis-t state))
              appended (mapv (fn [{:keys [e a v op]}]
                               {:e e :a a :v v :t t :added (= :assert op)})
                             tx)
              next-state (-> state
                             (assoc :basis-t t)
                             (update :history into appended))
              receipt {:database-id database-id
                       :epoch t
                       :request-id request-id
                       :tx-root tx-root
                       :physical-root (physical-root this next-state)
                       :engine profile/memory
                       :status :committed}
              stored {:tx-root tx-root :receipt receipt}]
          {:state (assoc-in next-state [:requests request-id] stored)
           :receipt receipt}))))

  (-open-snapshot [_ state selector]
    (let [basis (:basis-t state)
          as-of (get selector :as-of basis)]
      (when-not (and (integer? as-of) (<= 0 as-of basis))
        (throw (ex-info "snapshot :as-of is outside the database basis"
                        {:type :kotobase.engine/invalid-snapshot-selector
                         :selector selector :basis basis})))
      {:state state
       :database-id (:database-id state)
       :basis-t as-of
       :history? (true? (:history selector))}))

  (-scan [_ {:keys [state basis-t history?]} pattern _opts]
    (let [rows (if history?
                 (->> (:history state)
                      (filter #(<= (:t %) basis-t))
                      canonical/canonical-datoms)
                 (rows-at state basis-t))]
      (->> rows (filter #(matches? pattern %)) vec)))

  (-history [_ {:keys [state basis-t]} _opts]
    (->> (:history state)
         (filter #(<= (:t %) basis-t))
         canonical/canonical-datoms))

  (-checkpoint [this {:keys [state database-id basis-t]} _opts]
    (let [rows (rows-at state basis-t)
          snapshot-state (-> state
                             (assoc :basis-t basis-t)
                             (update :history
                                     (fn [history]
                                       (filterv #(<= (:t %) basis-t) history))))]
      {:database-id database-id
       :epoch basis-t
       :logical-checkpoint-root
       (digest-canonical-string this (canonical/checkpoint-string rows))
       :physical-root (physical-root this snapshot-state)
       :engine profile/memory})))

(defn memory-engine
  "Create the oracle. `digest-fn` accepts one canonical string and must return
  a nonblank string. Production users should inject a cryptographic digest;
  tests may inject an identity-labelled oracle."
  [digest-fn]
  (when-not (ifn? digest-fn)
    (throw (ex-info "memory-engine requires digest-fn"
                    {:type :kotobase.engine/missing-digest})))
  (->MemoryEngine digest-fn))
