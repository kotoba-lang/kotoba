(ns etzhayyim.ie-flow.metrics
  "ie-flow.metrics — the ORDER calculus over an information-energy flow. ADR-2606211200.

  An actor (organism, mirror, concierge, factory…) is a dissipative structure that draws
  free energy from society and is judged by how much LOW-ENTROPY STRUCTURE it returns. This
  namespace turns a stream of measured flow EVENTS (clicks, inferences, payments, agent runs,
  publications…) into the scalar yardsticks the co-scientist reasons over:

    net-gain          Σ (value − cost − risk)          — did the flow pay for itself? (Φ analog)
    order-index       1 − H(after)/H(before)           — was scattered flow RECTIFIED to outcome?
                                                          (秩序化; the negentropy-EXPORT / η analog)
    agent-efficiency  gross-profit / (api+human+fail)   — is the AI a利得 or a課金される魔法陣?

  Faithful to the founding design (the user's Datomic/Clojure sketch): entropy is Shannon over a
  normalised distribution; order-index is the entropy DROP from the raw-flow distribution to the
  realised-value distribution (flow散っている → 成果へ集中 ⇒ high order). EVERYTHING is PURE and
  deterministic (no wall clock, no randomness) so a measurement is content-addressable and a
  tournament reproducible. Stdlib only."
  (:require [kotoba.lang.text :as str]))

;; ── Shannon entropy over a distribution (the user's formulas, verbatim shape) ─

(defn entropy
  "Shannon entropy (natural log) of a probability vector `ps` (zeros ignored). H = −Σ p·ln p."
  [ps]
  (->> ps
       (map double)
       (remove zero?)
       (map (fn [p] (* -1.0 p (Math/log p))))
       (reduce + 0.0)))

(defn normalize
  "Scale a vector of non-negative magnitudes to a probability distribution (sums to 1). An
  all-zero vector is returned unchanged (entropy 0)."
  [xs]
  (let [xs (map double xs)
        s (reduce + 0.0 xs)]
    (if (zero? s) xs (map #(/ % s) xs))))

(defn order-index
  "How much the flow was rectified from its `before` distribution to its `after` distribution.
  1 − H(after)/H(before) ∈ (−∞,1]; high (→1) when scattered input concentrates onto few outcomes
  (秩序化), 0 when no order is added, negative if the flow is DIS-ordered. Pure."
  [before after]
  (let [hb (entropy (normalize before))
        ha (entropy (normalize after))]
    (if (zero? hb) 0.0 (- 1.0 (/ ha hb)))))

;; ── net gain (value − cost − risk) ──────────────────────────────────────────

(defn net-gain
  "Net free-energy gain of one flow/edge: value − cost − risk (all in the same unit, e.g. JPY)."
  [{:keys [value cost risk] :or {value 0 cost 0 risk 0}}]
  (- (double value) (double cost) (double risk)))

(defn total-net-gain
  "Σ net-gain over a seq of flows."
  [flows]
  (reduce (fn [acc f] (+ acc (net-gain f))) 0.0 flows))

;; ── agent efficiency (the「課金される魔法陣」test) ───────────────────────────

(defn agent-efficiency
  "Gross profit per unit of total agent cost (api + human-handhold + failure). >1 利得, =1 トントン,
  <1 the agent is itself a dissipation source (a paid magic-circle). ∞ when costless (degenerate)."
  [{:keys [gross-profit api-cost human-cost failure-cost]
    :or {gross-profit 0 api-cost 0 human-cost 0 failure-cost 0}}]
  (let [den (+ (double api-cost) (double human-cost) (double failure-cost))]
    (if (zero? den)
      ##Inf
      (/ (double gross-profit) den))))

;; ── flow aggregation: events → edges (the Sankey backbone) ──────────────────

(defn aggregate-flows
  "Group measured flow EVENTS into edges. Each event is a map with at least :source :target
  :type and optional :volume :cost :value :risk. Returns a vector of edge maps
  {:source :target :type :volume :cost :value :risk :count}, summed, deterministically ordered."
  [events]
  (->> events
       (group-by (juxt :source :target :type))
       (map (fn [[[s t ty] es]]
              {:source s :target t :type ty
               :count  (count es)
               :volume (reduce + 0.0 (map #(double (:volume % 0)) es))
               :cost   (reduce + 0.0 (map #(double (:cost % 0)) es))
               :value  (reduce + 0.0 (map #(double (:value % 0)) es))
               :risk   (reduce + 0.0 (map #(double (:risk % 0)) es))}))
       (sort-by (fn [e] [(str (:source e)) (str (:target e)) (str (:type e))]))
       vec))

(defn- magnitudes [flows k] (map #(max 0.0 (double (get % k 0))) flows))

;; ── the IE-flow STATE VECTOR (SENSE output the lifecycle folds over) ─────────

(defn flow-state
  "Fold measured flow EVENTS into the deterministic IE-flow state vector — the SENSE reading the
  co-scientist react loop reasons over. PURE. Optional `agent-costs` (a map with :gross-profit
  :api-cost :human-cost :failure-cost summed over the agent's own runs) feeds agent-efficiency;
  absent → derived from the flows whose :source/:target is an agent node (:agent? true on the edge).

  returns {:edges :flows-n :net-gain :total-value :total-cost :total-risk :throughput
           :order-index :agent-efficiency :parasitic?}.

    order-index = entropy drop from the VOLUME distribution (how the raw flow was spread) to the
                  VALUE distribution (where realised value concentrated) — the 整流 / negentropy-
                  export axis. parasitic? = net-gain < 0 (the flow took more order than it returned)."
  ([events] (flow-state events {}))
  ([events {:keys [agent-costs]}]
   (let [edges (aggregate-flows events)
         net   (total-net-gain edges)
         tv    (reduce + 0.0 (magnitudes edges :value))
         tc    (reduce + 0.0 (magnitudes edges :cost))
         tr    (reduce + 0.0 (magnitudes edges :risk))
         thru  (reduce + 0.0 (magnitudes edges :volume))
         oi    (order-index (magnitudes edges :volume) (magnitudes edges :value))
         ac    (or agent-costs
                   (let [ae (filter :agent? edges)]
                     {:gross-profit (reduce + 0.0 (magnitudes ae :value))
                      :api-cost     (reduce + 0.0 (magnitudes ae :cost))
                      :human-cost   0
                      :failure-cost (reduce + 0.0 (magnitudes ae :risk))}))
         aeff  (agent-efficiency ac)]
     {:edges edges
      :flows-n (count edges)
      :net-gain net
      :total-value tv
      :total-cost tc
      :total-risk tr
      :throughput thru
      :order-index oi
      :agent-efficiency aeff
      :parasitic? (neg? net)})))

(defn summary-line
  "One-line human summary of a flow-state. Pure."
  [{:keys [flows-n net-gain order-index agent-efficiency throughput]}]
  (str flows-n " edges · throughput=" (long throughput)
       " · net-gain=" (format "%.1f" (double net-gain))
       " · order-index=" (format "%.3f" (double order-index))
       " · agent-eff=" (if (Double/isInfinite (double agent-efficiency))
                         "∞" (format "%.2f" (double agent-efficiency)))))
