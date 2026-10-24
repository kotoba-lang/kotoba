(ns dmn.validate
  "Structural validation of a DMN DRG. Pure: returns a vector of problem maps
  `{:dmn/severity :error|:warn :dmn/code … :dmn/id … :dmn/msg …}` so a caller
  decides how to surface them. `valid?` is true iff there are no :error-level
  problems (warnings are advisory)."
  (:require [dmn.model :as m]))

(defn- problem [severity code id msg]
  {:dmn/severity severity :dmn/code code :dmn/id id :dmn/msg msg})

(defn problems
  "Return a vector of structural problems with `graph`."
  [graph]
  (let [decision-ids (set (keys (:dmn/decisions graph)))
        ps           (transient [])]
    (doseq [dec (m/decisions graph)]
      (let [id      (:dmn/id dec)
            inputs  (:dmn/inputs dec)
            outputs (:dmn/outputs dec)
            rules   (:dmn/rules dec)
            hp      (:dmn/hit-policy dec)]
        ;; hit-policy must be in the allowed set
        (when-not (contains? m/hit-policies hp)
          (conj! ps (problem :error :decision/invalid-hit-policy id
                             (str "unknown hit-policy " hp))))
        ;; each :dmn/requires must reference an existing decision
        (doseq [req (:dmn/requires dec)]
          (when-not (contains? decision-ids req)
            (conj! ps (problem :error :decision/unknown-requires id
                               (str "decision " id " requires unknown id " req)))))
        ;; rule arity: when-cells == inputs, then-cells == outputs
        (doseq [rule rules]
          (when (not= (count (:dmn/when rule)) (count inputs))
            (conj! ps (problem :error :rule/when-arity (:dmn/id rule)
                               (str "rule " (:dmn/id rule) " in " id ": "
                                    (count (:dmn/when rule)) " when-cell(s) but "
                                    (count inputs) " input(s)"))))
          (when (not= (count (:dmn/then rule)) (count outputs))
            (conj! ps (problem :error :rule/then-arity (:dmn/id rule)
                               (str "rule " (:dmn/id rule) " in " id ": "
                                    (count (:dmn/then rule)) " then-cell(s) but "
                                    (count outputs) " output(s)")))))
        ;; warn: :unique policy with >1 fully-unconditioned rules
        (when (= hp :unique)
          (let [wildcard? (fn [r] (every? #(= "-" (str %)) (:dmn/when r)))
                n-wild    (count (filter wildcard? rules))]
            (when (> n-wild 1)
              (conj! ps (problem :warn :decision/ambiguous-wildcards id
                                 (str "decision " id " (:unique) has " n-wild
                                      " fully-unconditioned rules — only one can ever fire"))))))))
    ;; DRG acyclicity: check each decision's transitive requirements
    (let [seen-cycle (atom false)]
      (doseq [dec (m/decisions graph)]
        (when-not @seen-cycle
          (try
            (m/topo-order graph (:dmn/id dec))
            (catch #?(:clj clojure.lang.ExceptionInfo :cljs cljs.core/ExceptionInfo) e
              (reset! seen-cycle true)
              (conj! ps (problem :error :drg/cycle (:dmn/id graph)
                                 (str "DRG contains a cycle among: "
                                      (pr-str (:dmn/ids (ex-data e)))))))))))
    (persistent! ps)))

(defn errors [graph] (filterv #(= :error (:dmn/severity %)) (problems graph)))

(defn valid?
  "True iff `graph` has no :error-level structural problems."
  [graph]
  (empty? (errors graph)))
