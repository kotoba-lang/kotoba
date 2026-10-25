(ns kotobase-shard-index.route
  "The read side with the fan-out removed.

  `query/search` asks every shard about every term. That is not an accident of
  the implementation, it is what a doc-sharded index has to do when the only
  thing it knows about a shard is that it exists — and it is the measured
  ceiling of the v1 design: growing 1 -> 32 shards multiplied GETs by 12.2x
  while the per-shard cost stayed flat (ADR-2608071500, `:scaled-shards`).
  Since the honest reach was put at 10^9-10^10 pages on exactly that number,
  the fan-out term is the thing standing between this design and the next
  order of magnitude.

  ## What is added

  One dictionary for the whole index instead of one per shard:

      term -> [{:shard :max-impact :df :postings} ...]

  `:max-impact` is that shard's largest possible contribution for that term
  (the first chunk's, since postings are impact-ordered). Two things follow.

  **Locating a term costs one descent, not S.** The routing entry already
  carries each shard's posting-head cid, so the per-shard dictionaries are not
  read at all on this path. `S x T x height` GETs become `T x height`.

  **A shard can be excluded without being opened.** Any document in shard `s`
  scores at most `sum over query terms of max-impact(t, s)`. If the k-th
  confirmed score already reaches that sum, no document in `s` can enter the
  top-k, so `s` is skipped entirely — no posting head, no chunks.

  ## Why this is still exact

  The bound is the same argument `query/search` already makes, one level up.
  There, a document absent from the read prefix of term `t` cannot beat the
  max-impact of `t`'s first unread chunk. Here, a document in an unopened
  shard cannot beat the sum of that shard's per-term max-impacts, because each
  of its term contributions is at most the corresponding max-impact and its
  score is their sum. So `shard-bound` is a sound upper bound for every unseen
  document in that shard, and folding it into the `u` term of the existing
  proof preserves the proof rather than weakening it.

  Exactness therefore carries over unchanged, **including its limit**: exact
  by score, ties unspecified. `route-vs-oracle` in the test suite checks that
  against `query/top-k-exhaustive` rather than asserting it.

  ## What it costs

  The routing dictionary is a second copy of the term dictionary — one entry
  per (term, shard) pair, which is exactly the total size of the per-shard
  dictionaries. Index blocks grow; that growth is reported by the bench rather
  than described here, because a routing layer that pays for itself only on
  paper is the kind of claim this subsystem exists to refuse."
  (:require [kotobase-shard-index.analyze :as analyze]
            [kotobase-shard-index.block :as block]))

;; ── routing descent ─────────────────────────────────────────────────

(defn route-lookup
  "`term` -> vector of `{:shard :max-impact :df :postings}`, or nil.

  One GET per tree level, once for the whole index. Same tree shape as the
  per-shard dictionary, so it is the same descent code path."
  [store root term]
  (loop [cid root]
    (let [blk (block/get-block store cid)]
      (if (= :dict-leaf (:kind blk))
        (some (fn [[t e]] (when (= t term) e)) (:entries blk))
        (let [entries (:entries blk)]
          (recur (reduce (fn [acc [first-term child]]
                           (if (<= (compare first-term term) 0) child acc))
                         (second (first entries))
                         entries)))))))

(defn shard-bounds
  "`{shard-id upper-bound}` over the shards any query term touches.

  The bound is the sum over terms of that shard's max-impact — the score of a
  hypothetical document that is simultaneously the best match for every term.
  No real document can exceed it."
  [routes]
  (reduce (fn [acc [_ti entries]]
            (reduce (fn [a e] (update a (:shard e) (fnil + 0) (:max-impact e)))
                    acc entries))
          {}
          routes))

;; ── scan ────────────────────────────────────────────────────────────

(defn- threshold [l]
  (if (< (:idx l) (count (:chunks l)))
    (:max-impact (nth (:chunks l) (:idx l)))
    0))

(defn- absorb-chunk [acc l postings]
  (reduce (fn [a [doc-id imp]]
            (update a doc-id
                    (fn [v]
                      (-> (or v {:score 0 :seen #{} :shard (:shard l)})
                          (update :score + imp)
                          (update :seen conj (:term-idx l))))))
          acc postings))

(defn- rank [acc]
  (->> acc
       (map (fn [[d v]] (assoc v :doc-id d)))
       (sort-by (juxt (comp - :score) :doc-id))
       vec))

(defn- proven?
  "Unchanged from `query/proven?` except that `u` now also covers shards that
  were never opened. `>=` is what leaves ties unspecified."
  [ranked k u ub]
  (let [m (count ranked)]
    (and (>= m k)
         (let [kth-lb (:score (nth ranked (dec k)))]
           (and (>= kth-lb u)
                (every? #(>= (:score (nth ranked %)) (ub (nth ranked (inc %))))
                        (range 0 (dec k)))
                (every? #(>= kth-lb (ub (nth ranked %)))
                        (range k m)))))))

(defn- fetch-meta [store shards hits]
  (reduce
   (fn [out [sid hs]]
     (let [sh (first (filter #(= sid (:id %)) shards))
           dir (block/get-block store (:meta-dir sh))
           {:keys [chunk-size base chunks]} dir]
       (reduce (fn [o ci]
                 (reduce (fn [o2 d] (assoc o2 (:id d) d))
                         o
                         (:docs (block/get-block store (nth chunks ci)))))
               out
               (distinct (map #(quot (- (:doc-id %) base) chunk-size) hs)))))
   {}
   (group-by :shard hits)))

;; ── entry point ─────────────────────────────────────────────────────

(defn search
  "Top-`k` for `q` using the routing dictionary. Same contract as
  `query/search`; `:stats` additionally reports `:shards-considered`,
  `:shards-opened` and `:shards-pruned`.

  Shards are opened in descending order of their bound, best first, and only
  while they can still change the answer. That ordering is what makes pruning
  bite: the k-th score rises fastest when the most promising shard is read
  first, and every shard whose bound falls under it is then excluded without a
  single GET."
  ([store manifest-cid q] (search store manifest-cid q {}))
  ([store manifest-cid q {:keys [k prefetch shard-batch]
                          :or {k 10 prefetch 8 shard-batch 8}}]
   (let [manifest (block/get-block store manifest-cid)
         _ (when-not (:route-root manifest)
             (throw (ex-info "index has no routing dictionary; rebuild with :route? true"
                             {:manifest-cid manifest-cid})))
         shards (:shards manifest)
         terms (vec (distinct (analyze/tokenize q)))
         ;; one descent per term, for the whole index
         routes (vec (keep-indexed
                      (fn [ti t]
                        (when-let [es (route-lookup store (:route-root manifest) t)]
                          [ti es]))
                      terms))
         bounds (shard-bounds routes)
         ;; best-first; the order is the whole reason pruning works
         order (mapv first (sort-by (fn [[sid b]] [(- b) sid]) bounds))
         descent-waves (if (seq routes) (:route-height manifest) 0)]
     (loop [pending order lists [] acc {} chunk-reads 0 waves 0 opened 0]
       (let [by-shard (group-by :shard lists)
             ;; An unseen document is bounded by the best of: what an opened
             ;; shard could still yield, and what an unopened shard could
             ;; yield at all. Dropping the second half is the mutation the
             ;; test suite kills.
             u-open (reduce max 0 (map (fn [ls] (reduce + 0 (map threshold ls)))
                                       (vals by-shard)))
             u-closed (reduce max 0 (map #(get bounds % 0) pending))
             u (max u-open u-closed)
             ub (fn [c]
                  (+ (:score c)
                     (reduce + 0 (map threshold
                                      (remove #(contains? (:seen c) (:term-idx %))
                                              (get by-shard (:shard c)))))))
             ranked (rank acc)
             spent? (and (empty? pending)
                         (every? #(>= (:idx %) (count (:chunks %))) lists))
             done (cond spent? :exhausted
                        (proven? ranked k u ub) :bounded)]
         (cond
           done
           (let [hits (vec (take k ranked))
                 meta-by-id (if (seq hits) (fetch-meta store shards hits) {})]
             {:hits (mapv (fn [h] (merge (select-keys h [:doc-id :score])
                                         (dissoc (get meta-by-id (:doc-id h)) :id)))
                          hits)
              :stats {:terms terms
                      :lists (count lists)
                      :chunk-reads chunk-reads
                      :candidates (count ranked)
                      :proof done
                      ;; Fan-out falls in TWO independent steps and reporting
                      ;; one of them hides the other:
                      ;;   total -> considered : shards holding NO query term.
                      ;;                         Free — the routing entry
                      ;;                         simply does not list them.
                      ;;   considered -> opened: shards that hold a term but
                      ;;                         whose bound cannot reach the
                      ;;                         k-th score. This is pruning.
                      ;; A topical corpus collapses at the first step, a
                      ;; homogeneous one at the second, and which dominates is
                      ;; a property of the corpus, not of this code.
                      :shards-total (count shards)
                      :shards-considered (count order)
                      :shards-opened opened
                      :shards-pruned (- (count order) opened)
                      :shards-absent (- (count shards) (count order))
                      :waves (+ 1 descent-waves waves (if (seq hits) 2 0))}})

           ;; Nothing left to read in the open shards -> open the next batch.
           ;;
           ;; `shard-batch` is the GETs-versus-waves dial and it is the reason
           ;; this is a batch rather than one shard at a time. Opening one per
           ;; wave gives the fewest GETs — every shard is re-judged against a
           ;; k-th score that has already risen — but it makes the sequential
           ;; depth linear in the shards opened, and depth is what latency
           ;; tracks. Measured on the uniform 64k/32-shard corpus: batch 1 was
           ;; 70.6 GETs in 70 waves, batch 8 is 84.6 GETs in 19. The posting
           ;; heads within a batch are independent, so a real client issues
           ;; them concurrently.
           (every? #(>= (:idx %) (count (:chunks %))) lists)
           (let [batch (take shard-batch pending)
                 wanted (set batch)
                 new-lists (vec (for [[ti es] routes
                                      e es
                                      :when (contains? wanted (:shard e))]
                                  (let [head (block/get-block store (:postings e))]
                                    {:shard (:shard e) :term-idx ti
                                     :chunks (vec (:chunks head)) :idx 0})))]
             (recur (drop shard-batch pending) (into lists new-lists) acc
                    chunk-reads (inc waves) (+ opened (count batch))))

           :else
           (let [batch (->> (for [[li l] (map-indexed vector lists)
                                  ci (range (:idx l) (count (:chunks l)))]
                              [(:max-impact (nth (:chunks l) ci)) li ci])
                            (sort-by (fn [[mi _ ci]] [(- mi) ci]))
                            (take prefetch)
                            vec)
                 acc' (reduce (fn [a [_ li ci]]
                                (let [l (nth lists li)
                                      chunk (block/get-block
                                             store (:cid (nth (:chunks l) ci)))]
                                  (absorb-chunk a l (:postings chunk))))
                              acc batch)
                 lists' (reduce (fn [ls [_ li ci]]
                                  (update-in ls [li :idx] max (inc ci)))
                                lists batch)]
             (recur pending lists' acc' (+ chunk-reads (count batch)) (inc waves) opened))))))))
