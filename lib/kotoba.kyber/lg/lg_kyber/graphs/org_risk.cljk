;; orgbrain — 決定論的組織リスク計算 (純関数; LLM をスコアに混入しない).
;; Input: docs/orgbrain/org-ontology.schema.edn の形状の map.
;; Each risk axis returns 0.0 (safe) .. 1.0 (critical). Charter gate: deterministic.
(ns lg.lg-kyber.graphs.org-risk
  (:require [clojure.edn :as edn]))

;; ── schema loading ────────────────────────────────────────────────────────────

(def ^:private node-fs (js/require "fs"))

(defn load-schema
  "Read the org ontology schema. Default is the repo's own docs/orgbrain schema;
  an explicit path (or already-parsed map) wins."
  ([] (load-schema "docs/orgbrain/org-ontology.schema.edn"))
  ([src]
   (cond (map? src) src
         (string? src) (->> (.readFileSync node-fs src "utf8") edn/read-string)
         :else (edn/read src))))

(def default-weights
  {:raci-coverage 0.3 :authority-concentration 0.2 :delegation-depth 0.15
   :single-point-of-failure 0.2 :approval-gap 0.15})

;; ── helpers ───────────────────────────────────────────────────────────────────

(defn- raci-roles [task]
  (let [r (:orgbrain/raci task)]
    (set (mapcat val r))))

(defn- accountable-role [task]
  (first (get-in task [:orgbrain/raci :accountable])))

(defn- authority-holders [schema]
  ;; authority → #{role-id} : direct delegations only
  (reduce (fn [acc d]
            (update acc (:orgbrain/authority d) (fnil conj #{}) (:orgbrain/to-role d)))
          {}
          (:orgbrain/delegations schema)))

(defn- depth-from
  ([delegations role] (depth-from delegations role #{}))
  ([delegations role seen]
   (if (contains? seen role)
     0
     (let [into-role (filter #(= role (:orgbrain/to-role %)) delegations)]
       (if (empty? into-role)
         0
         (inc (apply max (map #(depth-from delegations (:orgbrain/from-role %)
                                         (conj seen role))
                              into-role))))))))

;; ── risk axes ────────────────────────────────────────────────────────────────

(defn raci-coverage-risk
  "Critical tasks with no accountable role. 0 = all covered, 1 = none covered."
  [schema]
  (let [critical (filter :orgbrain/critical? (:orgbrain/tasks schema))]
    (if (empty? critical)
      0.0
      (/ (count (remove accountable-role critical)) (double (count critical))))))

(defn authority-concentration-risk
  "Max share of the authority vocabulary held by a single role (incl. board-level
  delegations received). ≥0.7 of all authorities = 1.0."
  [schema]
  (let [total (count (:orgbrain/authorities schema))
        holders (authority-holders schema)
        per-role (atom {})]
    (doseq [[_auth roles] holders, r roles]
      (swap! per-role update r (fnil inc 0)))
    (if (zero? total)
      0.0
      (min 1.0 (/ (or (apply max (vals @per-role)) 0) (* 0.7 total))))))

(defn delegation-depth-risk
  "Deepest delegation chain /3, capped at 1.0 (≥3 levels from the source role)."
  [schema]
  (let [delegs (:orgbrain/delegations schema)
        roles (set (map :orgbrain/role-id (:orgbrain/roles schema)))
        source-roles (remove (set (map :orgbrain/to-role delegs)) roles)
        deepest (if (empty? delegs)
                  0
                  (apply max 1 (map #(depth-from delegs %)
                                    (set (map :orgbrain/to-role delegs)))))]
    (if (empty? source-roles)
      0.0
      (min 1.0 (/ deepest 3.0)))))

(defn single-point-of-failure-risk
  "Critical tasks whose accountable role has min-headcount 1. Share of critical
  tasks exposed."
  [schema]
  (let [critical (filter :orgbrain/critical? (:orgbrain/tasks schema))
        hc (into {} (map (juxt :orgbrain/role-id :orgbrain/min-headcount)
                         (:orgbrain/roles schema)))]
    (if (empty? critical)
      0.0
      (/ (count (filter #(let [r (accountable-role %)]
                           (and r (<= (get hc r 1) 1)))
                        critical))
         (double (count critical))))))

(defn approval-gap-risk
  "Critical approval authorities (:approve-spend, :sign-contract) that no role holds."
  [schema]
  (let [holders (authority-holders schema)
        required [:approve-spend :sign-contract]
        missing (remove #(seq (get holders %)) required)]
    (/ (count missing) (double (count required)))))

;; ── composite ────────────────────────────────────────────────────────────────

(defn risk-report
  "Full report: each axis 0..1 plus the weighted composite. Deterministic."
  ([schema] (risk-report schema default-weights))
  ([schema weights]
   (let [axes {:raci-coverage (raci-coverage-risk schema)
               :authority-concentration (authority-concentration-risk schema)
               :delegation-depth (delegation-depth-risk schema)
               :single-point-of-failure (single-point-of-failure-risk schema)
               :approval-gap (approval-gap-risk schema)}
         wsum (reduce-kv (fn [a k v] (+ a (get weights k 0))) 0.0 axes)
         composite (if (zero? wsum)
                     0.0
                     (/ (reduce-kv (fn [a k v] (+ a (* v (get weights k 0))))
                                   0.0 axes)
                        wsum))]
     {:axes axes :composite composite :level
      (cond (< composite 0.2) :low
            (< composite 0.5) :moderate
            (< composite 0.8) :elevated
            :else :critical)})))

(defn bpmn-authority-audit
  "Cross-check a BPMN EDN (see docs/orgbrain/incorporation.bpmn.edn) against the
  schema: every :authority-required must be delegated to the task's :actor-role."
  ([bpmn] (bpmn-authority-audit (load-schema) bpmn))
  ([schema bpmn]
   (let [holders (authority-holders schema)]
     (for [el (:orgbrain.bpmn/elements bpmn)
           :when (:authority-required el)
           :let [auth (:authority-required el)
                 role (:actor-role el)]]
       {:element (:id el) :authority auth :role role
        :ok? (contains? (get holders auth #{}) role)}))))
