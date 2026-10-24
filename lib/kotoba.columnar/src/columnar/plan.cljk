(ns columnar.plan
  "Decide what not to read, then read it.

  Two properties this namespace is built around, both of them things a scan
  can get wrong while still looking right:

  - **A column is read only if the query needs it.** The columns in the
    predicates and the columns in the projection, and nothing else. On a wide
    table this is most of the saving, and it is invisible in the answer.
  - **A chunk is read only if statistics could not rule it out.** And when
    they could not, the predicate is still applied exactly — pruning decides
    what to read, never what matches (`columnar.stats`).

  `scan` reports `:chunks-read` and `:chunks-skipped` alongside the rows. Not
  telemetry: a caller cannot otherwise distinguish a plan that pruned from
  one that read everything and filtered, because both produce the same rows."
  (:require [columnar.source :as src]
            [columnar.stats :as stats]
            [columnar.vector :as vec]))

(defn- needed-columns
  "Projection ∪ predicate columns. Reading a column the query does not
  mention is the most common way a columnar scan quietly becomes a row scan."
  [schema columns predicates]
  (let [known (set schema)
        wanted (if (seq columns) columns schema)
        pred-cols (map second predicates)
        unknown (remove known (concat wanted pred-cols))]
    (when (seq unknown)
      (throw (ex-info "column not in schema"
                      {:type :columnar/unknown-column
                       :unknown (vec (distinct unknown)) :schema (vec schema)})))
    (distinct (concat wanted pred-cols))))

(defn scan
  "Rows matching `:predicates`, projected to `:columns`.

  Returns `{:rows [...] :chunks-read n :chunks-skipped n}`. Each row is a map
  of column name to value, plus the global row number under `:row-key`
  (default `::row`) — global so a caller can address a row without knowing
  how the source chunked it."
  [source {:keys [columns predicates row-key] :or {predicates [] row-key ::row}}]
  (let [schema (src/-schema source)
        project (vec (if (seq columns) columns schema))
        to-read (needed-columns schema columns predicates)
        n (src/-chunk-count source)]
    (loop [chunk 0 offset 0 acc [] read 0 skipped 0]
      (if (= chunk n)
        {:rows acc :chunks-read read :chunks-skipped skipped}
        (let [rows (src/-chunk-rows source chunk)
              skip? (stats/skip? #(src/-chunk-stats source chunk %) predicates)]
          (if skip?
            ;; Not one column read for this chunk, and the row numbers still
            ;; line up because `-chunk-rows` is metadata.
            (recur (inc chunk) (+ offset rows) acc read (inc skipped))
            (let [cols (into {} (map (fn [c] [c (src/-read-column source chunk c)])) to-read)
                  keep-idx (filter (fn [i]
                                     (every? (fn [[_ c _ :as p]]
                                               (stats/matches? (get cols c) i p))
                                             predicates))
                                   (range rows))
                  new-rows (mapv (fn [i]
                                   (into {row-key (+ offset i)}
                                         (map (fn [c] [c (vec/value-at (get cols c) i)]))
                                         project))
                                 keep-idx)]
              (recur (inc chunk) (+ offset rows) (into acc new-rows)
                     (inc read) skipped))))))))

(defn select
  "`scan` shaped for `kotobase.lake.tabular/ITabularEngine`.

  `request` is `{:columns [..] :row n-or-nil :filters [[col value] ..]
  :predicates [[op col v] ..]}`.
  Equality filters become `[:= col v]` predicates and are concatenated
  with `:predicates` so a value interval can prune via `columnar.stats`.
  A bound row becomes a row-number restriction — which prunes chunks too,
  because a row number names a chunk.

  Kept here rather than in the consumer so the translation has one home,
  and dependency-free: the row key travels as an argument rather than this
  library depending on the namespace that owns it."
  [source {:keys [columns row filters predicates]} row-key]
  (let [preds (into (mapv (fn [[c v]] [:= c v]) (or filters []))
                    (or predicates []))
        {:keys [rows] :as result} (scan source {:columns columns
                                                :predicates preds
                                                :row-key row-key})]
    (assoc result :rows (if (some? row)
                          (filterv #(= row (get % row-key)) rows)
                          rows))))
