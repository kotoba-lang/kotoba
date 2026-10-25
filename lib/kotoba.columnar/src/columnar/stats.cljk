(ns columnar.stats
  "Chunk statistics, and the decision that makes an analytic engine fast:
  **can this chunk be skipped without reading it.**

  Everything else here is bookkeeping. A columnar engine's speed does not
  come from reading columns quickly; it comes from not reading them. So this
  namespace is pure, is the most heavily tested part of the library, and
  answers exactly one question per predicate.

  ## Two rules that are easy to get backwards, and dangerous

  **1. Absent statistics never permit a skip.** A column chunk with no
  `min`/`max` — which is normal for a writer that did not record them, and
  for any type without an ordering — must be READ. The tempting shape is
  `(when-let [{:keys [min max]} stats] ...)` guarding the *keep* branch
  instead of the *skip* branch, and the failure is silent: rows vanish from
  answers and everything still looks like it worked.

  **2. Skipping is necessary, not sufficient.** `min`/`max` are bounds, and a
  writer may record wider ones than the data warrants (a page rewritten, a
  merged chunk, a deliberately cheap approximation). So a chunk that survives
  pruning still has to have the predicate applied to it exactly. Pruning
  decides what to read; it never decides what matches.

  ## Predicates

      [:= col v]  [:< col v]  [:<= col v]  [:> col v]  [:>= col v]
      [:in col #{v ...}]  [:is-null col]  [:not-null col]

  A chunk is skipped when ANY predicate in the conjunction proves it cannot
  contain a matching row."
  (:require [columnar.vector :as vec]))

(defn chunk-stats
  "Statistics a source reports for one column chunk.

  `:rows` is required. `:min`/`:max` are optional and their absence is
  meaningful — it means the source is not making a claim, not that the range
  is empty."
  [{:keys [rows nulls min max] :as m}]
  (when-not (and (number? rows) (>= rows 0))
    (throw (ex-info "chunk stats require a non-negative :rows"
                    {:type :columnar/invalid-stats :stats m})))
  (cond-> {:rows rows :nulls (or nulls 0)}
    (contains? m :min) (assoc :min min)
    (contains? m :max) (assoc :max max)))

(defn value-min
  "`min` over `compare`, not over numbers.

  `clojure.core/min` is numeric, and column bounds are not: Parquet records
  byte-order min/max for strings, dates order, and a mixed engine that only
  knew numbers would throw on the most ordinary column in any real file."
  [xs]
  (reduce (fn [a b] (if (neg? (compare b a)) b a)) xs))

(defn value-max [xs]
  (reduce (fn [a b] (if (pos? (compare b a)) b a)) xs))

(defn from-column
  "Exact statistics computed from a column. What a writer would record, and
  what tests compare a source's claims against."
  [col]
  (let [present (remove nil? (keep-indexed (fn [i _] (vec/value-at col i)) (:values col)))]
    (cond-> {:rows (vec/count col) :nulls (vec/null-count col)}
      (seq present) (assoc :min (value-min present) :max (value-max present)))))

(defn- bounded? [stats] (and (contains? stats :min) (contains? stats :max)))
(defn- all-null? [stats] (= (:nulls stats) (:rows stats)))
(defn- no-null? [stats] (zero? (:nulls stats)))

(defn skip-chunk?
  "True when `stats` proves no row in this chunk can satisfy `predicate`.

  False whenever the statistics do not prove it — including every case where
  they are absent. False is always safe; true is a claim."
  [stats [op _col v]]
  (let [{lo :min hi :max} stats]
    (case op
      :is-null  (no-null? stats)
      :not-null (all-null? stats)
      ;; Every remaining predicate needs a non-null row to match, so a chunk
      ;; that is entirely null cannot satisfy any of them.
      (if (all-null? stats)
        true
        (if-not (bounded? stats)
          false
          (case op
            :=  (or (neg? (compare v lo)) (pos? (compare v hi)))
            :<  (not (neg? (compare lo v)))
            :<= (pos? (compare lo v))
            :>  (not (pos? (compare hi v)))
            :>= (neg? (compare hi v))
            :in (not (some (fn [x] (and (not (neg? (compare x lo)))
                                        (not (pos? (compare x hi)))))
                           v))
            ;; An operator this namespace does not understand is not grounds
            ;; to skip anything.
            false))))))

(defn skip?
  "True when any predicate in `predicates` proves the chunk unusable.

  `stats-of` is `(fn [column] stats-or-nil)`. A column the source has no
  statistics for yields nil, and nil never permits a skip."
  [stats-of predicates]
  (boolean
   (some (fn [[_ col :as p]]
           (when-let [s (stats-of col)]
             (skip-chunk? s p)))
         predicates)))

(defn matches?
  "Apply `predicate` to one row of `col` exactly. This is the check that
  pruning does not replace."
  [col i [op _ v]]
  (let [present? (vec/valid-at? col i)
        x (vec/value-at col i)]
    (case op
      :is-null  (not present?)
      :not-null present?
      (boolean
       (and present?
            (case op
              :=  (= x v)
              :<  (neg? (compare x v))
              :<= (not (pos? (compare x v)))
              :>  (pos? (compare x v))
              :>= (not (neg? (compare x v)))
              :in (contains? (set v) x)
              false))))))
