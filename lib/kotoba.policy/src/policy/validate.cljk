(ns policy.validate
  "Structural validation of a policy-as-EDN model. Pure: returns a vector of problem
  maps `{:policy/severity :error|:warn :policy/code … :policy/id … :policy/msg …}`
  so a caller decides how to surface them. `valid?` is true iff there are no
  :error-level problems (warnings are advisory)."
  (:require [kotoba.dsl.problem :as problem]
            [policy.model :as m]))

(defn- policy-problem [severity code id msg]
  (problem/problem :policy severity code id msg))

(defn- validate-cond
  "Recursively validate a condition tree; returns a (possibly empty) seq of problems."
  [cond-expr rule-id]
  (cond
    (nil? cond-expr)
    []  ; no condition — unconditional rule, valid

    (contains? cond-expr :policy/and)
    (mapcat #(validate-cond % rule-id) (:policy/and cond-expr))

    (contains? cond-expr :policy/or)
    (mapcat #(validate-cond % rule-id) (:policy/or cond-expr))

    (contains? cond-expr :policy/not)
    (validate-cond (:policy/not cond-expr) rule-id)

    (contains? cond-expr :policy/attr)
    (if (contains? m/ops (:policy/op cond-expr))
      []
      [(policy-problem :error :rule/unknown-op rule-id
                (str "unknown op " (:policy/op cond-expr) " in rule " rule-id))])

    :else
    [(policy-problem :warn :rule/unrecognized-cond rule-id
              (str "unrecognized condition shape in rule " rule-id))]))

(defn problems
  "Return a vector of structural problems with `pol`."
  [pol]
  (let [ps (transient [])]
    ;; combining algorithm must be known
    (when-not (contains? m/algorithms (:policy/algorithm pol))
      (conj! ps (policy-problem :error :policy/unknown-algorithm (:policy/id pol)
                         (str "unknown algorithm " (:policy/algorithm pol)))))
    ;; validate each rule
    (doseq [rule (:policy/rules pol)]
      (let [rid (:policy/id rule)]
        ;; effect must be :allow or :deny
        (when-not (contains? m/effects (:policy/effect rule))
          (conj! ps (policy-problem :error :rule/unknown-effect rid
                             (str "rule " rid " has unknown effect " (:policy/effect rule)))))
        ;; validate the condition tree
        (doseq [p (validate-cond (:policy/when rule) rid)]
          (conj! ps p))))
    (persistent! ps)))

(defn errors [pol] (problem/errors :policy (problems pol)))

(defn valid?
  "True iff `pol` has no :error-level structural problems."
  [pol]
  (problem/valid? :policy (problems pol)))
