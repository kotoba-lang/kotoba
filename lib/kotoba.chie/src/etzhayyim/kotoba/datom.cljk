;; etzhayyim.kotoba.datom — EAVT datom model + four-index arrangement.
;;
;; A datom is the canonical [e a v tx op] 5-tuple (ADR-2605312345), matching the
;; on-disk shape already used across 80-data/*/​*-datoms.kotoba.edn (e.g. genome):
;;   ["gene.apc" :genome/kind :gene 1 :add]
;;
;;   e  = entity id     (string or keyword)
;;   a  = attribute     (keyword, namespaced)
;;   v  = value         (any EDN scalar / keyword / string / number / bool)
;;   tx = transaction   (monotonic integer)
;;   op = :add | :retract
;;
;; The four indexes (EAVT / AEVT / AVET / VAET) mirror kotoba-kqe's arrangement
;; so query access patterns port unchanged.

(ns etzhayyim.kotoba.datom)

(defn datom
  "Normalize a tuple/seq into a canonical [e a v tx op] vector."
  ([e a v tx] (datom e a v tx :add))
  ([e a v tx op] [e a v tx op]))

(defn d-e [d] (nth d 0))
(defn d-a [d] (nth d 1))
(defn d-v [d] (nth d 2))
(defn d-tx [d] (nth d 3))
(defn d-op [d] (nth d 4 :add))

(defn assert? [d] (= :add (d-op d)))
(defn retract? [d] (= :retract (d-op d)))

(defn- conj-set [m k x] (update m k (fnil conj #{}) x))

(defn live-datoms
  "Reduce a tx-ordered datom log into the set of currently-live [e a v]
   triples. :add asserts, :retract removes the matching triple. Pure set
   semantics — cardinality-one auto-retraction is applied by the schema layer
   at transaction time, not here. Returns a set of [e a v] vectors."
  [log]
  (reduce (fn [live d]
            (let [t [(d-e d) (d-a d) (d-v d)]]
              (if (assert? d) (conj live t) (disj live t))))
          #{}
          log))

(defn index
  "Build the four-index arrangement over a set of live [e a v] triples.
   Each index maps its leading component(s) to downstream data:
     :eavt  e      -> {a -> #{v}}
     :aevt  a      -> {e -> #{v}}
     :avet  a      -> {v -> #{e}}
     :vaet  v      -> {a -> #{e}}   (reverse / ref navigation)"
  [live]
  (reduce
   (fn [idx [e a v]]
     (-> idx
         (update-in [:eavt e] (fnil conj-set {}) a v)
         (update-in [:aevt a] (fnil conj-set {}) e v)
         (update-in [:avet a] (fnil conj-set {}) v e)
         (update-in [:vaet v] (fnil conj-set {}) a e)))
   {:eavt {} :aevt {} :avet {} :vaet {}}
   live))

(defn live-triples
  "Flatten an index back into the seq of live [e a v] triples."
  [idx]
  (for [[e am] (:eavt idx)
        [a vs] am
        v vs]
    [e a v]))
