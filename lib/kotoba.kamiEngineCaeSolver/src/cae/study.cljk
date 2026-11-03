(ns cae.study
  "Deterministic design-study helpers over the common CAE case contract.

  These helpers are intentionally solver-agnostic: a host can replace a
  reduced-order method with a high-fidelity adapter and preserve the same sweep
  and sensitivity evidence."
  (:require [cae.orchestration :as orchestration]
            [cae.solver :as solver]))

(defn- finite-number? [value]
  (and (number? value)
       #?(:clj (Double/isFinite (double value))
          :cljs (js/isFinite value))))

(defn parameter-sweep
  "Run `base-case` once per supplied value at nested `path`.

  Results use `cae.orchestration/run-cases`, so a physically invalid point is
  returned as a failed envelope without discarding neighbouring study points.
  Values and their case envelopes remain in input order."
  [base-case path values]
  (when-not (map? base-case)
    (throw (ex-info "CAE study base case must be a map" {:base-case base-case})))
  (when-not (and (vector? path) (seq path) (every? keyword? path))
    (throw (ex-info "CAE study path must be a non-empty vector of keywords" {:path path})))
  (when-not (sequential? values)
    (throw (ex-info "CAE study values must be sequential" {:values values})))
  (let [values (vec values)]
    (when (empty? values)
      (throw (ex-info "CAE study values cannot be empty" {})))
    (mapv (fn [value envelope]
            (assoc envelope :study/path path :study/value value))
          values
          (orchestration/run-cases (mapv #(assoc-in base-case path %) values)))))

(defn- finite-result! [result metric]
  (let [value (get result metric)]
    (when-not (and (contains? result metric) (finite-number? value))
      (throw (ex-info "CAE sensitivity needs a finite result metric"
                      {:metric metric :value value :result result})))
    value))

(defn central-sensitivity
  "Estimate `d result-metric / d input-path` around one case.

  `step` is in the native unit of `input-path`. Both perturbed simulations must
  succeed and yield a finite metric; otherwise the study fails explicitly
  rather than reporting a misleading derivative."
  [case input-path result-metric step]
  (when-not (map? case)
    (throw (ex-info "CAE sensitivity case must be a map" {:case case})))
  (when-not (and (vector? input-path) (seq input-path) (every? keyword? input-path))
    (throw (ex-info "CAE sensitivity input path must be a non-empty vector of keywords"
                    {:input-path input-path})))
  (when-not (keyword? result-metric)
    (throw (ex-info "CAE sensitivity result metric must be a keyword"
                    {:result-metric result-metric})))
  (when-not (and (finite-number? step) (pos? (double step)))
    (throw (ex-info "CAE sensitivity step must be finite and positive" {:step step})))
  (let [at (get-in case input-path)]
    (when-not (finite-number? at)
      (throw (ex-info "CAE sensitivity input value must be finite" {:input-path input-path :value at})))
    (let [minus-case (assoc-in case input-path (- at step))
          plus-case (assoc-in case input-path (+ at step))
          minus-result (solver/solve minus-case)
          plus-result (solver/solve plus-case)
          minus-value (finite-result! minus-result result-metric)
          plus-value (finite-result! plus-result result-metric)]
      (cond-> {:model :central-finite-difference :fidelity :derived
               :input-path input-path :result-metric result-metric
               :at at :step step :minus-value minus-value :plus-value plus-value
               :derivative (/ (- plus-value minus-value) (* 2.0 step))
               :solver (get-in case [:solver :kind])}
        (:case/id case) (assoc :case/id (:case/id case))
        (:case/provenance case) (assoc :case/provenance (:case/provenance case))))))
