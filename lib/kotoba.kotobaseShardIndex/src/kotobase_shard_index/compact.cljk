(ns kotobase-shard-index.compact
  "Merging segments back together — the other half of `append`.

  `append!` adds a segment per batch, so a crawl that never stops produces
  shards that never stop accumulating. That is not a slow leak: every shard a
  query term appears in is a shard the client opens, and the fan-out term is
  the measured ceiling of this whole design (ADR-2608085000 — growing 1 -> 32
  shards multiplied GETs by 12.2x before the routing dictionary, 3.9x after).
  Appending without compacting trades a rebuild for a read path that degrades
  on every batch.

  ## The property that makes this cheap: merging does not change the answer

  Impacts are computed against a scoring basis, and `append!` scores every new
  segment against the SAME recorded basis (`build!`'s `:scoring-basis`). So
  two shards' impacts are already on one scale, and merging them is a
  concatenation of posting lists followed by a re-sort — **not a rescore**.

  The top-k of the merged index is therefore *identical*, score for score, to
  the top-k before it. That is not an aspiration, it is what
  `compact-preserves-answers` in the suite checks against the pre-compaction
  index.

  This is the reason compaction is a separate operation from a rebuild rather
  than a special case of one. A rebuild recomputes idf against the current
  corpus and therefore DOES change answers (measured: at basis x2.92 the
  top-10 overlap with a rebuild is 0.64, ADR-2608086000). Compaction fixes
  fan-out. A rebuild fixes drift. Conflating them means paying a rebuild's
  price whenever you wanted the cheap one, and silently moving everyone's
  results whenever you wanted the safe one.

  ## Why only adjacent shards

  Doc-ids are contiguous and a metadata lookup resolves shard and offset by
  arithmetic on `:doc-base`. Merging shards whose ranges are adjacent yields a
  shard that is still one range; merging arbitrary shards would produce a hole
  that every metadata read would have to know about. Since `append!` always
  adds at the end, adjacent is also exactly what a crawl accumulates.

  A non-adjacent request is refused rather than quietly reordered — reordering
  would renumber documents, and doc-ids appear in receipts and in callers'
  saved results."
  (:require [kotobase-shard-index.append :as append]
            [kotobase-shard-index.block :as block]
            [kotobase-shard-index.build :as build]))

;; ── reading a shard back out ────────────────────────────────────────

(defn- dict-entries
  "Every `[term {:df :postings}]` in a shard's dictionary. A build-side full
  walk, the same shape as `append/route-entries`."
  [store root]
  (letfn [(walk [cid]
            (let [blk (block/get-block store cid)]
              (if (= :dict-leaf (:kind blk))
                (vec (:entries blk))
                (vec (mapcat (fn [[_ child]] (walk child)) (:entries blk))))))]
    (walk root)))

(defn- shard-postings
  "`{term [[doc-id impact] ...]}` for one shard, read back from its blocks.

  Reads every posting chunk of every term. That is the cost of compaction and
  it is unavoidable: the merged lists have to be re-sorted by impact, so the
  impacts have to be in hand."
  [store shard]
  (reduce (fn [acc [term {:keys [postings]}]]
            (let [head (block/get-block store postings)]
              (assoc acc term
                     (vec (mapcat #(:postings (block/get-block store (:cid %)))
                                  (:chunks head))))))
          {}
          (dict-entries store (:dict-root shard))))

(defn- shard-docs
  "Metadata for one shard, in doc-id order.

  Re-read and re-chunked rather than having the merged shard point at the
  originals' chunks: a shard whose document count is not a multiple of
  `meta-chunk-size` has a short final chunk, and concatenating chunk lists
  across such a boundary breaks the `(quot (- doc-id base) chunk-size)`
  arithmetic every metadata read depends on. Metadata is small next to
  postings, so re-chunking is the cheap way to stay correct."
  [store shard]
  (let [dir (block/get-block store (:meta-dir shard))]
    (vec (mapcat #(:docs (block/get-block store %)) (:chunks dir)))))

;; ── merging ─────────────────────────────────────────────────────────

(defn- adjacent?
  "Do these shards form one contiguous doc-id range?"
  [shards]
  (let [sorted (sort-by :doc-base shards)]
    (every? (fn [[a b]] (= (+ (:doc-base a) (:doc-count a)) (:doc-base b)))
            (partition 2 1 sorted))))

(defn plan
  "Which shards to merge, smallest-first, without exceeding `max-docs`.

  Returns a vector of shard ids, or nil when there is nothing worth doing.
  Smallest-first because the shards an append leaves behind are the small
  ones, and they cost the same fan-out as a large one — a query asks a
  50-document shard and a 50,000-document shard exactly once each.

  This is a suggestion, not a policy. `compact!` takes explicit ids so a
  caller with its own idea (merge by age, by host, by object size) is not
  fighting this function."
  [store manifest-cid {:keys [max-docs min-shards] :or {max-docs 100000 min-shards 2}}]
  (let [by-base (vec (sort-by :doc-base (:shards (block/get-block store manifest-cid))))
        n (count by-base)
        ;; Adjacency is required, so a candidate is a WINDOW of the doc-id
        ;; order. Every window under the budget is considered rather than one
        ;; grown from a chosen starting point: the first version started at
        ;; the smallest shard and extended forward, which finds almost nothing
        ;; on the shape this exists for — appends leave their small shards at
        ;; the END, so a forward run from there is one shard long.
        windows (for [i (range n)
                      j (range (+ i min-shards) (inc n))
                      :let [w (subvec by-base i j)
                            docs (reduce + 0 (map :doc-count w))]
                      :when (<= docs max-docs)]
                  {:shards w :docs docs})]
    ;; Most shards removed for the fewest documents rewritten. Compaction's
    ;; benefit is the drop in fan-out (one fewer shard to ask, per query,
    ;; forever) and its cost is re-reading and re-sorting the postings of
    ;; everything merged.
    (when-let [best (first (sort-by (juxt (comp - count :shards) :docs) windows))]
      (mapv :id (:shards best)))))

(defn compact!
  "Merge `shard-ids` into one shard. Returns `{:manifest-cid :stats :compacted}`.

  Impacts are carried across unchanged — every shard was scored against the
  manifest's `:scoring-basis`, so they are already comparable and a merge is a
  concatenation plus a re-sort. The answer is unchanged; the shard count is
  not."
  ([sink store hash-fn manifest-cid shard-ids]
   (compact! sink store hash-fn manifest-cid shard-ids {}))
  ([sink store hash-fn manifest-cid shard-ids opts]
   (let [manifest (block/get-block store manifest-cid)
         _ (when-not (:route-root manifest)
             (throw (ex-info "compact needs a routing dictionary" {:manifest-cid manifest-cid})))
         opts (merge build/default-opts (:layout manifest) (:scorer manifest) opts)
         all (:shards manifest)
         wanted (set shard-ids)
         victims (filterv #(contains? wanted (:id %)) all)
         keepers (filterv #(not (contains? wanted (:id %))) all)]
     (when (< (count victims) 2)
       (throw (ex-info "compaction needs at least two existing shards"
                       {:asked shard-ids :found (mapv :id victims)})))
     (when-not (adjacent? victims)
       (throw (ex-info "shards to compact must form one contiguous doc-id range"
                       {:ranges (mapv (juxt :id :doc-base :doc-count)
                                      (sort-by :doc-base victims))})))
     (let [ordered (vec (sort-by :doc-base victims))
           base (:doc-base (first ordered))
           ;; term -> merged postings. The lists are over disjoint doc-id
           ;; ranges, so concatenation cannot produce a duplicate doc-id and
           ;; `build-postings` re-sorts by impact with the doc-id tie-break
           ;; that makes a rebuild byte-identical.
           merged (reduce (fn [acc sh]
                            (reduce-kv (fn [a t ps] (update a t (fnil into []) ps))
                                       acc (shard-postings store sh)))
                          {} ordered)
           docs (vec (mapcat #(shard-docs store %) ordered))
           sid (:id (first ordered))
           built (mapv (fn [t]
                         [t (build/build-postings sink hash-fn (:chunk-size opts)
                                                    t (get merged t))])
                       (sort (keys merged)))
           entries (mapv (fn [[t b]] [t {:df (:df b) :postings (:cid b)}]) built)
           {:keys [root height]} (build/build-dict-tree
                                  sink hash-fn (:dict-fanout opts) entries
                                  (or (:chunking opts) :content))
           shard {:id sid
                  :doc-base base
                  :doc-count (count docs)
                  :dict-root root
                  :dict-height height
                  :term-count (count entries)
                  :meta-dir (build/build-meta sink hash-fn (:meta-chunk-size opts)
                                                base docs)}
           ;; The routing dictionary is rebuilt from the survivors: keepers'
           ;; entries are reused verbatim (their posting heads did not move),
           ;; and the victims' are replaced by the merged shard's.
           kept-ids (set (map :id keepers))
           surviving (->> (append/route-entries store (:route-root manifest))
                          (keep (fn [[t es]]
                                  (let [es' (filterv #(contains? kept-ids (:shard %)) es)]
                                    (when (seq es') [t es']))))
                          vec)
           new-route (mapv (fn [[t b]]
                             [t [{:shard sid :max-impact (:max-impact b)
                                  :df (:df b) :postings (:cid b)}]])
                           built)
           route-entries (build/merge-route-entries surviving new-route)
           route-tree (build/build-route-dict! sink hash-fn (:dict-fanout opts)
                                               route-entries (or (:chunking opts) :content))
           shards' (vec (sort-by :doc-base (conj keepers shard)))
           manifest' (-> manifest
                         (assoc :shards shards'
                                :route-root (:root route-tree)
                                :route-height (:height route-tree))
                         (update :stats assoc
                                 :term-count (count route-entries)
                                 :shard-count (count shards')))]
       {:manifest-cid (block/put-block! sink hash-fn manifest')
        :stats (:stats manifest')
        :compacted {:merged (mapv :id ordered)
                    :into sid
                    :docs (count docs)
                    :shards-before (count all)
                    :shards-after (count shards')}}))))
