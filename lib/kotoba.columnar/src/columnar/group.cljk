(ns columnar.group
  "GROUP BY: aggregates per distinct key, over chunks the predicates could not
  rule out.

  `columnar.aggregate` answers about a whole source and can often do it from
  metadata alone. Grouping cannot: the answer has one row per distinct key, and
  no format records which keys occur in which chunk. So this namespace always
  reads the grouping columns of every surviving chunk, and its saving is the
  same one the rest of the library is built on — the chunks the predicates
  pruned, and the columns the query never mentioned.

  That is worth stating rather than leaving to be discovered from a profile:
  **there is no metadata shortcut for GROUP BY**, and a caller who expects
  `:read 0` the way `count` delivers it is going to be disappointed by physics
  rather than by this implementation.

  ## Decisions that are easy to make silently, and shouldn't be

  1. **A null key is a group.** Grouping by a column with nulls puts them
     together under `nil` rather than dropping those rows. Dropping is the
     other defensible choice and it is the one that loses data without saying
     so, which is why this one is written down.
  2. **Output order is first appearance, not hash order.** A hash map's seq
     order is unspecified and varies by key set and by runtime, so a grouped
     result would differ between the JVM and ClojureScript for the same input.
     That makes tests flaky and diffs meaningless. First-appearance order is
     deterministic, costs one insertion-ordered accumulator, and is stable
     across runtimes.
  3. **`sum`/`min`/`max` skip nulls; `count` counts rows; `count-non-null`
     counts values.** The distinction is the whole reason both counts exist —
     `count` of a group is how many rows are in it, which is not how many of
     them had a value in the aggregated column.
  4. **`avg` is absent.** It would have to decide integer-vs-ratio division and
     what an all-null group averages to, and a caller who computes
     `sum / count-non-null` themselves has made that decision explicitly. Its
     absence is a decision rather than an oversight.

  ## What this does NOT close

  Aggregate **pushdown into the format** — asking Parquet for a per-row-group
  partial sum instead of reading the pages. Nothing here reaches below
  `IColumnSource`, which by design exposes chunks and columns and not
  arithmetic."
  (:require [columnar.plan :as plan]
            [columnar.source :as src]
            [columnar.stats :as stats]
            [columnar.vector :as vec]))

(def aggregates
  "The reductions a group can be folded with."
  #{:count :count-non-null :sum :min :max})

(defn- step
  "Fold one value into an accumulator. `v` is nil for a null."
  [agg acc v]
  (case agg
    :count (inc (or acc 0))
    :count-non-null (if (nil? v) (or acc 0) (inc (or acc 0)))
    :sum (if (nil? v) (or acc 0) (+ (or acc 0) v))
    :min (cond (nil? v) acc
               (nil? acc) v
               :else (stats/value-min [acc v]))
    :max (cond (nil? v) acc
               (nil? acc) v
               :else (stats/value-max [acc v]))))

(defn- initial [agg]
  ;; count and sum have a zero; min and max of nothing is nil, not a large
  ;; number, and must stay distinguishable from a real value.
  (case agg (:count :count-non-null :sum) 0 nil))

(defn- validate! [schema group-cols specs]
  (let [known (set schema)
        unknown (remove known (concat group-cols (keep :column specs)))]
    (when (seq unknown)
      (throw (ex-info "column not in schema"
                      {:type :columnar/unknown-column
                       :unknown (vec (distinct unknown)) :schema (vec schema)})))
    (doseq [{:keys [agg column as]} specs]
      (when-not (contains? aggregates agg)
        (throw (ex-info (str "unknown aggregate " (pr-str agg))
                        {:type :columnar/unknown-aggregate :agg agg
                         :known aggregates})))
      (when (and (not= agg :count) (nil? column))
        (throw (ex-info (str (pr-str agg) " needs a :column")
                        {:type :columnar/aggregate-needs-column :agg agg :as as}))))))

(defn group
  "`{:group-by [col ...] :aggs [{:as name :agg k :column col} ...] :predicates [...]}`

  Returns `{:rows [...] :chunks-read n :chunks-skipped n}`, one row per
  distinct key, each row carrying the grouping columns under their own names
  and each aggregate under its `:as`.

  Grouping by nothing is legal and yields exactly one row — the whole-source
  aggregate, which is what `SELECT sum(x) FROM t` means. An empty source
  yields no rows even then, because there is no group to report."
  [source {:keys [group-by aggs predicates] :or {group-by [] aggs [] predicates []}}]
  (let [schema (src/-schema source)
        specs (vec aggs)
        _ (validate! schema group-by specs)
        ;; Exactly the columns the query mentions: keys, aggregated values, and
        ;; whatever the predicates need to be applied exactly.
        to-read (distinct (concat group-by (keep :column specs) (map second predicates)))
        n (src/-chunk-count source)]
    (loop [chunk 0, order [], acc {}, read 0, skipped 0]
      (if (= chunk n)
        {:rows (mapv (fn [k]
                       (into (zipmap group-by k)
                             (map (fn [{:keys [as agg]}]
                                    [as (get-in acc [k as] (initial agg))]))
                             specs))
                     order)
         :chunks-read read
         :chunks-skipped skipped}
        (let [rows (src/-chunk-rows source chunk)]
          (if (stats/skip? #(src/-chunk-stats source chunk %) predicates)
            (recur (inc chunk) order acc read (inc skipped))
            (let [cols (into {} (map (fn [c] [c (src/-read-column source chunk c)])) to-read)
                  keep-idx (filter (fn [i]
                                     (every? (fn [[_ c _ :as p]]
                                               (stats/matches? (get cols c) i p))
                                             predicates))
                                   (range rows))
                  [order' acc']
                  (reduce
                   (fn [[o a] i]
                     (let [k (mapv (fn [c] (vec/value-at (get cols c) i)) group-by)
                           seen? (contains? a k)
                           a' (reduce (fn [m {:keys [as agg column]}]
                                        (update-in m [k as]
                                                   #(step agg (if (some? %) % (initial agg))
                                                          (when column
                                                            (vec/value-at (get cols column) i)))))
                                      (if seen? a (assoc a k {}))
                                      specs)]
                       [(if seen? o (conj o k)) a']))
                   [order acc] keep-idx)]
              (recur (inc chunk) order' acc' (inc read) skipped))))))))

(defn group-rows
  "`group` over rows already in hand, for a caller holding `plan/scan` output.

  Same folding and the same first-appearance ordering, so a grouped scan and a
  grouped source agree."
  [rows {:keys [group-by aggs] :or {group-by [] aggs []}}]
  (let [specs (vec aggs)]
    (loop [rs rows, order [], acc {}]
      (if-let [r (first rs)]
        (let [k (mapv #(get r %) group-by)
              seen? (contains? acc k)
              acc' (reduce (fn [m {:keys [as agg column]}]
                             (update-in m [k as]
                                        #(step agg (if (some? %) % (initial agg))
                                               (when column (get r column)))))
                           (if seen? acc (assoc acc k {}))
                           specs)]
          (recur (rest rs) (if seen? order (conj order k)) acc'))
        (mapv (fn [k]
                (into (zipmap group-by k)
                      (map (fn [{:keys [as agg]}] [as (get-in acc [k as] (initial agg))]))
                      specs))
              order)))))

(defn scan-and-group
  "Convenience: `plan/scan` then `group-rows`.

  Kept distinct from `group` because it is **not** the same computation —
  it materialises every surviving row before folding, where `group` folds as
  it reads. Use it when the rows are wanted for something else anyway."
  [source request]
  (let [{:keys [rows chunks-read chunks-skipped]}
        (plan/scan source {:columns (distinct (concat (:group-by request)
                                                      (keep :column (:aggs request))))
                           :predicates (or (:predicates request) [])
                           :row-key ::row})]
    {:rows (group-rows rows request)
     :chunks-read chunks-read
     :chunks-skipped chunks-skipped}))
