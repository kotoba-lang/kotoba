(ns kotobase-shard-index.query
  "Read side. Runs in the client; talks to nothing but an object store.

  There is no hydration step. The 2.3 seconds that dominate kotobase.net's
  p50 today (92% of it, ADR-2607310900 訂正3) are spent rebuilding a database
  value before the query starts, and the sequential part of that is walking
  the unfolded novelty cons-chain (97%, ADR-2608021000). Neither exists here:
  the client reads a published manifest, descends a tree to the terms it
  actually asked for, and stops as soon as the answer is proven.

  ## Why the answer is exact even though we stop early

  Postings are impact-ordered, so a document absent from the prefix of term
  `t` we have read cannot score more than the max-impact of `t`'s first unread
  chunk. That gives every candidate a lower bound (what we have summed) and an
  upper bound (plus its unseen terms' thresholds), and an unseen document an
  upper bound of the shard's threshold sum.

  We stop when those bounds separate: the k-th candidate's lower bound is at
  or above every other candidate's upper bound and above the unseen bound.
  At that point no further read can change the top-k — so this is early
  termination without approximation, and `top-k-exhaustive` exists to check
  exactly that claim rather than assert it.

  ## What \"exact\" covers, and what it does not

  Exact **by score**: the k scores returned are the k largest in the index,
  and each returned score is the document's full score. Among documents whose
  scores are equal, WHICH ones are returned and in what order is unspecified.

  That limit is real, not a wording hedge. The bound reasons about scores, and
  two documents that tie are separated by doc-id — a fact no score bound can
  see. Requiring the bound to also settle ties would mean reading every chunk
  whose max-impact equals the k-th score, which on a corpus with many ties is
  the whole index. This is the same contract impact-ordered retrieval gives
  everywhere; it is stated here because the first version of this namespace
  silently claimed more, and the oracle test caught it."
  (:require [kotobase-shard-index.analyze :as analyze]
            [kotobase-shard-index.block :as block]))

;; ── dictionary descent ──────────────────────────────────────────────

(defn dict-lookup
  "`term` -> `{:df :postings}` or nil. Costs one GET per tree level."
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

;; ── posting cursors ─────────────────────────────────────────────────

(defn- open-lists
  "One cursor per (shard, term) that exists. Terms absent from a shard cost
  the descent and nothing more."
  [store shards terms]
  (vec (for [sh shards
             ti (range (count terms))
             :let [entry (dict-lookup store (:dict-root sh) (nth terms ti))]
             :when entry
             :let [head (block/get-block store (:postings entry))]]
         {:shard (:id sh) :term-idx ti :chunks (vec (:chunks head)) :idx 0})))

(defn- threshold
  "Best score any unread document could still get from this cursor. Zero when
  the cursor is spent, which is what eventually forces termination."
  [l]
  (if (< (:idx l) (count (:chunks l)))
    (:max-impact (nth (:chunks l) (:idx l)))
    0))

(defn- absorb-chunk
  "Fold one posting chunk into the accumulator."
  [acc l postings]
  (reduce (fn [a [doc-id imp]]
            (update a doc-id
                    (fn [v]
                      (-> (or v {:score 0 :seen #{} :shard (:shard l)})
                          (update :score + imp)
                          (update :seen conj (:term-idx l))))))
          acc postings))

;; ── the bound ───────────────────────────────────────────────────────

(defn- rank [acc]
  (->> acc
       (map (fn [[d v]] (assoc v :doc-id d)))
       (sort-by (juxt (comp - :score) :doc-id))
       vec))

(defn- proven?
  "True when no further read can change the top-`k` SCORES. `ub` is the
  per-candidate upper bound, `u` the bound for a document we have not seen at
  all. Comparisons are `>=` rather than `>`, which is what makes ties
  unspecified — see this namespace's docstring."
  [ranked k u ub]
  (let [m (count ranked)]
    (and (>= m k)
         (let [kth-lb (:score (nth ranked (dec k)))]
           (and (>= kth-lb u)
                (every? #(>= (:score (nth ranked %)) (ub (nth ranked (inc %))))
                        (range 0 (dec k)))
                (every? #(>= kth-lb (ub (nth ranked %)))
                        (range k m)))))))

;; ── metadata ────────────────────────────────────────────────────────

(defn- fetch-meta
  "Display fields for the winning doc-ids: one GET per shard directory plus
  one per distinct metadata chunk. Neighbouring doc-ids share a chunk, so a
  host-clustered corpus usually pays one."
  [store shards hits]
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

;; ── entry points ────────────────────────────────────────────────────

(defn search
  "Top-`k` documents for `q`, read entirely from `store`.

  Returns `{:hits [...] :stats {...}}`. `:stats` reports `:waves` — the depth
  of the sequential dependency chain, which is what latency actually tracks —
  alongside `:chunk-reads` and the `:proof` that ended the scan."
  ([store manifest-cid q] (search store manifest-cid q {}))
  ([store manifest-cid q {:keys [k prefetch] :or {k 10 prefetch 8}}]
   (let [manifest (block/get-block store manifest-cid)
         shards (:shards manifest)
         terms (vec (distinct (analyze/tokenize q)))
         lists (open-lists store shards terms)
         descent-waves (if (seq lists) (inc (apply max (map :dict-height shards))) 0)]
     (loop [lists lists acc {} chunk-reads 0 waves 0]
       (let [by-shard (group-by :shard lists)
             u (reduce max 0 (map (fn [ls] (reduce + 0 (map threshold ls)))
                                  (vals by-shard)))
             ub (fn [c]
                  (+ (:score c)
                     (reduce + 0 (map threshold
                                      (remove #(contains? (:seen c) (:term-idx %))
                                              (get by-shard (:shard c)))))))
             ranked (rank acc)
             spent? (every? #(>= (:idx %) (count (:chunks %))) lists)
             done (cond spent? :exhausted
                        (proven? ranked k u ub) :bounded)]
         (if done
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
                      :waves (+ 1 descent-waves waves (if (seq hits) 2 0))}})
           ;; One wave fetches the `prefetch` most promising unread chunks
           ;; ACROSS all lists. This is possible only because the posting head
           ;; carries every chunk's cid and max-impact up front — there is no
           ;; pointer to chase, which is precisely what the hydrate path's
           ;; novelty cons-chain has and why its round trips cannot be
           ;; overlapped (ADR-2608021000).
           ;;
           ;; Chunks are impact-descending within a list, so the global top-N
           ;; by max-impact is automatically a prefix of each list — the
           ;; `threshold` bound stays valid without a special case.
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
             (recur lists' acc' (+ chunk-reads (count batch)) (inc waves)))))))))

(defn top-k-exhaustive
  "The same ranking with every posting chunk read. Not a second algorithm —
  the oracle `search` is checked against, and the O(index) baseline the GET
  counts are compared to."
  ([store manifest-cid q] (top-k-exhaustive store manifest-cid q {}))
  ([store manifest-cid q {:keys [k] :or {k 10}}]
   (let [manifest (block/get-block store manifest-cid)
         shards (:shards manifest)
         terms (vec (distinct (analyze/tokenize q)))
         lists (open-lists store shards terms)
         acc (reduce (fn [a l]
                       (reduce (fn [a2 ch]
                                 (absorb-chunk a2 l (:postings (block/get-block store (:cid ch)))))
                               a (:chunks l)))
                     {} lists)]
     {:hits (mapv #(select-keys % [:doc-id :score]) (take k (rank acc)))
      ;; every document's FULL score, so a caller checking `search` can ask
      ;; "is the score it reported for this doc the complete one" rather than
      ;; only "does the top-k score vector match".
      :scores (reduce-kv (fn [m d v] (assoc m d (:score v))) {} acc)
      :stats {:lists (count lists)
              :chunk-reads (reduce + 0 (map #(count (:chunks %)) lists))}})))
