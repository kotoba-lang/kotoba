(ns dot.emit
  "Concise EDN hiccup-style emitter for Graphviz DOT."
  (:require [kotoba.lang.text :as str]))

(defn- id [x] (if (keyword? x) (name x) (str x)))

(defn- aval [v]
  (cond
    (string? v) (str \" (-> v (str/replace "\\" "\\\\") (str/replace "\"" "\\\"")) \")
    (keyword? v) (name v)
    :else (str v)))

(defn- attrs [m]
  (when (seq m)
    (str " [" (str/join ", " (for [[k v] m] (str (name k) "=" (aval v)))) "]")))

(declare stmt)

(defn- block [stmts]
  (str/join "\n" (map #(str "  " (str/replace (stmt %) "\n" "\n  ")) stmts)))

(defn stmt
  "Compile one EDN statement to a DOT statement string."
  [form]
  (let [[op & more] form]
    (case op
      :node (str "node" (attrs (first more)) ";")
      :edge (str "edge" (attrs (first more)) ";")
      :graph-attr (str/join "\n" (for [[k v] (first more)] (str (name k) "=" (aval v) ";")))
      :n (str (id (first more)) (attrs (second more)) ";")
      :-> (str (id (first more)) " -> " (id (second more)) (attrs (nth more 2 nil)) ";")
      :-- (str (id (first more)) " -- " (id (second more)) (attrs (nth more 2 nil)) ";")
      :subgraph (let [[nm & body] more] (str "subgraph " (id nm) " {\n" (block body) "\n}"))
      (str (id op) (attrs (first more)) ";"))))

(defn dot
  "Compile a graph: kind (:digraph/:graph), optional name, then statements."
  [kind name & stmts]
  (str (clojure.core/name kind) (when name (str " " (id name))) " {\n" (block stmts) "\n}"))
