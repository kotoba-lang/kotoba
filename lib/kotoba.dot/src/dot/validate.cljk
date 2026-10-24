(ns dot.validate
  "Structural validation of a dot-clj graph model. Pure: returns a vector of problem
  maps `{:dot/severity :error|:warn :dot/code … :dot/id … :dot/msg …}` so a caller
  decides how to surface them. `valid?` is true iff there are no :error-level problems
  (warnings are advisory)."
  (:require [dot.model :as m]))

(defn- problem [severity code id msg]
  {:dot/severity severity :dot/code code :dot/id id :dot/msg msg})

(defn problems
  "Return a vector of structural problems with `g`."
  [g]
  (let [node-ids (set (keys (:dot/nodes g)))
        directed? (:dot/directed g)
        op        (if directed? "->" "--")
        wrong-op  (if directed? "--" "->")
        ps        (transient [])]
    ;; edge operator vs graph kind
    (doseq [{:dot/keys [from to attrs]} (:dot/edges g)]
      (let [edge-id (str from " " op " " to)]
        ;; wrong-operator flag stored by parser in :dot/edge-op
        (when (= wrong-op (get attrs ":dot/edge-op"))
          (conj! ps (problem :error :edge/wrong-operator edge-id
                             (str "edge uses \"" wrong-op "\" but graph is "
                                  (if directed? "directed" "undirected")))))
        ;; self-loop warning
        (when (= from to)
          (conj! ps (problem :warn :edge/self-loop edge-id
                             (str "self-loop on node " from))))))
    ;; dangling refs
    (doseq [{:dot/keys [from to]} (:dot/edges g)]
      (when-not (contains? node-ids from)
        (conj! ps (problem :error :edge/dangling-from (str from "->" to)
                           (str "edge from unknown node " from))))
      (when-not (contains? node-ids to)
        (conj! ps (problem :error :edge/dangling-to (str from "->" to)
                           (str "edge to unknown node " to)))))
    (persistent! ps)))

(defn errors [g] (filterv #(= :error (:dot/severity %)) (problems g)))

(defn valid?
  "True iff `g` has no :error-level structural problems."
  [g]
  (empty? (errors g)))
