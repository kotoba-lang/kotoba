(ns mine-pds
  "KAMI Mine PDS — mining domain PDS primitives: mine registry, mineral
  catalog, extraction history ledger. Restored from the legacy kami-
  engine/kami-mine-pds Rust crate (deleted in kotoba-lang/kami-engine
  PR #82 'Remove Rust workspace from kami-engine') as part of the
  clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. A
  single flat namespace (the original was one flat `lib.rs`, not split
  into `pub mod` blocks). Mutation-returning operations return `[:ok
  ledger']` or `[:error kind ledger]` (ledger unchanged) rather than
  Rust's `Result<(), MinePdsError>`, matching the fidelity pattern used
  elsewhere in this migration (e.g. `power.upf`).")

(def mine-types #{:surface :underground :placer :dredging})
(def mineral-types #{:metallic :non-metallic :energy :gemstone})
(def mine-statuses #{:active :suspended :abandoned :reclaimed})

(defn mine [{:keys [mine-id name mine-type country region status area-hectares operator]}]
  {:mine-id mine-id :name name :mine-type mine-type :country country :region region
   :status status :area-hectares area-hectares :operator operator})

(defn mineral [{:keys [mineral-id name mineral-type chemical-formula]}]
  {:mineral-id mineral-id :name name :mineral-type mineral-type :chemical-formula chemical-formula})

(defn extraction-record [{:keys [record-id mine-id mineral-id period quantity-tons grade]}]
  {:record-id record-id :mine-id mine-id :mineral-id mineral-id :period period
   :quantity-tons quantity-tons :grade grade})

(def error-kinds #{:mine-already-exists :mine-not-found :mineral-already-exists
                    :mineral-not-found :invalid-quantity})

(defn ledger
  "A fresh, empty mine ledger."
  []
  {:mines {} :minerals {} :extraction-records []})

(defn register-mine
  "Register `m` in `ledger`. Returns `[:ok ledger']` or
  `[:error :mine-already-exists ledger]`."
  [ledger m]
  (if (contains? (:mines ledger) (:mine-id m))
    [:error :mine-already-exists ledger]
    [:ok (assoc-in ledger [:mines (:mine-id m)] m)]))

(defn update-mine-status
  "Update the status of mine `mine-id` in `ledger`. Returns `[:ok ledger']`
  or `[:error :mine-not-found ledger]`."
  [ledger mine-id status]
  (if-not (contains? (:mines ledger) mine-id)
    [:error :mine-not-found ledger]
    [:ok (assoc-in ledger [:mines mine-id :status] status)]))

(defn register-mineral
  "Register `m` in `ledger`. Returns `[:ok ledger']` or
  `[:error :mineral-already-exists ledger]`."
  [ledger m]
  (if (contains? (:minerals ledger) (:mineral-id m))
    [:error :mineral-already-exists ledger]
    [:ok (assoc-in ledger [:minerals (:mineral-id m)] m)]))

(defn record-extraction
  "Record `rec` in `ledger` after validating the referenced mine/mineral
  exist and `:quantity-tons` is finite and non-negative. Returns `[:ok
  ledger']` or `[:error kind ledger]`."
  [ledger rec]
  (cond
    (not (contains? (:mines ledger) (:mine-id rec)))
    [:error :mine-not-found ledger]

    (not (contains? (:minerals ledger) (:mineral-id rec)))
    [:error :mineral-not-found ledger]

    (not (and #?(:clj (Double/isFinite (:quantity-tons rec))
                 :cljs (js/isFinite (:quantity-tons rec)))
              (>= (:quantity-tons rec) 0.0)))
    [:error :invalid-quantity ledger]

    :else
    [:ok (update ledger :extraction-records conj rec)]))

(defn get-mine [ledger mine-id] (get (:mines ledger) mine-id))
(defn get-mineral [ledger mineral-id] (get (:minerals ledger) mineral-id))
(defn list-mines [ledger] (vec (vals (:mines ledger))))

(defn extraction-history
  "All extraction records for `mine-id`."
  [ledger mine-id]
  (vec (filter #(= (:mine-id %) mine-id) (:extraction-records ledger))))
