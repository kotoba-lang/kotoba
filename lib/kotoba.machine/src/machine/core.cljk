(ns machine.core
  "The T5 contract: what a piece of hardware IS, as validated data.

  Every hardware-shaped decision in this stack — field layout, traversal
  order, page-cache sizing, I/O batching, GPU launch geometry — needs the
  same handful of numbers: how wide a cache line is, how big a page is, how
  many bytes fit in L2, how deep a device queue runs. Before this namespace
  those numbers lived nowhere, so each planner would have had to invent its
  own constants. Constants invented per planner is exactly how an
  optimization fossil forms: a number that was true on the machine someone
  measured in 2026 and silently wrong everywhere after.

  So a descriptor is data, it is validated, and — this is the part that
  matters — **it carries its own provenance**. `:measured` means someone ran
  something on the actual device. `:vendor-declared` means it came off a
  datasheet. `:assumed` means it is a portable floor nobody measured.
  `perfgate` refuses to qualify a performance claim built on `:assumed`
  numbers, which is the mechanism that stops a guess from hardening into a
  fact.

  This namespace deliberately does NOT probe. Reading `sysctl`, `cpuid`,
  `/sys/devices/system/cpu`, `navigator.gpu.limits` or a `WGSLLanguageFeatures`
  set is a host effect; a contract that performs effects cannot be a contract.
  A host builds a descriptor and hands it in.

  Pure `.cljc`, zero dependencies, no host objects."
  (:require [kotoba.lang.text :as str]))

(def format-id :kotoba.machine/v1)

(def provenances
  "How a descriptor's numbers were obtained. Ordered weakest-last."
  #{:measured :vendor-declared :assumed})

(def ^:private provenance-rank {:measured 2 :vendor-declared 1 :assumed 0})

(defn at-least-as-strong?
  "Is `p` at least as strong a provenance as `floor`?"
  [p floor]
  (>= (get provenance-rank p -1) (get provenance-rank floor 99)))

;; ── shape ────────────────────────────────────────────────────────────────
;;
;; A descriptor is a closed map. Unknown top-level keys are an error rather
;; than being ignored, because a typo'd `:strorage` that silently reads as
;; "no storage devices" produces a planner that quietly stops planning.

(def ^:private top-level-keys
  #{:format :machine/id :machine/provenance :machine/source
    :cpu :page :tlb :numa :dram :gpu :storage :bandwidth})

(def ^:private required-keys #{:format :machine/id :machine/provenance :machine/source})

(def cache-kinds #{:data :instruction :unified})
(def seek-costs
  "How much a device charges for a non-adjacent access.

  `:none` is not a rounding of `:low`. It is the statement that reordering
  requests to reduce seek distance buys nothing, which changes an I/O
  planner from a sorter into a batcher."
  #{:none :low :high})

(defn- pow2? [n] (and (integer? n) (pos? n) (zero? (bit-and n (dec n)))))

(defn- err [code m] (merge {:error code} m))

(defn- cache-errors [caches]
  (if-not (or (nil? caches) (vector? caches))
    [(err :invalid-cache-list {:cache caches})]
    (vec
     (concat
      (for [[i c] (map-indexed vector caches)
            :let [{:keys [level kind bytes line-bytes ways shared-by]} c]
            e (cond-> []
                (not (pos-int? level))          (conj :invalid-cache-level)
                (not (cache-kinds kind))        (conj :invalid-cache-kind)
                (not (pos-int? bytes))          (conj :invalid-cache-bytes)
                (not (pow2? line-bytes))        (conj :invalid-cache-line-bytes)
                ;; Associativity is OPTIONAL, learned the hard way: macOS
                ;; exposes cache sizes, line width, page size and cluster
                ;; topology through sysctl and does NOT expose ways at all.
                ;; A contract that demands a fact the platform will not give
                ;; leaves a probe with two options — fabricate a plausible
                ;; number, or refuse to describe the machine — and both are
                ;; worse than recording that it is unknown.
                (and (some? ways) (not (pos-int? ways))) (conj :invalid-cache-ways)
                (not (pos-int? shared-by))      (conj :invalid-cache-shared-by)
                (and (pos-int? bytes) (pos-int? ways) (pow2? line-bytes)
                     (not (zero? (mod bytes (* ways line-bytes)))))
                (conj :cache-geometry-inconsistent))]
        (err e {:index i :cache c}))
      ;; Levels must be strictly increasing in capacity per kind. A machine
      ;; whose L2 is smaller than its L1 is a transcription error, and every
      ;; "does the working set fit" question downstream would answer wrongly.
      (for [[kind group] (group-by :kind caches)
            :let [sorted (sort-by :level group)]
            [a b] (partition 2 1 sorted)
            :when (and (pos-int? (:bytes a)) (pos-int? (:bytes b))
                       (>= (:bytes a) (:bytes b)))]
        (err :cache-capacity-not-increasing
             {:kind kind :level-a (:level a) :level-b (:level b)}))))))

(defn- simd-errors [simd]
  (when simd
    (cond-> []
      (not (pow2? (:width-bits simd))) (conj (err :invalid-simd-width {:simd simd}))
      (not (keyword? (:name simd)))    (conj (err :invalid-simd-name {:simd simd})))))

(defn- cluster-errors [clusters]
  (if-not (or (nil? clusters) (vector? clusters))
    [(err :invalid-cluster-list {:clusters clusters})]
    (vec
     (concat
      (for [[i c] (map-indexed vector clusters)
            e (concat
               (cond-> []
                 (not (keyword? (:id c)))     (conj (err :invalid-cluster-id {:index i :cluster c}))
                 (not (pos-int? (:cores c)))  (conj (err :invalid-cluster-cores {:index i :cluster c})))
               (simd-errors (:simd c))
               (cache-errors (:cache c)))]
        e)
      (let [ids (map :id clusters)]
        (when-not (= (count ids) (count (set ids)))
          [(err :duplicate-cluster-id {:ids (vec ids)})]))))))

(defn- cpu-errors [cpu]
  (if (nil? cpu)
    []
    (concat
     (cond-> []
       (not (keyword? (:arch cpu)))     (conj (err :invalid-cpu-arch {:arch (:arch cpu)}))
       (not (pos-int? (:cores cpu)))    (conj (err :invalid-cpu-cores {:cores (:cores cpu)})))
     (simd-errors (:simd cpu))
     (cache-errors (:cache cpu))
     (cluster-errors (:clusters cpu))
     ;; A heterogeneous machine that also carries a top-level `:cache` invites
     ;; exactly the bug the cluster model exists to prevent: a planner reads
     ;; the flat cache, gets one cluster's numbers, and silently plans the
     ;; wrong tile for the other. Carry one or the other.
     (when (and (seq (:clusters cpu)) (seq (:cache cpu)))
       [(err :both-flat-cache-and-clusters
             {:note "a heterogeneous CPU must not also declare a flat :cache"})]))))

(defn- page-errors [page]
  (when page
    (cond-> []
      (not (pow2? (:base-bytes page)))
      (conj (err :invalid-page-base-bytes {:page page}))
      (not (and (vector? (:huge page)) (every? pow2? (:huge page))))
      (conj (err :invalid-huge-pages {:page page}))
      (and (pow2? (:base-bytes page)) (vector? (:huge page))
           (not (every? #(and (pow2? %) (> % (:base-bytes page))) (:huge page))))
      (conj (err :huge-page-not-larger-than-base {:page page})))))

(def translation-regimes
  "How the walk that pays the translation cost is shaped.

  A dependent chain has no memory-level parallelism to hide a page walk
  behind; a streaming walk has plenty. That is a real difference in mechanism,
  and it is why the fact carries a curve per regime rather than one curve.

  **It is not, on this part, a large difference in magnitude — and the figure
  that once said otherwise was an artifact.** An earlier version of the probe
  touched one line per page at offset 0, so every touched line sat 16 KiB
  apart and congruent to the same cache sets; the resulting 5x was mostly L1
  conflict, not translation. De-confounded and measured across three runs, the
  two regimes overlap at the only page count both cover: `:dependent` at 512
  pages reads 1.17-1.55x and `:streaming` reads 1.09-1.48x.

  So the reason `translation-penalty` refuses to guess is not that the numbers
  are far apart here. It is that a machine measures the regimes separately,
  and silently answering with one regime's curve when asked for the other
  returns a number about a different walk. On a part where the TLB is smaller
  relative to the working set than this one, that number could be far off; on
  this one it happens not to be, and neither the caller nor this function
  knows which case it is in."
  #{:dependent :streaming})

(defn- tlb-errors
  "Measured translation penalty: pages touched -> slowdown vs the flat region.

  Values are ratios, not times, so the fact survives a machine getting
  faster. A ratio below 1.0 means touching more pages made it quicker, which
  is not a thing, so it is rejected rather than smoothed."
  [tlb]
  (when tlb
    (let [by-regime (:penalty-by-pages tlb)
          curve-ok? (fn [c] (and (map? c) (seq c)
                                 (every? (fn [[k v]] (and (pos-int? k) (number? v) (>= v 1.0)))
                                         c)))]
      (cond-> []
        (not (and (map? by-regime) (seq by-regime)))
        (conj (err :invalid-tlb-curve {:tlb tlb}))
        (and (map? by-regime)
             (not (every? translation-regimes (keys by-regime))))
        (conj (err :unknown-translation-regime
                   {:tlb tlb :known translation-regimes}))
        (and (map? by-regime) (not (every? curve-ok? (vals by-regime))))
        (conj (err :invalid-tlb-entry {:tlb tlb}))
        (not (and (string? (:source tlb)) (seq (:source tlb))))
        (conj (err :tlb-curve-needs-a-source {:tlb tlb}))
        ;; Same reason bandwidth carries one: a translation curve measured
        ;; from the JVM does not describe native code on the same silicon.
        (not (keyword? (:runtime tlb)))
        (conj (err :tlb-curve-needs-a-runtime {:tlb tlb}))))))

(defn- numa-errors [numa]
  (when numa
    (let [{:keys [nodes distance]} numa]
      (cond-> []
        (not (pos-int? nodes))
        (conj (err :invalid-numa-nodes {:numa numa}))
        (not (and (vector? distance)
                  (= nodes (count distance))
                  (every? #(and (vector? %) (= nodes (count %))
                                (every? pos-int? %)) distance)))
        (conj (err :invalid-numa-distance-matrix {:numa numa}))
        ;; A node is never further from itself than from a peer. Violating
        ;; this inverts every placement decision built on the matrix.
        (and (vector? distance) (= nodes (count distance))
             (not (every? (fn [i] (= (get-in distance [i i])
                                     (apply min (get distance i))))
                          (range nodes))))
        (conj (err :numa-self-distance-not-minimal {:numa numa}))))))

(defn- bandwidth-errors
  "A measured bandwidth curve: stride in bytes -> bytes per nanosecond."
  [bw]
  (when bw
    (let [by-stride (:by-stride bw)]
      (cond-> []
        (not (and (map? by-stride) (seq by-stride)))
        (conj (err :invalid-bandwidth-curve {:bandwidth bw}))
        (and (map? by-stride)
             (not (every? (fn [[k v]] (and (pos-int? k) (number? v) (pos? v))) by-stride)))
        (conj (err :invalid-bandwidth-entry {:bandwidth bw}))
        (not (and (string? (:source bw)) (seq (:source bw))))
        (conj (err :bandwidth-curve-needs-a-source {:bandwidth bw}))
        ;; A curve without its runtime is a curve nobody can place: the same
        ;; machine measured from C and from the JVM differs by 4x at the
        ;; short-stride end.
        (not (keyword? (:runtime bw)))
        (conj (err :bandwidth-curve-needs-a-runtime {:bandwidth bw}))))))

(defn- dram-errors [dram]
  (when dram
    (cond-> []
      (not (pos-int? (:channels dram)))  (conj (err :invalid-dram-channels {:dram dram}))
      (not (pow2? (:row-bytes dram)))    (conj (err :invalid-dram-row-bytes {:dram dram})))))

(defn- gpu-errors [gpu]
  (when gpu
    (cond-> []
      (not (keyword? (:kind gpu)))
      (conj (err :invalid-gpu-kind {:gpu gpu}))
      (not (pow2? (:max-workgroup gpu)))
      (conj (err :invalid-gpu-max-workgroup {:gpu gpu}))
      (not (pow2? (:subgroup gpu)))
      (conj (err :invalid-gpu-subgroup {:gpu gpu}))
      (not (pos-int? (:shared-bytes gpu)))
      (conj (err :invalid-gpu-shared-bytes {:gpu gpu}))
      (and (pow2? (:max-workgroup gpu)) (pow2? (:subgroup gpu))
           (< (:max-workgroup gpu) (:subgroup gpu)))
      (conj (err :gpu-workgroup-smaller-than-subgroup {:gpu gpu})))))

(defn- storage-errors [devices]
  (if-not (or (nil? devices) (vector? devices))
    [(err :invalid-storage-list {:storage devices})]
    (vec
     (concat
      (for [[i d] (map-indexed vector devices)
            e (cond-> []
                (not (keyword? (:id d)))                  (conj :invalid-storage-id)
                (not (keyword? (:kind d)))                (conj :invalid-storage-kind)
                (not (pow2? (:block-bytes d)))            (conj :invalid-storage-block-bytes)
                (not (pos-int? (:queue-depth d)))         (conj :invalid-storage-queue-depth)
                (not (seek-costs (:seek-cost d)))         (conj :invalid-storage-seek-cost)
                (not (pos-int? (:max-transfer-bytes d)))  (conj :invalid-storage-max-transfer-bytes)
                (and (pow2? (:block-bytes d)) (pos-int? (:max-transfer-bytes d))
                     (< (:max-transfer-bytes d) (:block-bytes d)))
                (conj :storage-transfer-smaller-than-block))]
        (err e {:index i :device d}))
      (let [ids (map :id devices)]
        (when-not (= (count ids) (count (set ids)))
          [(err :duplicate-storage-id {:ids (vec ids)})]))))))

(defn validation-errors
  "Every reason `m` is not a valid machine descriptor, as a vector of maps.

  Returns all errors rather than the first, because a descriptor is usually
  hand-written once and the useful output is the whole list."
  [m]
  (vec
   (remove nil?
     (concat
      (when-not (map? m) [(err :not-a-map {:value m})])
      (when (map? m)
        (concat
         (when-not (= format-id (:format m))
           [(err :invalid-format {:format (:format m)})])
         (for [k (sort (remove top-level-keys (keys m)))]
           (err :unknown-key {:key k}))
         (for [k (sort (remove (set (keys m)) required-keys))]
           (err :missing-required-key {:key k}))
         (when-not (and (string? (:machine/id m)) (seq (:machine/id m)))
           [(err :invalid-machine-id {:machine/id (:machine/id m)})])
         (when-not (provenances (:machine/provenance m))
           [(err :invalid-provenance {:machine/provenance (:machine/provenance m)})])
         (when-not (and (string? (:machine/source m)) (seq (:machine/source m)))
           [(err :invalid-source {:machine/source (:machine/source m)})])
         (cpu-errors (:cpu m))
         (page-errors (:page m))
         (tlb-errors (:tlb m))
         (numa-errors (:numa m))
         (dram-errors (:dram m))
         (gpu-errors (:gpu m))
         (bandwidth-errors (:bandwidth m))
         (storage-errors (:storage m))))))))

(defn valid? [m] (empty? (validation-errors m)))

(defn validate!
  [m]
  (let [errors (validation-errors m)]
    (when (seq errors)
      (throw (ex-info "invalid machine descriptor"
                      {:phase :machine/validate :errors errors})))
    m))

;; ── derived facts ────────────────────────────────────────────────────────
;;
;; Every accessor here answers `nil` for an absent section rather than
;; substituting a default. A planner that needs a number it was not given
;; should say so (see `require-fact`), not quietly plan against a constant
;; the descriptor never claimed.

(defn clusters
  "The CPU's performance clusters, or `nil` on a homogeneous machine.

  Heterogeneous CPUs are the normal case now, not an exotic one — Apple
  silicon, Intel hybrid, ARM DynamIQ. This machine model gained clusters the
  first time it was pointed at a real device: an M1 Max reports 8 performance
  cores with 128 KiB L1d and a 12 MiB L2 shared by four, alongside 2
  efficiency cores with 64 KiB L1d and a 4 MiB L2 shared by two. A single
  `:cpu :cache` cannot say that, and picking either set silently mis-plans for
  the other half of the machine."
  [m]
  (seq (get-in m [:cpu :clusters])))

(defn heterogeneous? [m] (boolean (clusters m)))

(defn cluster [m id] (first (filter #(= id (:id %)) (clusters m))))

(defn caches
  "Every cache the machine declares — flat, or every cluster's on a
  heterogeneous CPU. Correct for questions that take a maximum (line width);
  not for questions that take a capacity, which is why those demand a
  cluster."
  [m]
  (if-let [cs (clusters m)]
    (vec (mapcat :cache cs))
    (get-in m [:cpu :cache])))

(defn for-cluster
  "A homogeneous descriptor view of one cluster.

  This is the ergonomic half of the honest answer. Asking a heterogeneous
  machine for \"the private L2 share\" has no single answer and throws; asking
  `(for-cluster m :performance)` has one, and every downstream planner —
  `layout`, `traversal`, `paging` — takes it unchanged, because what it gets
  back is an ordinary flat descriptor. Naming the cluster is the whole cost,
  and it is the right cost: a tile sized against the efficiency cluster's L2
  is a different tile."
  [m id]
  (let [c (or (cluster m id)
              (throw (ex-info "no such cluster"
                              {:phase :machine/for-cluster :cluster id
                               :known (mapv :id (clusters m))})))]
    (-> m
        (assoc :machine/id (str (:machine/id m) "/" (name id)))
        (assoc :cpu (cond-> {:arch (get-in m [:cpu :arch])
                             :cores (:cores c)
                             :cache (:cache c)}
                      (or (:simd c) (get-in m [:cpu :simd]))
                      (assoc :simd (or (:simd c) (get-in m [:cpu :simd]))))))))

(defn- homogeneous!
  "Refuse a capacity question that a heterogeneous machine cannot answer."
  [m what]
  (when (heterogeneous? m)
    (throw (ex-info (str what " is not a single number on a heterogeneous CPU")
                    {:phase :machine/homogeneous
                     :machine/id (:machine/id m)
                     :clusters (mapv :id (clusters m))
                     :remedy "(machine.core/for-cluster m :performance) — name the cluster"})))
  m)

(defn cache-at
  "The cache record at `level` of `kind` (`:data`/`:instruction`/`:unified`).
  Falls back to `:unified` at that level when the exact kind is absent, which
  is how real hierarchies are shaped: split L1, unified L2/L3."
  [m level kind]
  (homogeneous! m "a cache at a level")
  (let [cs (caches m)]
    (or (first (filter #(and (= level (:level %)) (= kind (:kind %))) cs))
        (first (filter #(and (= level (:level %)) (= :unified (:kind %))) cs)))))

(defn line-bytes
  "The cache line width to plan against.

  The MAXIMUM declared line, not the L1 line. Padding to the widest line is
  correct at every level; padding to a narrower one leaves false sharing on
  the level that has a wider line."
  [m]
  (when-let [ls (seq (keep :line-bytes (caches m)))] (apply max ls)))

(defn cache-bytes [m level kind] (:bytes (cache-at m level kind)))

(defn private-cache-bytes
  "Bytes of level-`level` cache a single core may assume it owns.

  Capacity divided by how many cores share it. Blocking a working set
  against the raw shared capacity is the classic way to produce a tile that
  fits on paper and thrashes with three sibling threads."
  [m level kind]
  (homogeneous! m "a private cache share")
  (when-let [c (cache-at m level kind)]
    (quot (:bytes c) (:shared-by c))))

(defn page-bytes [m] (get-in m [:page :base-bytes]))
(defn huge-page-bytes [m] (get-in m [:page :huge]))

(defn simd-lanes
  "How many `element-bytes`-wide elements fit in one SIMD register."
  [m element-bytes]
  (when-let [w (get-in m [:cpu :simd :width-bits])]
    (when (pos-int? element-bytes)
      (quot (quot w 8) element-bytes))))

(defn numa-nodes [m] (get-in m [:numa :nodes]))

(defn numa-distance [m from to] (get-in m [:numa :distance from to]))

(defn numa-local?
  "Is `to` the closest node to `from`? True on a single-node machine."
  [m from to]
  (when-let [row (get-in m [:numa :distance from])]
    (= (get row to) (apply min row))))

(defn bandwidth-at-stride
  "Bytes per nanosecond this machine delivers to a walk of the given stride.

  **Bandwidth is a property of the machine AND the access pattern.** The same
  part measured here gives 24 GB/s to a line-strided walk, 34 at a 1 KiB
  stride and 11.5 at the 16 KiB page size, where the TLB gives out — a 3x
  spread. Handing a planner the wrong end of that range is not a rounding
  error: it made one model predict a 1.00x speedup where measurement showed
  2.69x.

  Documenting \"pass the right constant\" did not stop that happening twice, so
  the curve lives in the descriptor and this reads it. Returns `nil` when the
  machine carries no measured curve, which is the usual `require-fact`
  contract — a planner must ask out loud rather than default.

  **A curve is specific to the runtime that measured it, not only to the
  machine.** On the part this was developed against, a C loop and a JVM loop
  disagree by 4x at a 128-byte stride and by under 10% at 16 KiB, and the
  curves differ in shape as well as scale. Record which runtime produced it —
  `:source` and `:runtime` exist for that — and do not hand a JVM-measured
  curve to a model of native code.

  Between measured points it takes the **nearer-lower** stride's figure, which
  is the pessimistic side: real curves fall as stride grows, so rounding down
  the stride rounds up the bandwidth only when the caller asked past the last
  measured point, and that case returns the last (lowest) entry instead."
  [m stride-bytes]
  (when-let [curve (get-in m [:bandwidth :by-stride])]
    (when (pos-int? stride-bytes)
      (let [at-or-below (filter #(<= % stride-bytes) (keys curve))]
        (if (seq at-or-below)
          (get curve (apply max at-or-below))
          ;; Below every measured stride: the smallest measured one is the
          ;; closest thing to an answer and is not extrapolated past.
          (get curve (apply min (keys curve))))))))

(defn translation-penalty
  "How much slower a walk gets from spreading over `pages` pages, as a ratio.

  Address translation is a cost the byte-counting models do not see: the same
  bytes, the same cache pressure, spread over more pages, cost more.

  **How much more is smaller than this docstring used to claim.** It said 16.8
  ns per access at 16 pages against 84.5 at 2048, a 5x spread. That probe put
  every touched line at a page boundary, so the lines were mutually congruent
  in the cache and most of the 5x was conflict rather than translation. With
  the addresses staggered, the same sweep gives about 1.5-1.8x at 2048 pages.

  The fact still earns its place -- a byte-counting model sees none of even
  1.5x, and `traversal/pages-touched` exists because a tile's page footprint
  is not implied by its size. But it is a modest effect on this part, not the
  dominant one an earlier reading suggested.

  **The regime is not optional and has no default.** That same spread costs
  1.36x rather than 5x when the walk streams instead of chasing pointers, and
  the gap is the whole point of the fact: a planner handed the pointer-chase
  figure will size tiles against a cost a streaming loop never pays. Callers
  name `:dependent` or `:streaming`; an unknown regime throws rather than
  falling back, because a silent fallback here is a 4x error.

  Returns `nil` when the machine carries no measured curve for that regime —
  the usual `require-fact` contract, where a planner must ask out loud.

  Between measured points it takes the **nearer-lower** page count, which is
  the optimistic side: penalty rises with pages, so a caller sitting between
  two measurements is told the cheaper of the two. That is deliberate — this
  number's job is to warn about a real cost, and rounding it up would let it
  veto tiles on evidence that was never measured."
  [m pages regime]
  (when-not (translation-regimes regime)
    (throw (ex-info "unknown translation regime"
                    {:phase :machine/translation-penalty
                     :regime regime :known translation-regimes})))
  (when-let [curve (get-in m [:tlb :penalty-by-pages regime])]
    (when (pos-int? pages)
      (let [at-or-below (filter #(<= % pages) (keys curve))]
        (if (seq at-or-below)
          (get curve (apply max at-or-below))
          ;; Below every measured point: the smallest measured count is the
          ;; flat region, which is exactly 1.0 by construction.
          (get curve (apply min (keys curve))))))))

(defn gpu [m] (:gpu m))

(defn storage-device [m id] (first (filter #(= id (:id %)) (:storage m))))

(defn reorderable?
  "Does reordering requests to this device reduce cost?

  False for `:seek-cost :none` — on an NVMe/SSD an elevator sort spends CPU
  and latency to buy nothing, and destroys the submission order the caller
  chose."
  [device]
  (boolean (#{:low :high} (:seek-cost device))))

(defn require-fact
  "`(get-in m path)`, but throws when the descriptor does not carry it.

  The point is that a planner asks out loud. `(or (line-bytes m) 64)` is how
  a fossil gets in; this is the alternative."
  [m path what]
  (let [v (get-in m path)]
    (when (nil? v)
      (throw (ex-info (str "machine descriptor does not declare " what)
                      {:phase :machine/require-fact
                       :machine/id (:machine/id m) :path (vec path) :what what})))
    v))

;; ── canonical form and fingerprint ───────────────────────────────────────

(defn- canonical-string* [x sb]
  (cond
    (map? x)     (do (sb "{")
                     (doseq [[k v] (sort-by (comp pr-str key) x)]
                       (canonical-string* k sb) (sb " ") (canonical-string* v sb) (sb ","))
                     (sb "}"))
    (set? x)     (do (sb "#{")
                     (doseq [v (sort-by pr-str x)] (canonical-string* v sb) (sb ","))
                     (sb "}"))
    (sequential? x) (do (sb "[")
                        (doseq [v x] (canonical-string* v sb) (sb ","))
                        (sb "]"))
    :else        (sb (pr-str x))))

(defn canonical-string
  "A deterministic textual rendering: map keys sorted, sets sorted, vectors
  in order. Two descriptors that differ anywhere render differently, and the
  same descriptor renders identically on JVM and JS."
  [m]
  (let [acc (volatile! [])]
    (canonical-string* m #(vswap! acc conj %))
    (str/join @acc)))

(def ^:private fnv-prime 131)
(def ^:private modulus 2147483647)   ; 2^31-1

(defn fingerprint
  "A deterministic 31-bit fingerprint of a descriptor.

  NOT cryptographic and not claimed to be: it exists so a performance claim
  can notice that the machine underneath it changed
  (`perfgate/stale-on?`). Sealing an artifact is `kotoba-lang/artifact`'s
  job. Arithmetic is chosen to stay under 2^53 so JVM longs and JS doubles
  agree exactly — no BigInt, no host hash."
  [m]
  ;; `reduce` over a string yields Characters on JVM and single-char strings
  ;; in cljs, so the code-point read is the one thing that must branch.
  (reduce (fn [h c]
            (mod (+ (* h fnv-prime)
                    #?(:clj (int c) :cljs (.charCodeAt c 0)))
                 modulus))
          2166136261
          (canonical-string m)))

;; ── profiles ─────────────────────────────────────────────────────────────
;;
;; Only two, and neither pretends to be a specific product. Shipping a
;; hardcoded "apple-m4" full of numbers nobody in this repo measured would
;; create precisely the fossil this contract exists to prevent — and the
;; provenance field would have to say `:assumed` while the id said otherwise.
;; Real machines come from a host probe at `:measured`.

(def portable-64
  "A conservative floor: 64-byte lines, 4 KiB pages, one NUMA node.

  Every number is the WEAKEST common value across mainstream 64-bit targets,
  so a plan built on it is safe (if unambitious) anywhere. Marked `:assumed`,
  which means `perfgate` will not qualify a claim measured against it."
  {:format format-id
   :machine/id "portable-64"
   :machine/provenance :assumed
   :machine/source "conservative floor across mainstream 64-bit targets; not measured"
   :cpu {:arch :portable-64
         :cores 1
         :simd {:name :none :width-bits 64}
         :cache [{:level 1 :kind :data :bytes 32768 :line-bytes 64 :ways 8 :shared-by 1}
                 {:level 2 :kind :unified :bytes 262144 :line-bytes 64 :ways 8 :shared-by 1}]}
   :page {:base-bytes 4096 :huge []}
   :numa {:nodes 1 :distance [[10]]}})

(def unknown
  "A machine nothing is known about.

  Valid, so it can be threaded through a pipeline, but carries no `:cpu`,
  `:page`, `:gpu` or `:storage` — so every planner that needs a real number
  fails loudly at `require-fact` instead of inventing one. This is the right
  default for a host that has not probed yet."
  {:format format-id
   :machine/id "unknown"
   :machine/provenance :assumed
   :machine/source "no probe performed"})

(defn measured
  "Stamp a host-probed descriptor as `:measured` with its evidence.

  `source` must say what was actually read — `\"sysctl hw.cachelinesize\"`,
  `\"navigator.gpu.limits\"`, `\"/sys/devices/system/cpu/cpu0/cache\"`. A
  provenance without a source is a provenance nobody can check, so this
  refuses an empty one."
  [m source]
  (when-not (and (string? source) (seq source))
    (throw (ex-info "measured descriptor needs a non-empty source"
                    {:phase :machine/measured :machine/id (:machine/id m)})))
  (validate! (assoc m :machine/provenance :measured :machine/source source)))
