(ns kotoba.gitdiff
  "GitOffice Phase 1 (doc e §3-§4 partial) — semantic diff + merge-base/LCA.

   Pure (.cljc). Operates on the element-granular nodes produced by Phase 0
   (gitoffice/body->blocks, grid->cells): a node set is a map {stable-id -> attr-map}.

   - diff-nodes: stable-id keyed diff -> {:added :removed :moved :modified :unchanged}.
     This is the SEMANTIC diff doc e argues for: not text lines but elements keyed by a
     save-stable id (block elementId / cell A1 / shape ocz1:). A move (order-only change)
     is distinguished from a content change; a content change carries per-attribute deltas.
   - doc-nodes / sheet-nodes: lift Phase-0 datoms into node sets.
   - commit-ancestors / merge-base: LCA over a commit DAG {commit -> {:parents [...]}} so a
     3-way merge (Phase 3) has its common base."
  (:require [kotoba.gitoffice :as g]
            [clojure.set :as set]))

;; ---------------------------------------------------------------------------
;; node sets (lift Phase-0 datoms into {stable-id -> attrs})
;; ---------------------------------------------------------------------------

(defn doc-nodes
  "{block-id -> {:kind :text :order :heading-level?}} for one doc."
  [datoms doc-id]
  (->> datoms
       (keep (fn [[e a v]] (when (and (= a :block/parent) (= v doc-id)) e)))
       distinct
       (reduce (fn [m bid]
                 (assoc m bid
                        (cond-> {:kind  (g/v-one datoms bid :block/kind)
                                 :text  (g/v-one datoms bid :block/text)
                                 :order (g/v-one datoms bid :block/order)}
                          (some? (g/v-one datoms bid :block/heading-level))
                          (assoc :heading-level (g/v-one datoms bid :block/heading-level)))))
               {})))

(defn sheet-nodes
  "{cell-id -> {:sheet :ref :row :col :value}} for one book."
  [datoms book-id]
  (->> datoms
       (keep (fn [[e a v]] (when (and (= a :cell/book) (= v book-id)) e)))
       distinct
       (reduce (fn [m cid]
                 (assoc m cid {:sheet (g/v-one datoms cid :cell/sheet)
                               :ref   (g/v-one datoms cid :cell/ref)
                               :row   (g/v-one datoms cid :cell/row)
                               :col   (g/v-one datoms cid :cell/col)
                               :value (g/v-one datoms cid :cell/value)}))
               {})))

;; ---------------------------------------------------------------------------
;; semantic diff
;; ---------------------------------------------------------------------------

(defn- attr-deltas
  "{attr [old new]} for keys that differ between two node attr-maps."
  [o n]
  (into {} (for [k (set/union (set (keys o)) (set (keys n)))
                 :when (not= (get o k) (get n k))]
             [k [(get o k) (get n k)]])))

(defn diff-nodes
  "Diff two node sets keyed by stable id.

   opts :order-key  - attr that encodes sibling order (e.g. :order for docs). When the
                      ONLY differing attr is the order-key, the change is :moved (from->to);
                      otherwise it is :modified (deltas include the order change if any).
                      Omit (or nil) for positional sets like cells (no reorder concept).

   -> {:added    [{:id :node}...]
       :removed  [{:id :node}...]
       :moved    [{:id :from :to}...]
       :modified [{:id :deltas {attr [old new]}}...]
       :unchanged #{id...}}"
  [base head & {:keys [order-key]}]
  (reduce
   (fn [acc id]
     (let [o (get base id) n (get head id)]
       (cond
         (nil? o) (update acc :added conj {:id id :node n})
         (nil? n) (update acc :removed conj {:id id :node o})
         (= o n)  (update acc :unchanged conj id)
         :else
         (let [deltas (attr-deltas o n)]
           (if (and order-key (= (keys deltas) (list order-key)))
             (update acc :moved conj {:id id :from (get o order-key) :to (get n order-key)})
             (update acc :modified conj {:id id :deltas deltas}))))))
   {:added [] :removed [] :moved [] :modified [] :unchanged #{}}
   (sort (set/union (set (keys base)) (set (keys head))))))

(defn diff-doc   [base-datoms head-datoms doc-id]
  (diff-nodes (doc-nodes base-datoms doc-id) (doc-nodes head-datoms doc-id) :order-key :order))
(defn diff-sheet [base-datoms head-datoms book-id]
  (diff-nodes (sheet-nodes base-datoms book-id) (sheet-nodes head-datoms book-id)))

(defn empty-diff?
  "True when nothing changed (only :unchanged populated)."
  [d]
  (every? empty? [(:added d) (:removed d) (:moved d) (:modified d)]))

;; ---------------------------------------------------------------------------
;; commit DAG / merge-base (LCA)
;; ---------------------------------------------------------------------------

(defn commit-ancestors
  "Set of c and all its (transitive) parents in dag {commit {:parents [..]}}."
  [dag c]
  (loop [seen #{} stack [c]]
    (if-let [x (peek stack)]
      (if (seen x)
        (recur seen (pop stack))
        (recur (conj seen x) (into (pop stack) (get-in dag [x :parents]))))
      seen)))

(defn merge-base
  "Best common ancestor(s) of a and b: common commit-ancestors with no other common
   ancestor as a (proper) descendant. Returns a set (may be >1 on criss-cross)."
  [dag a b]
  (let [common (set/intersection (commit-ancestors dag a) (commit-ancestors dag b))]
    (set (remove (fn [x]
                   (some (fn [y] (and (not= x y)
                                      (contains? (disj (commit-ancestors dag y) y) x)))
                         common))
                 common))))

(defn merge-base-1
  "Deterministic single merge-base (sorted first), or nil if histories are disjoint."
  [dag a b]
  (first (sort (merge-base dag a b))))
