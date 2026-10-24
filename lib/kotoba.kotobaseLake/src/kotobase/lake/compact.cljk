(ns kotobase.lake.compact
  "The small-file problem: N files that should be one.

  A lake accumulates files because writers land them — one per batch, one per
  hour, one per correction. Query cost is per file (a footer, a range read, a
  plan) so a thousand tiny files cost a thousand times what one costs to
  answer the same question. Compaction rewrites a group of them as one.

  ## What this namespace does, and what it deliberately does not

  It **plans** and it **commits**. It does not move bytes: `kotobase.lake`
  never does I/O, and the caller already holds the readers and writers that
  would do the rewrite. So the shape is

      plan  ->  caller rewrites the group into one object  ->  commit

  and the two ends are this namespace's, because both are the parts that are
  easy to get wrong in a way nothing notices.

  ## Only members with identical partition values may be grouped

  `region=east/part-0` and `region=west/part-1` cannot become one file.
  Partition values live in the path, not in the data, so merging across them
  either loses the value or forces it to become a column — and the first is
  data loss while the second silently changes the table's schema.

  ## Compaction is the operation that can silently lose rows

  Every other thing here fails loudly. A rewrite that drops a row produces a
  file that opens, parses, and answers queries — with less in it. Nothing
  downstream can tell, because there is no record of what should have been
  there except the manifest of the files being replaced.

  So `verify-replacement!` is not a nicety: it is the reason the commit is a
  function rather than a note in a runbook. The replacement must account for
  **every row** of what it replaces, and its bounds must **contain** theirs.
  Bounds may be wider — `columnar.stats` rule 2 says statistics are bounds and
  a writer may record loose ones — but narrower means values went missing, and
  a row count that disagrees means it happened even where the bounds did not
  notice.

  ## The commit is a new snapshot, never a mutation

  Which is why this could not be written before `kotobase.lake.table` had
  snapshots. Removing the old members and adding the new one as an edit would
  leave the table inconsistent in between and offer no way back; as a snapshot
  it is atomic, and the previous snapshot keeps answering exactly what it
  answered."
  (:require [kotobase.lake.table :as table]))

(defn merged-statistics
  "Statistics the merged file must report, folded from the group's.

  min/max/nulls/rows all compose: the merged minimum is the least of the
  minima, and so on. A column that any member makes no claim about is a column
  the merged file cannot be checked on, so its bounds are dropped rather than
  guessed from the members that did report."
  [members]
  (let [cols (into #{} (mapcat (comp keys :statistics)) members)]
    (into {}
          (map (fn [col]
                 (let [ss (map #(get-in % [:statistics col]) members)]
                   [col (cond-> {:nulls (reduce + 0 (map #(or (:nulls %) 0) ss))}
                          ;; Only when EVERY member bounded it. One member
                          ;; without bounds makes the merged bound unknowable,
                          ;; and inventing it from the rest would be a claim
                          ;; about rows nobody described.
                          (every? #(contains? % :min) ss)
                          (assoc :min (reduce (fn [a b] (if (neg? (compare b a)) b a))
                                              (map :min ss)))
                          (every? #(contains? % :max) ss)
                          (assoc :max (reduce (fn [a b] (if (pos? (compare b a)) b a))
                                              (map :max ss))))])))
          cols)))

(defn plan
  "Groups of `members` worth rewriting as one file each.

  `{:target-rows n :min-members k}` — a group stops accumulating once it would
  exceed `target-rows` (so compaction does not turn a thousand small files
  into one unmanageable one), and a group smaller than `min-members` is not
  worth the rewrite and is dropped.

  Grouping is by partition, and within a partition it follows the order
  `table/members` produced — which is sorted, so a plan is reproducible."
  [members {:keys [target-rows min-members] :or {target-rows 1000000 min-members 2}}]
  (->> members
       (group-by :partition)
       (sort-by (comp pr-str key))
       (mapcat (fn [[partition ms]]
                 (->> ms
                      (reduce (fn [groups m]
                                (let [g (peek groups)]
                                  (if (and g (<= (+ (:rows g) (:rows m)) target-rows))
                                    (conj (pop groups)
                                          (-> g (update :members conj m)
                                              (update :rows + (:rows m))))
                                    (conj groups {:partition partition
                                                  :members [m]
                                                  :rows (:rows m)}))))
                              [])
                      (filter #(>= (count (:members %)) min-members)))))
       vec))

(defn verify-replacement!
  "Throw unless `replacement` accounts for everything `replaced` held.

  `replacement` is `{:rows n :statistics {col {...}}}` — what the caller's
  writer actually produced, **read back from the file it wrote** rather than
  assumed. Passing the numbers it intended to write would check the intention
  against itself."
  [replaced replacement]
  (let [want (reduce + 0 (map :rows replaced))
        got (:rows replacement)]
    (when-not (= want got)
      (throw (ex-info (str "compaction would change the row count: " want " -> " got)
                      {:type :kotobase.lake/compaction-lost-rows
                       :expected want :actual got
                       :replaced (mapv :cid replaced)})))
    (let [merged (merged-statistics replaced)]
      (doseq [[col {:keys [min max]}] merged]
        (let [s (get-in replacement [:statistics col])]
          (when (and (some? min) (contains? s :min)
                     (pos? (compare (:min s) min)))
            (throw (ex-info (str "compaction narrowed the minimum of " (pr-str col))
                            {:type :kotobase.lake/compaction-narrowed-bounds
                             :column col :was min :now (:min s)})))
          (when (and (some? max) (contains? s :max)
                     (neg? (compare (:max s) max)))
            (throw (ex-info (str "compaction narrowed the maximum of " (pr-str col))
                            {:type :kotobase.lake/compaction-narrowed-bounds
                             :column col :was max :now (:max s)}))))))
    true))

(defn commit
  "Quads for the snapshot in which `replaced` are gone and `replacement` is in.

  `:members` is the member list of the snapshot being replaced — normally
  `(table/members-at quads table (table/current quads table))`. `:replacement`
  is the new member's map, as `table/members` would report it, so its row
  count and statistics are the ones the written file actually has.

  Returns the snapshot quads only. The caller still emits `add-member` for the
  new file and `set-current` to point at the result — kept separate because
  they are separate facts, and a caller replaying a history wants the member
  to exist before a snapshot names it."
  [{:keys [table id parent members replaced replacement]}]
  (verify-replacement! replaced replacement)
  (let [gone (set (map :member replaced))
        kept (remove #(contains? gone (:member %)) members)]
    (when (= (count kept) (count members))
      (throw (ex-info "none of the replaced members are in this snapshot"
                      {:type :kotobase.lake/compaction-replaces-nothing
                       :replaced (mapv :cid replaced)})))
    (table/snapshot {:table table :id id :parent parent
                     :members (conj (mapv :member kept) (:member replacement))})))
