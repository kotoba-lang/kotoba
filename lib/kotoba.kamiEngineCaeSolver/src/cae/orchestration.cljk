(ns cae.orchestration
  "Deterministic orchestration helpers for independent CAE cases.

  The functions here deliberately do not schedule threads or own persistence:
  a host may parallelise a batch or write it to Datom/OpenUSD infrastructure.
  Their responsibility is a stable result envelope and failure isolation, so a
  bad CAD/BIM-derived case never hides the valid simulation results beside it."
  (:require [cae.solver :as solver]))

(defn run-case
  "Run one case and return an envelope instead of throwing solver failures.

  The envelope has `:status` (`:succeeded` or `:failed`), `:case/index`, the
  requested `:solver/kind`, and either `:result` or a data-only `:error` map.
  The original `:case/id`, when supplied, is retained for traceability."
  [case index]
  (let [base (cond-> {:case/index index
                      :solver/kind (get-in case [:solver :kind])}
               (:case/id case) (assoc :case/id (:case/id case)))]
    (try
      (assoc base :status :succeeded :result (solver/solve case))
      (catch #?(:clj Throwable :cljs :default) error
        (assoc base :status :failed
               :error (cond-> {:message (ex-message error)}
                        (ex-data error) (assoc :data (ex-data error))))))))

(defn run-cases
  "Run independent cases in input order with per-case failure isolation.

  `cases` must be sequential. This function intentionally evaluates every
  case; use the returned status rather than exception handling to drive a
  design-space sweep, a factory what-if run, or a host job queue."
  [cases]
  (when-not (sequential? cases)
    (throw (ex-info "CAE batch must be a sequential collection of cases"
                    {:cases cases})))
  (mapv (fn [index case]
          (if (map? case)
            (run-case case index)
            {:case/index index :status :failed
             :error {:message "CAE case must be a map" :data {:case case}}}))
        (range) cases))

(defn successful-results
  "Extract only solved result maps, preserving the batch input order."
  [batch]
  (mapv :result (filter #(= :succeeded (:status %)) batch)))

(defn summary
  "Return stable batch KPIs suitable for a run record or dashboard." 
  [batch]
  (let [statuses (frequencies (map :status batch))]
    {:total (count batch)
     :succeeded (get statuses :succeeded 0)
     :failed (get statuses :failed 0)
     :by-solver (frequencies (map :solver/kind batch))}))
