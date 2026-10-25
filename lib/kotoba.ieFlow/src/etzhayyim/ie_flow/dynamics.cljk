(ns etzhayyim.ie-flow.dynamics
  "ie-flow.dynamics — system-dynamics over the accumulated-order stocks. ADR-2606211200.

  The flow ledger captures the FLOWS (rates); the stocks accumulate ORDER (subscribers, trust,
  data-asset, model-quality, reserves…). Datomic stores the stocks; Clojure evolves them. This is
  the user's `step-system`/`simulate` generalised: a stock map + a per-step inputs map → the next
  stock map, and `simulate` is `reductions` over a sequence of inputs (counterfactual: 施策 before
  vs after). PURE — no I/O, no randomness; a run is reproducible and content-addressable, and is
  persisted to the ledger as a model-run snapshot by the caller."
  (:require [kotoba.lang.text :as str]))

(defn- clamp01 [x] (-> x double (max 0.0) (min 1.0)))

(defn step-system
  "One time-step of the order dynamics (the user's step-system, charter-fitted). `stock` carries
  :customers :trust :data-asset :model-quality :reserves; `inputs` carries the per-step rates
  :acquisition :churn :good-exp :spam :failures :revenue :cost. Trust is bounded [0,1]; reserves
  cannot go negative (0 = death). Returns the next stock. Pure."
  [{:keys [customers trust data-asset model-quality reserves]
    :or {customers 0 trust 0.0 data-asset 0 model-quality 0.0 reserves 0}}
   {:keys [acquisition churn good-exp spam failures revenue cost]
    :or {acquisition 0 churn 0 good-exp 0 spam 0 failures 0 revenue 0 cost 0}}]
  (let [data' (+ (long data-asset) (long acquisition))]
    {:customers (max 0 (+ (long customers) (long acquisition) (- (long churn))))
     :trust (-> (double trust)
                (+ (* 0.01 good-exp))
                (- (* 0.02 spam))
                (- (* 0.05 failures))
                clamp01)
     :data-asset data'
     :model-quality (clamp01 (+ (double model-quality) (* 0.0001 data')))
     :reserves (max 0 (+ (long reserves) (long revenue) (- (long cost))))}))

(defn simulate
  "Evolve `initial` stock through the seq of per-step `inputs`. Returns the trajectory (length
  = (inc (count inputs))), `initial` first — the user's `(reductions step-system …)`. Pure."
  [initial inputs]
  (vec (reductions step-system initial inputs)))

(defn counterfactual
  "Run two trajectories from the same `initial` — `baseline-inputs` vs `intervention-inputs` — and
  return both plus the terminal Δ per stock dimension (the施策 lift, the co-scientist's evidence)."
  [initial baseline-inputs intervention-inputs]
  (let [base (simulate initial baseline-inputs)
        iv   (simulate initial intervention-inputs)
        bt   (peek base)
        it   (peek iv)
        dims (distinct (concat (keys bt) (keys it)))]
    {:baseline base
     :intervention iv
     :delta (into {} (for [k dims]
                       [k (- (double (get it k 0)) (double (get bt k 0)))]))}))
