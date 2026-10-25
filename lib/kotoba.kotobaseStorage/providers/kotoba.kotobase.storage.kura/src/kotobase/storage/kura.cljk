(ns kotobase.storage.kura
  "`kotobase.storage` over the kura shard plane.

  The point of this adapter is that every consumer already speaking
  `kotobase.storage` — including DataLad datasets reaching it through
  `kotoba-annex` — gets kura without learning a new API (ADR-2607299200
  section 0). Writing it surfaced two facts the ADR's one-line description of
  this repo (\"a thin layer holding none of the decisions\") did not account
  for. Both are load-bearing.

  ## 1. kura cannot provide refs, and does not pretend to

  `kotobase.storage` is two protocols: immutable CID blocks and a mutable ref
  with compare-and-set. kura is a *shard plane* — it has objects, placement
  groups and erasure coding, and no linearizable CAS primitive anywhere in it.
  A backend that declared `:single-writer-ref` and shrugged would be doing
  exactly what `kotobase.storage/ref-profiles` warns about: an ignored
  precondition returns success.

  So `open` **requires** a `:ref-store` delegate — another
  `kotobase.storage` backend that really does have a CAS (D1, a Durable
  Object, git) — and this adapter reports *that delegate's* ref profile rather
  than inventing one. Without a delegate it refuses to construct. Blocks come
  from kura; refs come from something that can actually do refs; nothing
  claims to do both.

  ## 2. kura's 1.625x does not apply at kotobase block sizes

  kotobase cuts blocks at 16-128 KB. Erasure-coding a 128 KB block at k=16
  gives 8 KB shards, twenty-six of them, and a read that touches sixteen
  nodes. The storage multiplier would be the advertised 1.625x and the
  operational cost would be sixteen requests to fetch 128 KB — against one
  request for a replica. Below some size, replication is simply better, and
  quoting 1.625x to a consumer whose blocks are all 64 KB would be a lie
  about what they are buying.

  So the adapter has an `:erasure-threshold-bytes`: blocks at or above it are
  erasure-coded, blocks below it are replicated `:replicas` ways. The default
  threshold is 1 MiB, which is where sixteen shard reads start to amortise.
  `effective-multiplier` reports what a given block-size distribution actually
  costs, because the honest number for a real workload is a mixture and not
  either constant."
  (:require [erasure.lrc :as lrc]
            [erasure.matrix :as matrix]
            [kotobase.storage.core :as storage]
            [kura.manifest :as manifest]
            [kura.node.gf :as gf]
            [kura.node.store :as node-store]
            [kura.placement :as placement]))

;; --- policy ----------------------------------------------------------------

(def default-erasure-threshold-bytes
  "1 MiB. At k=16 that is 64 KiB shards — large enough that sixteen reads
  amortise against per-request overhead. Below it, replication wins on
  everything except storage, and storage is the cheap axis at these sizes."
  (* 1024 1024))

(defn policy
  [{:keys [erasure-threshold-bytes replicas layout]
    :or {erasure-threshold-bytes default-erasure-threshold-bytes
         replicas 3}}]
  (assert (>= replicas 2) "replication below 2 is not redundancy")
  {:erasure-threshold-bytes erasure-threshold-bytes
   :replicas replicas
   :layout (or layout (lrc/layout {:k 16 :r 4 :g 6}))})

(defn strategy-for
  "Which strategy a block of `n` bytes gets. A pure function of size and
  policy, so a caller can ask before writing and a report can be computed
  without touching the store."
  [pol n]
  (if (>= n (:erasure-threshold-bytes pol)) :erasure :replication))

(defn multiplier-for
  [pol n]
  (if (= :erasure (strategy-for pol n))
    (/ (double (:n (:layout pol))) (:k (:layout pol)))
    (double (:replicas pol))))

(defn effective-multiplier
  "The physical-to-logical ratio for a real distribution of block sizes.

  Neither 1.625 nor 3 is the answer for a mixed workload, and quoting either
  as *the* multiplier is how a storage estimate ends up wrong by a factor of
  two. Takes the sizes, returns what they actually cost."
  [pol sizes]
  (let [logical (reduce + 0 sizes)
        physical (reduce + 0.0 (map #(* % (multiplier-for pol %)) sizes))]
    {:blocks (count sizes)
     :logical-bytes logical
     :physical-bytes (long physical)
     :multiplier (if (zero? logical) 0.0 (/ physical logical))
     :erasure-coded (count (filter #(= :erasure (strategy-for pol %)) sizes))
     :replicated (count (filter #(= :replication (strategy-for pol %)) sizes))}))

;; --- placement -------------------------------------------------------------

(defn- fleet-descriptors [fleet]
  (mapv #(node-store/-descriptor %) (vals fleet)))

(defn- targets
  "Which nodes hold shard/replica `i` of `cid`.

  Computed, never stored. The fleet is not consulted — placement is a function
  of the cid and the node set (`kura.placement`), which is what keeps the
  metadata plane O(objects) instead of O(objects x shards) as ADR-2607299200
  section 3 requires."
  [{:keys [placement-cfg]} cid width]
  (let [pl (placement/placement cid (assoc placement-cfg :n width))]
    {:complete? (:complete? pl)
     :shortfall (:shortfall pl)
     :by-index (:shards pl)}))

(defn- store-for [fleet node-id] (get fleet node-id))

;; --- block encode / decode -------------------------------------------------

(defn- put-erasure! [{:keys [pol] :as ctx} cid body]
  (let [lay (:layout pol)
        k (:k lay)
        n (gf/blength body)
        ;; One stripe per block: a kotobase block is small enough that cutting
        ;; it further would only shrink the shards. Padded up to a k-multiple,
        ;; which is why the index has to remember the logical length — the
        ;; padding is not recoverable from the shards.
        shard-bytes (max 1 (quot (+ n k -1) k))
        data (mapv (fn [i]
                     (let [s (gf/alloc shard-bytes)]
                       (dotimes [j shard-bytes]
                         (let [src (+ (* i shard-bytes) j)]
                           (when (< src n) (gf/bset! s j (gf/bget body src)))))
                       s))
                   (range k))
        parity (into (mapv (fn [q]
                             (gf/xor-shards (map #(nth data %) (lrc/group-members lay q))
                                            shard-bytes))
                           (range (:l lay)))
                     (map (fn [row] (gf/apply-row row data shard-bytes))
                          (matrix/cauchy-rows k (:g lay))))
        all (into data parity)
        {:keys [by-index complete?]} (targets ctx cid (:n lay))]
    (assert complete? (str "placement could not fill " cid " under the domain caps"))
    (doseq [[i node-id] by-index]
      (node-store/-put-shard! (store-for (:fleet ctx) node-id)
                              (manifest/shard-id cid 0 i)
                              (nth all i)))
    {:cid cid :strategy :erasure :logical n :shards (:n lay)}))

(defn- get-erasure [{:keys [pol] :as ctx} cid logical]
  (let [lay (:layout pol)
        {:keys [by-index]} (targets ctx cid (:n lay))
        ;; Systematic: read the k data shards directly. No reconstruction on
        ;; the clean path — the whole benefit of the layout (ADR section 7).
        data (mapv (fn [i]
                     (when-let [s (store-for (:fleet ctx) (get by-index i))]
                       (node-store/-get-shard s (manifest/shard-id cid 0 i))))
                   (range (:k lay)))]
    (when (every? some? data)
      (let [shard-bytes (gf/blength (first data))
            out (gf/alloc logical)]
        (dotimes [i logical]
          (gf/bset! out i (gf/bget (nth data (quot i shard-bytes))
                                   (mod i shard-bytes))))
        out))))

(defn- put-replication! [{:keys [pol] :as ctx} cid body]
  (let [r (:replicas pol)
        {:keys [by-index complete?]} (targets ctx cid r)]
    (assert complete? (str "placement could not fill " cid " under the domain caps"))
    (doseq [[i node-id] by-index]
      (node-store/-put-shard! (store-for (:fleet ctx) node-id)
                              (manifest/shard-id cid 0 i)
                              body))
    {:cid cid :strategy :replication :logical (gf/blength body) :shards r}))

(defn- get-replication [{:keys [pol] :as ctx} cid]
  (let [{:keys [by-index]} (targets ctx cid (:replicas pol))]
    (some (fn [[i node-id]]
            (when-let [s (store-for (:fleet ctx) node-id)]
              (node-store/-get-shard s (manifest/shard-id cid 0 i))))
          by-index)))

;; --- the backend -----------------------------------------------------------

(defrecord KuraBackend [ctx index ref-store]
  storage/IBlockStore
  (-put-blocks! [_ blocks]
    (doseq [{:keys [cid bytes]} blocks]
      (let [n (gf/blength bytes)
            strategy (strategy-for (:pol ctx) n)
            r (if (= :erasure strategy)
                (put-erasure! ctx cid bytes)
                (put-replication! ctx cid bytes))]
        ;; The index records size and strategy, not placement: placement is a
        ;; function of the cid and the node set (kura.placement), so storing
        ;; it would be the O(objects x shards) table ADR section 3 exists to
        ;; avoid. What cannot be recomputed is the block's logical length,
        ;; because erasure coding pads to a shard boundary.
        (swap! index assoc cid (select-keys r [:strategy :logical]))))
    nil)

  (-get-blocks [_ cids]
    (into {}
          (keep (fn [cid]
                  (when-let [{:keys [strategy logical]} (get @index cid)]
                    (when-let [b (if (= :erasure strategy)
                                   (get-erasure ctx cid logical)
                                   (get-replication ctx cid))]
                      [cid b]))))
          cids))

  storage/IRefStore
  (-read-ref [_ ref-name] (storage/-read-ref ref-store ref-name))
  (-compare-and-set-ref! [_ ref-name expected next]
    (storage/-compare-and-set-ref! ref-store ref-name expected next))

  storage/IBackendCapabilities
  (-capabilities [_]
    ;; The ref profile is the DELEGATE's, reported rather than asserted. This
    ;; adapter has no CAS of its own and must not imply one.
    (conj #{:immutable-blocks :cid-addressed-read :conditional-ref}
          (storage/ref-profile ref-store))))

(defn open
  "Open a kotobase backend over kura.

  `:fleet` maps node-id -> a `kura.node.store` backend. `:placement-cfg` is
  `kura.placement`'s `{:group-count :nodes :pol}`. `:ref-store` is another
  `kotobase.storage` backend that provides the mutable ref — required, because
  kura has no CAS and a backend that faked one would return success on an
  ignored precondition."
  [{:keys [fleet placement-cfg ref-store] :as opts}]
  (assert (map? fleet) "fleet must be a map of node-id -> shard store")
  (assert (seq fleet) "fleet must not be empty")
  (assert (some? ref-store)
          "a ref-store delegate is required: kura provides blocks, not refs")
  (assert (storage/ref-profile ref-store)
          "the ref-store delegate must declare exactly one ref profile")
  (let [pol (policy (or (:policy opts) {}))]
    (->KuraBackend {:fleet fleet :placement-cfg placement-cfg :pol pol}
                   (atom {})
                   ref-store)))

(defn durability-report
  "What the fleet behind this backend can actually survive.

  Delegates to `kura.node.store/audit`, because the question a kotobase
  consumer asks — how durable is my data — is answered by how many independent
  failure domains the fleet really has, not by the erasure code's parameters.
  A fleet of pseudo-nodes on one account reports one domain here."
  [backend]
  (let [{:keys [fleet pol]} (:ctx backend)]
    (node-store/audit (fleet-descriptors fleet)
                      (lrc/max-tolerated-erasures (:layout pol)))))
