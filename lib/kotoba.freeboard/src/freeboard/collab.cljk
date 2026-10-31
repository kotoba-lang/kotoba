(ns freeboard.collab
  "Operation-based collaborative editing (pure cljc). Each edit is a serializable
   op carrying its actor + timestamp; the shared op log is **totally ordered** by
   [ts actor seq] and replayed from a base board, so any two clients that have
   seen the same set of ops converge to the same board (LWW on conflicts) —
   independent of receive order. The op log is the thing host adapters sync over
   kotoba. See ADR-2606280200."
  (:require [freeboard.board :as b]))

;; ---- ops -------------------------------------------------------------------
;; {:op/id "uuid" :op/seq n :op/actor "did" :op/ts ms :op/kind :move :op/args {…}}
(defn apply-op
  "Deterministically apply one op to a board. Ops that create items carry the
   item id in their args so replay is reproducible across clients."
  [board {:op/keys [kind args]}]
  (case kind
    :add-item      (b/add-item board (:item args))
    :move          (b/move-item board (:id args) (:dx args) (:dy args))
    :resize        (b/resize-item board (:id args) (:w args) (:h args))
    :delete        (b/delete-item board (:id args))
    :set-text      (b/set-text board (:id args) (:text args))
    :bring-front   (b/bring-to-front board (:id args))
    :add-connector (b/add-item board {:item/id (:id args) :item/kind :connector
                                      :connector/from (:from args) :connector/to (:to args)
                                      :item/x 0 :item/y 0 :item/w 0 :item/h 0 :item/stroke "#888"})
    :add-ink       (b/add-item board (:item args))
    :set-viewport  (assoc board :freeboard/viewport (:viewport args))
    board))

(defn- op-key [op] [(:op/ts op 0) (:op/actor op "") (:op/seq op 0)])

(defn- distinct-by [f coll]
  (let [seen (volatile! #{})]
    (filter (fn [x] (let [k (f x)] (when-not (@seen k) (vswap! seen conj k) true))) coll)))

(defn order
  "Total order over an op log: dedup by :op/id, sort by [ts actor seq]."
  [ops]
  (->> ops (distinct-by :op/id) (sort-by op-key) vec))

(defn merge-logs
  "Convergent merge of op logs → one totally-ordered log."
  [& logs]
  (order (apply concat logs)))

(defn replay
  "Apply an op log (will be ordered) to a base board."
  ([ops] (replay (b/new-board) ops))
  ([base ops] (reduce apply-op base (order ops))))

;; ---- op constructors (client side) ----------------------------------------
(defn op [actor seq kind args]
  {:op/id (str actor "/" seq) :op/seq seq :op/actor actor :op/kind kind :op/args args})
