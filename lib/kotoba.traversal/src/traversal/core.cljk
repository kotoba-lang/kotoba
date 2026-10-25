(ns traversal.core
  "In what order to visit the elements, given a real cache.

  `layout` decides where bytes sit; this decides the sequence they are
  touched in. The two are independent — a perfect struct-of-arrays walked
  down the wrong axis still misses every line — and the second is usually the
  larger effect, because changing an order changes how much data crosses the
  slow boundary rather than how it is arranged once it is across.

  Three families, and they answer different questions:

  - **linearizations** (`:row-major`, `:column-major`, `:morton`,
    `:hilbert`) — how an n-dimensional index becomes one address. Space-
    filling curves are supposed to keep 2-D neighbours near each other in
    1-D. `neighbour-locality` measures that instead of repeating it, and the
    measurement is worth reading: on a 16×16 grid Morton's mean neighbour
    distance is *identical* to row-major's and Hilbert's is *worse*. The win
    is real but it is in block co-residency (80% against 50%), not in the
    mean — so the intuitive metric answers the wrong question.
  - **tiling** (`tile-plan`) — how large a block may be before it stops
    fitting in a named level of cache. The capacity is asked of `machine`,
    divided by the cores that share it, and multiplied by a stated occupancy
    fraction, because a tile that fills the whole cache on paper thrashes
    against everything else running.
  - **loop order** (`loop-order`) — which loop belongs innermost. This is the
    one that produces the textbook `ikj` matmul from first principles rather
    than from memory.

  Every permutation here is checked to BE a permutation (`bijection?`). A
  reordering that silently skips or repeats an element is not a slow program,
  it is a wrong one.

  Pure `.cljc`. Depends only on `kotoba-lang/machine`."
  (:require [machine.core :as m]))

(def format-id :kotoba.traversal/v1)

(def orders #{:row-major :column-major :morton :hilbert})

;; Bit budgets. cljs bitwise operators work on signed 32-bit values, so an
;; interleave that runs past bit 30 would go negative there and not on the
;; JVM. Rather than branch per runtime, the coordinate range is capped so the
;; result always fits in a positive int32 on both.
(def max-morton-2d-bits 15)   ; side <= 32768, result < 2^30
(def max-morton-3d-bits 10)   ; side <= 1024,  result < 2^30

;; ── Morton (Z-order) ─────────────────────────────────────────────────────

(defn- spread-2 [v]
  ;; Insert a zero between each of the low 15 bits.
  (let [v (bit-and v 0x7fff)
        v (bit-and (bit-or v (bit-shift-left v 8)) 0x00ff00ff)
        v (bit-and (bit-or v (bit-shift-left v 4)) 0x0f0f0f0f)
        v (bit-and (bit-or v (bit-shift-left v 2)) 0x33333333)
        v (bit-and (bit-or v (bit-shift-left v 1)) 0x55555555)]
    v))

(defn- compact-2 [v]
  (let [v (bit-and v 0x55555555)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 1)) 0x33333333)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 2)) 0x0f0f0f0f)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 4)) 0x00ff00ff)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 8)) 0x0000ffff)]
    v))

(defn- check-bits! [vs bits what]
  (let [limit (bit-shift-left 1 bits)]
    (doseq [v vs]
      (when-not (and (integer? v) (<= 0 v) (< v limit))
        (throw (ex-info (str what " coordinate out of range")
                        {:phase :traversal/range :value v :max-exclusive limit
                         :reason "cljs bitwise ops are signed 32-bit; the range is capped so
                                  both runtimes agree"}))))))

(defn morton-encode-2d
  "Interleave the bits of `x` and `y`, x in the even positions."
  [x y]
  (check-bits! [x y] max-morton-2d-bits "morton-2d")
  (bit-or (spread-2 x) (bit-shift-left (spread-2 y) 1)))

(defn morton-decode-2d [d]
  [(compact-2 d) (compact-2 (unsigned-bit-shift-right d 1))])

(defn- spread-3 [v]
  ;; Insert two zeros between each of the low 10 bits.
  (let [v (bit-and v 0x3ff)
        v (bit-and (bit-or v (bit-shift-left v 16)) 0x030000ff)
        v (bit-and (bit-or v (bit-shift-left v 8)) 0x0300f00f)
        v (bit-and (bit-or v (bit-shift-left v 4)) 0x030c30c3)
        v (bit-and (bit-or v (bit-shift-left v 2)) 0x09249249)]
    v))

(defn- compact-3 [v]
  (let [v (bit-and v 0x09249249)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 2)) 0x030c30c3)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 4)) 0x0300f00f)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 8)) 0x030000ff)
        v (bit-and (bit-or v (unsigned-bit-shift-right v 16)) 0x000003ff)]
    v))

(defn morton-encode-3d [x y z]
  (check-bits! [x y z] max-morton-3d-bits "morton-3d")
  (bit-or (spread-3 x)
          (bit-shift-left (spread-3 y) 1)
          (bit-shift-left (spread-3 z) 2)))

(defn morton-decode-3d [d]
  [(compact-3 d)
   (compact-3 (unsigned-bit-shift-right d 1))
   (compact-3 (unsigned-bit-shift-right d 2))])

;; ── Hilbert (2-D, power-of-two side) ─────────────────────────────────────
;;
;; The classic xy2d/d2xy pair. Unlike Morton, consecutive positions on a
;; Hilbert curve are always 4-adjacent cells — no long jumps at quadrant
;; boundaries — which is why it scores better on `neighbour-locality` and why
;; it is the usual choice for spatial index keys.

(defn- pow2? [n] (and (integer? n) (pos? n) (zero? (bit-and n (dec n)))))

(defn- check-side! [side]
  (when-not (pow2? side)
    (throw (ex-info "hilbert side must be a power of two"
                    {:phase :traversal/hilbert :side side})))
  (when (> side (bit-shift-left 1 max-morton-2d-bits))
    (throw (ex-info "hilbert side out of range"
                    {:phase :traversal/hilbert :side side
                     :max (bit-shift-left 1 max-morton-2d-bits)})))
  side)

(defn- hilbert-rot [n [x y] rx ry]
  (if (zero? ry)
    (let [[x y] (if (= 1 rx) [(- n 1 x) (- n 1 y)] [x y])]
      [y x])
    [x y]))

(defn hilbert-encode-2d
  "Position of `(x, y)` along a Hilbert curve of side `side` (power of two)."
  [side x y]
  (check-side! side)
  (check-bits! [x y] max-morton-2d-bits "hilbert-2d")
  (loop [s (quot side 2) x x y y d 0]
    (if (zero? s)
      d
      (let [rx (if (pos? (bit-and x s)) 1 0)
            ry (if (pos? (bit-and y s)) 1 0)
            d (+ d (* s s (bit-xor (* 3 rx) ry)))
            [x y] (hilbert-rot side [x y] rx ry)]
        (recur (quot s 2) x y d)))))

(defn hilbert-decode-2d [side d]
  (check-side! side)
  (loop [s 1 t d x 0 y 0]
    (if (>= s side)
      [x y]
      (let [rx (bit-and 1 (quot t 2))
            ry (bit-and 1 (bit-xor t rx))
            [x y] (hilbert-rot s [x y] rx ry)
            x (+ x (* s rx))
            y (+ y (* s ry))]
        (recur (* s 2) (quot t 4) x y)))))

;; ── generic linearization ────────────────────────────────────────────────

(defn linearize
  "`[x y] -> position` under `order`, for a 2-D extent `[w h]`.

  `:morton` and `:hilbert` need a square power-of-two extent; a curve does
  not cover a ragged box without leaving holes, and quietly returning
  positions with holes in them is how a \"reordering\" starts skipping data."
  [order [w h] [x y]]
  (case order
    :row-major    (+ x (* y w))
    :column-major (+ y (* x h))
    :morton       (do (when-not (= w h)
                        (throw (ex-info "morton needs a square extent"
                                        {:phase :traversal/linearize :extent [w h]})))
                      (morton-encode-2d x y))
    :hilbert      (do (when-not (and (= w h) (pow2? w))
                        (throw (ex-info "hilbert needs a square power-of-two extent"
                                        {:phase :traversal/linearize :extent [w h]})))
                      (hilbert-encode-2d w x y))))

(defn visit-sequence
  "Every coordinate of a 2-D extent, in the order `order` visits them."
  [order [w h]]
  (->> (for [y (range h) x (range w)] [x y])
       (sort-by #(linearize order [w h] %))
       vec))

(defn bijection?
  "Does `order` visit every cell of the extent exactly once?

  Checked, not assumed. A reordering that silently skips or repeats an
  element is not a slow program, it is a wrong one — and both Morton and
  Hilbert do exactly that on an extent they were not given (ragged, or not a
  power of two), which is why `linearize` refuses those extents outright."
  [order [w h]]
  (let [n (* w h)
        positions (for [y (range h) x (range w)] (linearize order [w h] [x y]))]
    (= (set positions) (set (range n)))))

;; ── measuring the locality claim ─────────────────────────────────────────

(defn neighbour-locality
  "How well an order keeps spatial neighbours together, measured three ways.

  For every 4-adjacent pair of cells: how far apart does this order put them
  (`:mean`, `:worst`), and — the one that matters — do they land in the same
  block of `block` consecutive positions (`:same-block`)?

  **Measure this rather than repeating the folklore.** Running it on a 16×16
  grid says something people do not expect: Morton's mean neighbour distance
  is *exactly* row-major's (8.5), and Hilbert's is *worse* (9.92). Space-
  filling curves do not win on the mean, because the mean is dominated by the
  few very long jumps and the curves trade many medium jumps for a few huge
  ones.

  Where they do win is `:same-block`, which is the question a cache line or a
  page actually asks: with `block` 16, both curves put 80% of neighbouring
  pairs in one block against row-major's 50%, because a 4×4 tile of the grid
  is 16 consecutive, block-aligned positions on either curve while row-major
  spreads it across four separate rows.

  So: use `:same-block` to choose an order, and keep `:mean` around as the
  reminder that the intuitive metric answers the wrong question."
  ([order extent] (neighbour-locality order extent nil))
  ([order [w h] block]
   (let [pos (fn [x y] (linearize order [w h] [x y]))
         pairs (vec (concat (for [y (range h) x (range (dec w))]
                              [(pos x y) (pos (inc x) y)])
                            (for [y (range (dec h)) x (range w)]
                              [(pos x y) (pos x (inc y))])))
         deltas (mapv (fn [[a b]] (Math/abs (- a b))) pairs)
         n (count pairs)]
     (cond-> {:order order
              :extent [w h]
              :pairs n
              :mean (if (pos? n) (double (/ (reduce + deltas) n)) 0.0)
              :worst (if (pos? n) (apply max deltas) 0)}
       block
       (assoc :block block
              :same-block
              (if (pos? n)
                (double (/ (count (filter (fn [[a b]] (= (quot a block) (quot b block)))
                                          pairs))
                           n))
                0.0))))))

;; ── tiling ───────────────────────────────────────────────────────────────

(def tile-model
  {:model/id :kotoba.traversal.tile/square-working-set-v1
   :model/rule "arrays * tile^2 * element-bytes <= capacity * occupancy"
   :model/assumes
   ["a square tile touched by `arrays` operands, the classic blocked-matmul shape"
    "capacity is the PRIVATE share of the level: total / cores sharing it"
    "occupancy < 1 because the tile shares the level with stack, code and neighbours"]
   ;; `:tlb-reach` stays on this list even though the plan now reports pages
   ;; and a penalty. Reporting a cost is not modelling it: the rule still
   ;; picks the tile from bytes and capacity alone, and nothing here shrinks a
   ;; tile to touch fewer pages. Measured 2026-08-03, that is the right call
   ;; rather than an omission — at the page counts this rule produces, the
   ;; streaming penalty is 1.06-1.36x, and trading cache reuse away to avoid
   ;; it would cost more than it saves. Caveat on that 1.06-1.36x: it came off
   ;; a machine at a load average of 68 across 10 cores and has not passed a
   ;; noise gate (machine-probe's :tlb probe refuses to restate it). It is
   ;; enough to say the penalty is small, not enough to size against — which
   ;; is exactly why nothing here sizes against it. The 5x figure from a pointer chase is
   ;; the wrong constant to design against; see machine/translation-regimes.
   :model/does-not-model [:associativity-conflicts :tlb-reach :prefetch :nuca-latency]
   ;; Honest status: this tile has NOT been shown to be the fast one. That is
   ;; different from having been shown wrong, and the distinction is the whole
   ;; entry.
   :model/validation
   {:status :partially-validated
    :attempted "2026-08-03, Apple M1 Max/performance, blocked ikj matmul n=768,
                f64, three operands, tiles 8..768"
    :predicted "48 against L1d (128 KiB), 256 against private L2 (3 MiB)"
    :result "no tile separated from any other. Two runs of the same sweep named
             different winners -- 384 then 48 -- and the best blocking beat the
             unblocked arm by 1-5%, which perfgate refused both times."
    :cause "the harness is loop-bound, not memory-bound. A Clojure/JVM inner
            loop costs about 4 ns per iteration against roughly 0.15 ns of
            memory traffic per iteration at this working-set size, so blocking
            can move at most a few percent of the total and cannot be
            separated from noise."
    :precondition "perfgate/detectable? on a pilot said the minimum detectable
                   improvement was 133% before the sweep ran. Check that first:
                   a tiling experiment is only informative when the memory term
                   dominates the loop term."
    :note "This says nothing about whether the capacity rule is right. It says
           this machine plus this harness cannot tell in WALL CLOCK, and that a
           validated tile needs an inner loop cheap enough for memory to
           dominate."
    :validated-without-a-clock
    "2026-08-04. Miss counts are a property of the access sequence, so they can
     be checked on a machine too loaded to time anything. Feeding computed
     matmul page traces to `paging` (n=24, 512 B pages, 6-page cache): the ikj
     order this library derives takes 234 misses where the textbook ijk takes
     5478, a tile sized for the level takes 96, and a tile too large takes 379
     -- LOSING to not tiling. So the capacity rule's SHAPE is confirmed, in
     misses rather than seconds: there is a right tile size, and being wrong
     about it is worse than not blocking. What remains unvalidated is the
     wall-clock consequence and the exact constant."
    :explained-by "traversal/tiling-benefit, added 2026-08-03. Fed the measured
                   inner loop (3.77 ns per multiply-add) and bandwidth
                   (30 GB/s), it predicts a 1.00x speedup from blocking --
                   which is what the sweep measured, and it predicts it BEFORE
                   the sweep. It also reports the threshold: the loop would
                   have to reach 0.27 ns per multiply-add, about one cycle,
                   for blocking to be worth measuring at all."}})

(defn pages-touched
  "How many distinct pages a strided 2D block lands on.

  A tile's byte size does not tell you this. The same 512 KiB tile sits on 32
  pages or on 512 depending only on the row stride of the matrix it is cut
  from, and the difference is measurable: 1.11 vs 1.40 ns per element on the
  part this was developed against, at identical bytes and identical run
  length.

  Two regimes, each exact in its own and wrong in the other, so it takes the
  smaller:

  - rows far apart (stride >= page): each row starts its own page, so the
    count is `rows * pages-per-row`
  - rows close together (stride < page): rows share pages and the block is
    nearly contiguous, so the count is the span divided by the page

  Assumes the block starts page-aligned. A misaligned start adds at most one
  page per row, and this deliberately does not pad for it: the number is a
  planning input, and inflating it would let it veto tiles on arithmetic
  rather than on measurement."
  [page-bytes {:keys [rows row-span-bytes row-stride-bytes]}]
  (when (and (pos-int? page-bytes) (pos-int? rows)
             (pos-int? row-span-bytes) (pos-int? row-stride-bytes))
    (let [ceil-div (fn [a b] (quot (+ a (dec b)) b))
          span (+ (* (dec rows) row-stride-bytes) row-span-bytes)
          per-row (* rows (ceil-div row-span-bytes page-bytes))
          contiguous (ceil-div span page-bytes)]
      (max 1 (min per-row contiguous)))))

(defn tile-plan
  "The largest square tile whose working set still fits a named cache level.

  `:arrays` is how many operands the inner block touches at once — 3 for
  `C += A*B`. `:occupancy` defaults to 0.5: a tile sized to the full capacity
  fits on paper and thrashes in practice, because the level also holds the
  stack, the code and whatever the sibling core is doing.

  The tile is rounded DOWN to a whole number of cache lines, so a tile row
  never straddles, and clamped to the extent."
  [machine {:keys [extents element-bytes arrays level kind occupancy]
            :or {arrays 3 level 2 kind :unified occupancy 0.5}}]
  (m/require-fact machine [:cpu :cache] "a cache hierarchy")
  (let [capacity (or (m/private-cache-bytes machine level kind)
                     (throw (ex-info "machine declares no cache at that level"
                                     {:phase :traversal/tile :level level :kind kind})))
        line (m/line-bytes machine)
        usable (long (* capacity occupancy))
        raw (long (Math/floor (Math/sqrt (double (/ usable (* arrays element-bytes))))))
        per-line (max 1 (quot line element-bytes))
        rounded (max per-line (* per-line (quot raw per-line)))
        tile (max 1 (apply min rounded extents))
        working-set (* arrays tile tile element-bytes)]
    (merge
    {:format format-id
     :tile/size tile
     :tile/arrays arrays
     :tile/level level
     :tile/kind kind
     :tile/capacity-bytes capacity
     :tile/occupancy occupancy
     :tile/usable-bytes usable
     :tile/working-set-bytes working-set
     :tile/fits? (<= working-set usable)
     :tile/elements-per-line per-line
     :tile/tiles (mapv #(quot (+ % (dec tile)) tile) extents)
     :tile/model tile-model
     :tile/machine (:machine/id machine)}
    ;; Pages are REPORTED, never sized against. The rule above still picks the
    ;; tile purely from bytes and capacity; this says what that choice costs in
    ;; translation so a caller can see it rather than discover it. Sizing
    ;; against it would need a validated penalty on this workload, and the
    ;; measurement so far says the streaming penalty is small enough that
    ;; trading cache reuse for it would be the worse deal.
    (let [page (get-in machine [:page :base-bytes])
          pages (some-> page
                        (pages-touched {:rows tile
                                        :row-span-bytes (* tile element-bytes)
                                        :row-stride-bytes (* (first extents)
                                                             element-bytes)})
                        (* arrays))]
      (cond-> {}
        pages (assoc :tile/pages-touched pages)
        pages (assoc :tile/translation-penalty
                     ;; Named regime, no default: a blocked kernel streams.
                     ;; `nil` here means the machine carries no measured curve,
                     ;; which is a missing fact and not a penalty of 1.0.
                     (m/translation-penalty machine pages :streaming)))))))

(defn tile-origins
  "Origins of every tile covering `extents`, in row-major tile order."
  [[w h] tile]
  (vec (for [ty (range 0 h tile) tx (range 0 w tile)] [tx ty])))

;; ── loop order ───────────────────────────────────────────────────────────

(defn- access-cost
  "Cost of a loop's stride for one array, in lines.

  Stride 0 is free — the reference is invariant in that loop and hoists.
  Stride 1 is the unit-stride ideal. Beyond one line's worth of elements the
  cost stops growing: you were already paying a whole line per access, and a
  larger stride cannot make you pay more than that."
  [stride elements-per-line]
  (cond
    (zero? stride) 0
    :else (min stride elements-per-line)))

(defn loop-order
  "Which loop belongs innermost, derived rather than remembered.

  `accesses` is `[{:array :A :strides {:i 512 :k 1 :j 0}} …]` — the element
  stride each loop induces in each array. Loops are ordered by total cost
  descending, so the cheapest ends up innermost.

  For `C[i][j] += A[i][k] * B[k][j]` at N=512 this returns `[:i :k :j]` — the
  textbook `ikj` — because `j` is the only loop under which no array strides
  badly."
  [machine loops accesses element-bytes]
  (m/require-fact machine [:cpu :cache] "a cache hierarchy")
  (let [per-line (max 1 (quot (m/line-bytes machine) element-bytes))
        scored (mapv (fn [l]
                       {:loop l
                        :cost (reduce + 0 (map #(access-cost (get-in % [:strides l] 0) per-line)
                                               accesses))
                        :strides (into {} (map (juxt :array #(get-in % [:strides l] 0)) accesses))})
                     loops)
        ;; Worst outermost, cheapest innermost. Name breaks ties so the
        ;; result is a total order and two runs agree.
        ranked (vec (sort-by (juxt (comp - :cost) (comp str :loop)) scored))]
    {:format format-id
     :loop/order (mapv :loop ranked)
     :loop/innermost (:loop (last ranked))
     :loop/ranked ranked
     :loop/elements-per-line per-line
     :loop/machine (:machine/id machine)}))

;; ── is tiling worth anything here? ───────────────────────────────────────

(def tiling-benefit-model
  {:model/id :kotoba.traversal.tiling-benefit/v2
   :model/rule "time(T) = combine(loop-ns * n^3, traffic-bytes(T) / bandwidth)
                where combine is `max` when the access pattern is
                prefetch-friendly and `+` when it is not"
   :model/overlap
   {:full "max — a hardware prefetcher covers the latency, so the loop and the
           memory system run concurrently and the slower one is the cost.
           Applies when the inner access is unit-stride."
    :none "+ — every miss stalls the pipeline, so the costs add. Applies when
           the stride defeats the prefetcher, which for a blocked matmul means
           the unblocked arm walking B with a row-sized stride."
    :measured "v1 used `max` unconditionally and under-predicted an unblocked
               NEON matmul by 2.7x. With no-overlap and the right bandwidth it
               predicts 4278 ms against 4282 measured."}
   :model/bandwidth-is-not-one-number
   "The bandwidth constant belongs to the machine AND the access pattern, not
    to the machine alone. The same M1 Max gives 30 GB/s on a line-strided scan
    of a contiguous array and 10.8 GB/s to an unblocked matmul walking B with a
    12 KiB stride. Feeding the first number to a plan about the second is what
    made v1 predict 1.00x where measurement gave 2.69x. Measure bandwidth at
    the stride the arm being modelled actually uses."
   :model/traffic
   {:blocked "2*n^3/T + n^2 elements — each of the n^3/T^3 block triples moves
              3*T^2 elements, plus C written once"
    :unblocked "n^3 + 2*n^2 elements — B is re-streamed once per i when it does
                not fit, A and C move once"}
   :model/assumes
   ["one level of blocking, square tiles, the operand that gets re-streamed is B"
    "a tile whose working set fits the named level stays there for the block triple"
    "loop and memory overlap perfectly, so the slower one is the whole cost"]
   :model/does-not-model [:tlb-reach :associativity-conflicts :register-blocking :prefetch]
   :model/validation
   {:date "2026-08-03"
    :machine "Apple M1 Max/performance"
    :held-out "A C -O2 blocked ikj matmul at n=768, tiles 16 to 768, interleaved
               across rounds so thermal drift penalises every tile equally."
    :kernel "0.517 ns per multiply-add — above the 0.27 ns threshold this model
             reports, so it predicts blocking buys nothing."
    :predicted-speedup 1.00
    :measured-speedup 1.062
    :verdict "Held. The model said 1.00x and the best tile (48) managed 1.06x,
              which is 6% and inside the run-to-run spread of this harness. The
              same sweep on the JVM at 3.77 ns/madd was flat, and this one at
              0.517 is very nearly flat — consistent with a threshold at 0.27."
    :caveat "The loop-ns constant was taken from the UNBLOCKED arm, so the
             model reproducing that arm's absolute time (234 ms predicted
             against 234.15 measured) is circular and proves nothing. The
             speedup between the arms is the part that was actually predicted."
    :other-side "Tested 2026-08-03 with a hand-written NEON kernel at n=1536,
                 where B is 18 MiB and does not fit L2. Blocking gave 2.688x --
                 so yes, past the threshold regime tiling matters a great deal.
                 But v1 PREDICTED 1.00x for it, which is why this model is now
                 v2: the failure was two independent errors, a bandwidth
                 constant measured at the wrong stride and a max() that assumed
                 an overlap the stride destroys. With 10.8 GB/s and no overlap
                 it predicts 2.69x. See the v2 notes above."}})

(defn tiling-benefit
  "What blocking can buy, before anyone runs it.

  `tile-plan` answers *how big a tile fits*. This answers the prior question —
  *is there anything for a tile to win* — and the two are independent. A tile
  can be perfectly sized and buy nothing, which is exactly what happened when
  `tile-plan`'s answer was measured on a JVM matmul: every block width from 8
  to 768 landed within 1.2x of every other.

  The reason is visible in one comparison. Blocking only moves the memory
  term, so it can only matter when the memory term is the larger one. Both
  `loop-ns-per-op` and `bandwidth-bytes-per-ns` must be measured somewhere
  the *other* one is not the bottleneck — see `machine-probe`'s calibrate
  path, and the 65% error that came of getting that wrong."
  [machine {:keys [n element-bytes arrays tile loop-ns-per-op bandwidth-bytes-per-ns
                   overlap]
            :or {element-bytes 8 arrays 3 overlap :full}}]
  (let [combine (case overlap :full max :none +)
        ;; The two arms walk different strides, so they sit at different points
        ;; on the machine's bandwidth curve. Unblocked, B is re-streamed with a
        ;; whole ROW between consecutive k steps; blocked, the tile is resident
        ;; and the walk within it is contiguous. Sharing one figure between
        ;; them is exactly what made v1 predict 1.00x against a measured 2.69x.
        unblocked-stride (* n element-bytes)
        blocked-stride element-bytes
        bw-for (fn [stride]
                 (or bandwidth-bytes-per-ns
                     (m/bandwidth-at-stride machine (long stride))
                     (throw (ex-info "no bandwidth for this arm"
                                     {:phase :traversal/tiling-benefit
                                      :machine/id (:machine/id machine)
                                      :stride-bytes (long stride)
                                      :remedy "pass :bandwidth-bytes-per-ns, or give the machine a measured :bandwidth curve"}))))
        n (double n)
        ops (* n n n)
        loop-ns (* loop-ns-per-op ops)
        traffic (fn [elements bw] (/ (* elements (double element-bytes)) bw))
        blocked-elements (+ (/ (* 2.0 ops) (double tile)) (* n n))
        unblocked-elements (+ ops (* 2.0 n n))
        blocked-bw (bw-for blocked-stride)
        unblocked-bw (bw-for unblocked-stride)
        blocked-mem (traffic blocked-elements blocked-bw)
        unblocked-mem (traffic unblocked-elements unblocked-bw)
        ;; Blocking exists to make the working set cache-resident, so the
        ;; blocked arm is prefetch-friendly whatever the unblocked arm does.
        ;; Only the unblocked arm gets the caller's overlap verdict.
        blocked-time (max loop-ns blocked-mem)
        unblocked-time (combine loop-ns unblocked-mem)]
    {:format format-id
     :tile tile
     :ops ops
     :loop-ns loop-ns
     :blocked {:stride-bytes (long blocked-stride) :bandwidth-bytes-per-ns blocked-bw
               :memory-ns blocked-mem :time-ns blocked-time
               :bound-by (if (> blocked-mem loop-ns) :memory :loop)}
     :unblocked {:stride-bytes (long unblocked-stride) :bandwidth-bytes-per-ns unblocked-bw
                 :memory-ns unblocked-mem :time-ns unblocked-time
                 :bound-by (if (> unblocked-mem loop-ns) :memory :loop)}
     :overlap overlap
     :achievable-speedup (/ unblocked-time blocked-time)
     ;; Both, always, because choosing between them needs a fact about the
     ;; stride that this function is not given.
     :speedup-bounds {:optimistic (/ (max loop-ns unblocked-mem) blocked-time)
                      :pessimistic (/ (+ loop-ns unblocked-mem) blocked-time)}
     ;; The whole point. When this is false, tiling is unmeasurable here no
     ;; matter how well the tile is chosen, and a sweep will return noise.
     :worth-tiling? (> unblocked-mem loop-ns)
     ;; And if it is false: how fast would the inner loop have to get? Solving
     ;; unblocked-mem > loop-ns * ops for loop-ns gives the threshold, which is
     ;; a more useful thing to report than "no".
     :loop-ns-threshold (/ unblocked-mem ops)
     :model tiling-benefit-model
     :machine (:machine/id machine)}))
