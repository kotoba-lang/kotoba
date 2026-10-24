(ns columnar.aggregate
  "Aggregates, answered from statistics when the statistics are enough.

  `SELECT count(*)` and `SELECT max(price)` over a file the writer described
  honestly need to read **no data at all** — the answer is already in the
  footer. That is the single most visible thing an analytic engine does, and
  it is why `:read` is reported alongside every result: a caller can see
  whether the file's metadata earned its keep.

  ## When statistics are NOT enough, and the guards are the whole namespace

  - **Any predicate disqualifies them.** Chunk bounds describe every row in
    the chunk, and a filter selects some of them. `max(price)` over the whole
    chunk says nothing about `max(price) where region = 'east'`, and the
    tempting shortcut — prune chunks, then fold their bounds — is wrong for
    exactly the surviving chunks, which contain both matching and
    non-matching rows.
  - **One chunk without bounds disqualifies them all.** A fold over the
    chunks that *did* report bounds silently answers about a subset of the
    file. Absent statistics mean no claim, never an empty range.
  - **`sum` is never available.** min/max/rows/nulls cannot produce it. It is
    listed here so that its absence is a decision rather than an oversight.

  All-null chunks are skipped when folding min/max: they have no value to
  contribute, and `nil` is not a small number."
  (:require [columnar.plan :as plan]
            [columnar.stats :as stats]
            [columnar.source :as src]))

(def from-statistics
  "Aggregates that chunk metadata can answer outright, absent a predicate."
  #{:count :count-non-null :min :max})

(defn- chunk-stats-seq [source column]
  (map #(src/-chunk-stats source % column) (range (src/-chunk-count source))))

(defn- all-null? [s] (= (:nulls s) (:rows s)))

(defn- try-statistics [source {:keys [agg column]}]
  (let [n (src/-chunk-count source)]
    (case agg
      :count {:value (reduce + 0 (map #(src/-chunk-rows source %) (range n)))
              :from :statistics :read 0}
      (:count-non-null :min :max)
      (let [ss (chunk-stats-seq source column)]
        (when (every? some? ss)
          (case agg
            :count-non-null {:value (reduce + 0 (map #(- (:rows %) (:nulls %)) ss))
                             :from :statistics :read 0}
            (let [usable (remove all-null? ss)
                  k (if (= agg :min) :min :max)]
              (when (every? #(contains? % k) usable)
                {:value (when (seq usable)
                          ((if (= agg :min) stats/value-min stats/value-max) (map k usable)))
                 :from :statistics :read 0})))))
      nil)))

(defn- fold-rows [agg column rows]
  (let [vs (remove nil? (map #(get % column) rows))]
    (case agg
      :count (count rows)
      :count-non-null (count vs)
      :min (when (seq vs) (stats/value-min vs))
      :max (when (seq vs) (stats/value-max vs))
      :sum (reduce + 0 vs)
      (throw (ex-info "unknown aggregate" {:type :columnar/unknown-aggregate :agg agg})))))

(defn aggregate
  "`{:agg :count|:count-non-null|:min|:max|:sum :column c :predicates [...]}`.

  Returns `{:value v :from :statistics|:scan :read n}`, where `:read` is the
  number of chunks whose data was touched — 0 when the footer sufficed."
  [source {:keys [agg column predicates] :as request}]
  (or (when (empty? predicates)
        (when (contains? from-statistics agg)
          (try-statistics source request)))
      (let [{:keys [rows chunks-read]}
            (plan/scan source {:columns (when column [column])
                               :predicates (or predicates [])})]
        {:value (fold-rows agg column rows) :from :scan :read chunks-read})))
