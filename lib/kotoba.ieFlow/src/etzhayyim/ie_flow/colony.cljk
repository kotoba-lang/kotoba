(ns etzhayyim.ie-flow.colony
  "etzhayyim.ie-flow.colony — the SYSTEM-OF-SYSTEMS energy balance. ADR-2606212200.

  Each actor is a bounded dissipative system (etzhayyim.ie-flow.boundary) with its own Φ/η/reward.
  The COLONY is the system OF those systems: this namespace folds the bounded actors into one
  aggregate energy balance — total net-gain Φ drawn-and-returned, mean order-index η (共生 across the
  colony), total reward, how many actors are charter-aligned, and a colony-level CONTROL run that
  drives the aggregate reserves to a target (settling/overshoot/error numbers). Pure, deterministic."
  (:require [etzhayyim.ie-flow.reward :as reward]
            [etzhayyim.ie-flow.control :as control]))

(defn balance
  "Aggregate a seq of bounded `actors` (each {:id :state :weights}) into the colony energy balance.
  `opts`: :steps (control horizon, default 12). Returns the colony numbers map. Pure."
  ([actors] (balance actors {}))
  ([actors {:keys [steps] :or {steps 12}}]
   (let [states (mapv :state actors)
         n (count actors)
         sumf (fn [k] (reduce + 0.0 (map #(double (get % k 0)) states)))
         total-phi (sumf :net-gain)
         total-thru (sumf :throughput)
         total-value (sumf :total-value)
         total-cost (sumf :total-cost)
         mean-order (if (pos? n)
                      (/ (reduce + 0.0 (map #(double (:order-index % 0)) states)) n) 0.0)
         rewards (map (fn [{:keys [state weights]}]
                        (:reward (reward/reward-signal state {:weights (or weights reward/default-weights)
                                                              :descendant 0.3 :wellbecoming 0.3})))
                      actors)
         finite (filter #(not (Double/isInfinite (double %))) rewards)
         per (fn [x] (/ (double x) (max 1 steps)))
         ctl (control/control-stock {:init {"reserves" 0}
                                     :inp {"revenue" (per total-value) "cost" (per total-cost)}
                                     :steps steps})]
     {:n n
      :total-phi total-phi
      :total-throughput total-thru
      :mean-order mean-order
      :total-reward (reduce + 0.0 finite)
      :aligned (count (filter #(>= (double %) 0.0) rewards))
      :control {:target (:target ctl) :settling-step (:settling-step ctl)
                :settled? (:settled? ctl) :overshoot-pct (:overshoot-pct ctl)
                :final-error (:final-error ctl)}})))
