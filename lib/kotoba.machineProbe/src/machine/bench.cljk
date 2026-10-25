(ns machine.bench
  "Running a measurement on the machine the probe just described.

  The other half of the same host effect. `machine.probe` reads the static
  facts; this runs the dynamic ones. Both exist because `machine` is a
  contract that may not probe and `perfgate` is an assurance layer that may
  not benchmark — somebody has to actually touch the device, and it is this
  namespace, in one place, on purpose.

  The point is not to produce a fast number. It is to close the loop:
  `layout` *predicts* a cache-line count from a descriptor, this *measures*
  wall time on the machine that descriptor describes, and `perfgate` decides
  whether the difference survives the noise. A prediction nobody checked
  against a device is the thing this whole stack was built to stop shipping.

  JVM-only, and honest about that: the JIT, the GC and a laptop's thermal
  governor are all in the measurement. Warmup runs before samples, samples are
  reported raw, and `perfgate` is what decides whether they mean anything."
  (:require [layout.core :as l]
            [perfgate.core :as pg]
            [machine.core :as m]))

;; ── the two layouts, as actual arrays ────────────────────────────────────
;;
;; A particle with x, y, z, mass. AoS is one array with the four values
;; adjacent per element; SoA is four arrays. Both hold identical values, and
;; both passes sum only `x` — the access pattern where the layouts diverge.

(def fields
  [{:name :x :bytes 8 :align 8}
   {:name :y :bytes 8 :align 8}
   {:name :z :bytes 8 :align 8}
   {:name :mass :bytes 8 :align 8}])

(defn make-aos ^doubles [^long n ^long width]
  (let [a (double-array (* width n))]
    (dotimes [i n] (aset a (* width i) (double i)))
    a))

(defn make-soa ^doubles [^long n]
  (let [xs (double-array n)]
    (dotimes [i n] (aset xs i (double i)))
    xs))

(defn sum-aos ^double [^doubles a ^long n ^long width]
  (loop [i 0 acc 0.0]
    (if (< i n)
      (recur (inc i) (+ acc (aget a (* width i))))
      acc)))

(defn sum-soa ^double [^doubles xs ^long n]
  (loop [i 0 acc 0.0]
    (if (< i n)
      (recur (inc i) (+ acc (aget xs i)))
      acc)))

;; ── sampling ─────────────────────────────────────────────────────────────

(defn- time-ns
  "Nanoseconds for one call of `f`, with the result consumed so the JIT cannot
  delete the loop it was asked to time."
  [f]
  (let [t0 (System/nanoTime)
        r (f)
        t1 (System/nanoTime)]
    (when (Double/isNaN r) (throw (ex-info "impossible" {:r r})))
    (- t1 t0)))

(defn samples
  "`reps` timings of `f`, after `warmup` untimed calls.

  Warmup exists because the first few passes measure the JIT rather than the
  memory system. It is not a way to make the numbers look better — the raw
  samples still go to `perfgate`, which refuses them if they are too noisy to
  mean anything."
  [f {:keys [warmup reps] :or {warmup 5 reps 12}}]
  (dotimes [_ warmup] (f))
  (vec (repeatedly reps #(time-ns f))))

;; ── the loop that closes ─────────────────────────────────────────────────

(defn fields-of
  "`width` doubles per element, only the first of which the pass reads."
  [width]
  (mapv (fn [i] {:name (keyword (str "f" i)) :bytes 8 :align 8}) (range width)))

(defn predicted
  "What `layout` says the two layouts cost on this machine, before running.

  Note what the descriptor changes: on a 128-byte line an 8-byte field gives
  16 elements per line, so a 32-byte AoS element wastes three quarters of
  every line. On the 64-byte line of `machine.core/portable-64` the same
  computation gives the same ratio, but every absolute line count halves —
  which is why a prediction has to name the machine it was made on."
  [machine n width]
  (let [fs (fields-of width)
        access {:access/fields #{:f0} :access/stride 1}
        aos (l/cost machine (l/aos machine fs) n access)
        soa (l/cost machine (l/soa machine fs) n access)]
    {:aos aos
     :soa soa
     :line-bytes (m/line-bytes machine)
     :predicted-ratio (double (/ (:cost/lines aos) (:cost/lines soa)))}))

(defn run
  "Measure both layouts on `machine` and return raw samples plus the prediction.

  `n` defaults to two million elements: 64 MiB as an array of structs, well
  past this machine's 12 MiB L2, so the pass is memory-bound and the layout is
  what is actually being measured. A working set that fits in cache measures
  the loop overhead instead, and reports a ratio near 1.0 that means nothing."
  ([machine] (run machine {}))
  ([machine {:keys [n width] :or {n 2000000 width 4} :as opts}]
   (let [aos (make-aos n width)
         soa (make-soa n)]
     {:n n
      :width width
      :machine-id (:machine/id machine)
      :prediction (predicted machine n width)
      :aos-samples (samples #(sum-aos aos n width) opts)
      :soa-samples (samples #(sum-soa soa n) opts)})))

;; ── bandwidth saturation ─────────────────────────────────────────────────
;;
;; The single-threaded run said 2.02x against a predicted 16x. The obvious
;; hypothesis for the gap is that one core cannot ask for enough bandwidth to
;; make bandwidth the bottleneck: the prefetcher hides the latency, and a
;; machine with hundreds of GB/s to give has plenty left over. If that is
;; right, adding cores should push the measured ratio toward the byte ratio,
;; because every added core competes for the same memory system.
;;
;; If it is wrong — if the ratio stays flat as cores are added — then the gap
;; is somewhere else and the hypothesis has to be thrown away rather than
;; explained around.

(defn sum-aos-range ^double [^doubles a ^long from ^long to ^long width]
  (loop [i from acc 0.0]
    (if (< i to)
      (recur (inc i) (+ acc (aget a (* width i))))
      acc)))

(defn sum-soa-range ^double [^doubles xs ^long from ^long to]
  (loop [i from acc 0.0]
    (if (< i to)
      (recur (inc i) (+ acc (aget xs i)))
      acc)))

(defn- parallel
  "Split `n` into `threads` contiguous slices and sum them concurrently.

  Contiguous rather than interleaved on purpose: interleaving would put
  several threads on the same cache lines and measure false sharing instead
  of bandwidth."
  ^double [threads ^long n slice-fn]
  (let [chunk (quot n threads)
        fs (mapv (fn [t]
                   (let [from (* t chunk)
                         to (if (= t (dec threads)) n (* (inc t) chunk))]
                     (future (slice-fn from to))))
                 (range threads))]
    (reduce + 0.0 (map deref fs))))

(defn run-scaling
  "Measure both layouts at each thread count in `thread-counts`.

  Returns one entry per thread count, each with raw samples for both arms, so
  every point can be handed to `perfgate` separately. A scaling curve whose
  points were never individually gated is a shape, not a result."
  [machine {:keys [n width thread-counts] :or {n 2000000 width 16 thread-counts [1 2 4 8]}
            :as opts}]
  (let [aos (make-aos n width)
        soa (make-soa n)]
    {:n n
     :width width
     :machine-id (:machine/id machine)
     :prediction (predicted machine n width)
     :points (mapv (fn [t]
                     {:threads t
                      :aos-samples (samples #(parallel t n (fn [from to]
                                                             (sum-aos-range aos from to width)))
                                            opts)
                      :soa-samples (samples #(parallel t n (fn [from to]
                                                             (sum-soa-range soa from to)))
                                            opts)})
                   thread-counts)}))

;; ── blocked matrix multiply ──────────────────────────────────────────────
;;
;; `traversal/tile-plan` picks a tile from a cache capacity. Whether that tile
;; is the fastest one is a different question from whether it fits, and the
;; roofline lesson says to check before believing: a model can be arithmetically
;; right about bytes and still be answering a question the machine does not ask.
;;
;; Loop order is fixed to blocked `ikj` — the order `traversal/loop-order`
;; derives — so that what varies across the sweep is the tile and nothing else.

(defn matmul-tiled
  "C += A*B for n x n row-major f64, blocked at `tile`. `tile` >= n is unblocked."
  ;; No primitive hints on n/tile: Clojure caps primitive-taking fns at four
  ;; args, and the arrays have to stay hinted or every aget boxes.
  [^doubles a ^doubles b ^doubles c n tile]
  (let [n (long n) tile (long tile)]
   (loop [ii 0]
    (when (< ii n)
      (loop [kk 0]
        (when (< kk n)
          (loop [jj 0]
            (when (< jj n)
              (let [imax (min n (+ ii tile))
                    kmax (min n (+ kk tile))
                    jmax (min n (+ jj tile))]
                (loop [i ii]
                  (when (< i imax)
                    (let [irow (* i n)]
                      (loop [k kk]
                        (when (< k kmax)
                          (let [aik (aget a (+ irow k))
                                krow (* k n)]
                            (loop [j jj]
                              (when (< j jmax)
                                (aset c (+ irow j)
                                      (+ (aget c (+ irow j)) (* aik (aget b (+ krow j)))))
                                (recur (inc j)))))
                          (recur (inc k)))))
                    (recur (inc i)))))
              (recur (+ jj tile))))
          (recur (+ kk tile))))
      (recur (+ ii tile))))))

(defn- filled ^doubles [^long n]
  (let [a (double-array (* n n))]
    (dotimes [i (* n n)] (aset a i (double (mod i 97))))
    a))

(defn run-tiling
  "Time `matmul-tiled` across `tiles`, everything else held fixed.

  C is zeroed inside the timed region for every arm, so the memset is a
  constant that cannot favour one tile over another."
  [{:keys [n tiles] :or {n 768} :as opts}]
  (let [a (filled n) b (filled n) c (double-array (* n n))
        tiles (or tiles [8 16 32 48 64 128 256 384 n])]
    {:n n
     :flops (* 2.0 n n n)
     :points (mapv (fn [t]
                     {:tile t
                      :samples (samples (fn []
                                          (java.util.Arrays/fill c 0.0)
                                          (matmul-tiled a b c n t)
                                          (aget c 0))
                                        opts)})
                   tiles)}))

;; ── breaking the dependency chain ────────────────────────────────────────
;;
;; 3.03 ns per element for a sequential f64 sum is about ten cycles on this
;; machine, which is far too many for one load and one add. The memory system
;; is not the reason: 16 MiB in 6 ms is 2.7 GB/s, a small fraction of what the
;; part delivers. The reason is the loop-carried dependency on the accumulator
;; — every add waits for the previous add's result, so the loop runs at
;; floating-point add latency rather than throughput.
;;
;; The fix is the classic one and it is not a micro-optimization: four
;; independent accumulators let four adds be in flight at once. It matters
;; here beyond speed, because a loop this slow makes every memory experiment
;; in this repo unable to see the memory system at all.

(defn sum-soa-unrolled
  "Same sum, four independent accumulators."
  ^double [^doubles xs n]
  (let [n (long n)
        limit (- n 3)]
    (loop [i 0 a0 0.0 a1 0.0 a2 0.0 a3 0.0]
      (if (< i limit)
        (recur (+ i 4)
               (+ a0 (aget xs i))
               (+ a1 (aget xs (+ i 1)))
               (+ a2 (aget xs (+ i 2)))
               (+ a3 (aget xs (+ i 3))))
        (loop [i i acc (+ (+ a0 a1) (+ a2 a3))]
          (if (< i n) (recur (inc i) (+ acc (aget xs i))) acc))))))

(defn sum-aos-unrolled
  "Same, striding by `width` elements per accumulator."
  ^double [^doubles a n width]
  (let [n (long n) width (long width)
        limit (- n 3)
        w2 (* 2 width) w3 (* 3 width) w4 (* 4 width)]
    (loop [i 0 o 0 a0 0.0 a1 0.0 a2 0.0 a3 0.0]
      (if (< i limit)
        (recur (+ i 4) (+ o w4)
               (+ a0 (aget a o))
               (+ a1 (aget a (+ o width)))
               (+ a2 (aget a (+ o w2)))
               (+ a3 (aget a (+ o w3))))
        (loop [i i o o acc (+ (+ a0 a1) (+ a2 a3))]
          (if (< i n) (recur (inc i) (+ o width) (+ acc (aget a o))) acc))))))

(defn run-unrolled
  "Both layouts with the dependency chain broken, alongside the original."
  [machine {:keys [n width] :or {n 2000000 width 16} :as opts}]
  (let [aos (make-aos n width)
        soa (make-soa n)]
    {:n n :width width
     :machine-id (:machine/id machine)
     :prediction (predicted machine n width)
     :serial {:aos (samples #(sum-aos aos n width) opts)
              :soa (samples #(sum-soa soa n) opts)}
     :unrolled {:aos (samples #(sum-aos-unrolled aos n width) opts)
                :soa (samples #(sum-soa-unrolled soa n) opts)}}))

;; ── independent calibration ──────────────────────────────────────────────
;;
;; `layout/achievable-ratio` needs a loop floor and a bandwidth. Taking the
;; first from the candidate arm and the second from the baseline arm makes the
;; formula reproduce those two timings by construction — an identity dressed
;; as a prediction, which is what happened here on 2026-08-03 before anyone
;; noticed. These two measurements exist so the constants come from somewhere
;; else entirely, and the model can then be asked about a configuration nobody
;; has run.

(defn loop-floor-ns
  "Nanoseconds per element with memory effectively free.

  A working set small enough to sit in L1 makes the memory term vanish, so
  what is left is the loop: index arithmetic, bounds check, the add. This is
  the term `achievable-ratio` calls `loop-ns-per-element`, and measuring it
  here rather than reading it off the arm being explained is the whole point."
  [{:keys [elements] :or {elements 2048} :as opts}]
  (let [xs (make-soa elements)
        ;; Many passes over the same small array: the loop cost dominates and
        ;; the timer's own resolution does not.
        passes 2000
        s (samples (fn [] (loop [p 0 acc 0.0]
                            (if (< p passes)
                              (recur (inc p) (+ acc (sum-soa-unrolled xs elements)))
                              acc)))
                   opts)
        mean (/ (reduce + 0.0 s) (count s))]
    {:elements elements
     :passes passes
     :samples s
     :ns-per-element (/ mean (* (double elements) passes))
     :working-set-bytes (* 8 elements)}))

(defn bandwidth-bytes-per-ns
  "Bytes per nanosecond a single thread observes on a streaming read.

  **A contiguous f64 sum cannot measure this, and the first version of this
  function tried to.** Each iteration of that loop touches 8 bytes and costs
  0.766 ns, so it caps at 10.4 GB/s no matter how fast the memory is — what
  comes back is the loop floor wearing different units, and feeding it to
  `achievable-ratio` produced a prediction 65% wrong (it over-predicted the
  AoS arm by 2.9x, because that arm really did reach 31.5 GB/s).

  So the scan is strided by a full cache line: every touched element pulls
  `line-bytes` and the loop cost is amortised over all of them, which puts the
  memory system back in charge. Stride and size are both different from
  anything `achievable-ratio` is asked to predict."
  [machine {:keys [elements] :or {elements 6000000} :as opts}]
  (let [line (or (m/line-bytes machine) 64)
        stride (quot line 8)
        xs (make-soa elements)
        touched (quot elements stride)
        s (samples #(sum-aos-unrolled xs touched stride) opts)
        mean (/ (reduce + 0.0 s) (count s))]
    {:elements elements
     :stride stride
     :touched touched
     :samples s
     ;; Bytes MOVED, not bytes summed: a strided touch pulls a whole line.
     :bytes-per-ns (/ (* (double line) touched) mean)
     :working-set-bytes (* 8 elements)}))

;; ── the bandwidth curve ──────────────────────────────────────────────────
;;
;; `bandwidth-bytes-per-ns` above measures ONE point, at a line stride. That
;; single number was handed to two planners this afternoon that needed a
;; different one, and both were wrong as a result. `machine.core` now carries
;; a curve; this produces it.
;;
;; The loop is not a limit here the way it was for the contiguous sum: each
;; iteration touches one cache line, so at ~0.8 ns/iteration the ceiling is
;; over 150 GB/s and the memory system is comfortably in charge at every
;; stride measured.

(defn bandwidth-curve
  "Bytes per nanosecond at each stride, as `machine.core`'s `:bandwidth` map.

  One f64 touched every `S` bytes over a `bytes`-sized working set. Bytes
  MOVED counts a whole line per touch once `S` reaches the line width, which
  is what the memory system actually transfers.

  The working set must be large enough that the touched lines do not fit in
  cache. At a 64 KiB stride over 256 MiB only 4096 lines are touched — half a
  megabyte — so that point measures TLB reach rather than DRAM bandwidth, and
  is reported rather than hidden because that is exactly the regime a
  page-strided planner is asking about."
  [machine {:keys [bytes strides] :or {bytes (* 256 1024 1024)} :as opts}]
  (let [line (or (m/line-bytes machine) 64)
        strides (or strides (vec (take-while #(<= % (quot bytes 1024))
                                             (iterate #(* 2 %) line))))
        n (quot bytes 8)
        xs (make-soa n)]
    {:working-set-bytes bytes
     :line-bytes line
     :by-stride
     (into (sorted-map)
           (for [s strides
                 :let [step (quot s 8)
                       touches (quot n step)
                       samples (samples #(sum-aos-unrolled xs touches step) opts)
                       mean (/ (reduce + 0.0 samples) (count samples))]]
             [s (/ (* (double line) touches) mean)]))
     ;; The runtime is part of the provenance, not a detail. Measured on this
     ;; machine, a C -O2 loop and this JVM loop disagree by 4x at a 128-byte
     ;; stride (24.1 against 6.2 GB/s) and by less than 10% at 16 KiB, and the
     ;; curves differ in SHAPE as well as scale -- the JVM's peak sits at
     ;; 2 KiB where C's sits at 1 KiB. So a curve measured here describes
     ;; JVM-on-this-machine, and feeding it to a model of native code would be
     ;; the same category error as feeding a contiguous-scan number to a
     ;; page-strided plan.
     :source (str "machine.bench/bandwidth-curve on "
                  (System/getProperty "java.vm.name") " "
                  (System/getProperty "java.version")
                  ": one f64 every S bytes over " (quot bytes 1048576) " MiB")
     :runtime :jvm}))

;; ── translation (TLB) ────────────────────────────────────────────────────
;;
;; Two walks over the SAME bytes with the SAME cache pressure, differing only
;; in how many pages those bytes sit on. That is the whole design: if page
;; count is held to be the cause, then line count -- and therefore cache
;; pressure -- has to be held fixed, or the result is just a cache curve
;; wearing a TLB costume.

(def ^:private ^:const LINE-LONGS 16)   ; 128-byte line / 8

(defn chase-over
  "A pointer chase touching `lines-per-page` lines on each of `pages` pages.

  The total number of distinct lines is `pages * lines-per-page`, so a sweep
  that doubles pages while halving lines-per-page holds the cache footprint
  exactly constant and varies only the page spread. Page order is shuffled so
  neither the prefetcher nor the page walker gets a run of ascending pages to
  work with."
  ^longs [^long pages ^long lines-per-page ^long page-bytes ^long seed]
  (let [lpp (quot page-bytes 8)
        total (* pages lines-per-page)
        a (long-array (* pages lpp))
        idx (long-array total)
        r (java.util.Random. seed)]
    ;; Stagger which line inside the page is touched, by page index. Without
    ;; this, one-line-per-page puts every touched line at a page boundary --
    ;; all 16 KiB apart and therefore congruent to the same handful of cache
    ;; sets -- and the arm measures L1 conflict misses while being read as
    ;; translation. Measured on this machine at 2048 pages: 86.83 ns aligned
    ;; against 26.42 ns staggered, same page count and same line count, a 3.29x
    ;; artifact. The line count and page count are unchanged by staggering, so
    ;; the quantity under study is not.
    (let [lines-per-pg (quot page-bytes (* LINE-LONGS 8))]
      (dotimes [k total]
        (let [pg (quot k lines-per-page)
              within (rem (+ (rem k lines-per-page) (rem pg lines-per-pg))
                          lines-per-pg)]
          (aset idx k (+ (* pg lpp) (* within LINE-LONGS))))))
    (loop [i (dec total)]
      (when (pos? i)
        (let [j (.nextInt r (inc i)) t (aget idx i)]
          (aset idx i (aget idx j)) (aset idx j t) (recur (dec i)))))
    (dotimes [k total] (aset a (aget idx k) (aget idx (rem (inc k) total))))
    a))

(defn chase ^long [^longs a ^long start ^long steps]
  (loop [i 0 p start] (if (< i steps) (recur (inc i) (aget a p)) p)))

(def ^:private ^:const TILE-COLS 128)   ; 1 KiB run -- identical in every arm
(def ^:private ^:const TILE-VISITS 4)   ; revisit, so translation cost recurs

(defn ^:private row-run
  "Sum one contiguous run. Split out so the scan below never threads an
  accumulator across nested loops, which is what boxes it."
  ^double [^doubles a ^long base]
  (loop [c 0 s 0.0] (if (>= c TILE-COLS) s (recur (inc c) (+ s (aget a (+ base c)))))))

(defn tile-scan
  "Stream over tiles of `rpt` rows, `TILE-COLS` wide, from a matrix `w` wide.

  Tile shape and contiguous run length are identical whatever `w` is, so the
  only thing `w` changes is how many pages a tile lands on. Without that
  control a shape sweep confounds page count with run length, and the run
  length is what the prefetcher cares about."
  ^double [^doubles a ^long w ^long rpt]
  (let [h (quot (alength a) w)
        sink (double-array 1)]
    (loop [r0 0]
      (when (< r0 h)
        (let [end (min h (+ r0 rpt))]
          (loop [v 0]
            (when (< v TILE-VISITS)
              (loop [r r0]
                (when (< r end)
                  (aset sink 0 (+ (aget sink 0) (row-run a (* r w))))
                  (recur (inc r))))
              (recur (inc v))))
          (recur (+ r0 rpt)))))
    (aget sink 0)))

(defn arm-statistic
  "The one number that stands for an arm: the MEAN.

  Not the minimum, though a minimum is the usual choice for a latency
  microbenchmark and for a good reason -- it rejects preemption. That is
  exactly why it is wrong here. `perfgate` decides whether an arm may be
  stated at all, and its separation rule is about means: qualifying needs
  `mean_b - mean_c > sd_b + sd_c`. Reporting a minimum and then judging it
  with a threshold calibrated for means compares a bound against a different
  quantity than the one it bounds.

  It also defeats the gate on purpose. The minimum is the statistic that
  survives a loaded machine, so a min-reported curve looks steady while the
  samples underneath are not -- measured here, batch minima came out at
  0.22-0.49 relative spread where the raw samples were at 0.59-1.01. Both are
  far over the allowed 0.10; the minimum simply hid how far.

  Every other curve in this namespace already reports a mean. This makes the
  translation curve stop being the exception."
  ^double [xs]
  (/ (reduce + 0.0 xs) (count xs)))

(defn- normalise
  "Times -> penalties relative to the cheapest arm, so the fact survives the
  machine getting faster and the flat region reads as exactly 1.0."
  [by-pages]
  (let [best (apply min (vals by-pages))]
    (into (sorted-map) (for [[p t] by-pages] [p (/ (Math/round (* 100.0 (/ t best))) 100.0)]))))

(defn translation-curve
  "Measure both translation regimes and return a `machine` `:tlb` fact.

  The two curves are not two estimates of one number. A dependent chase has no
  memory-level parallelism to hide a page walk behind and pays the cost in
  full; a streaming walk has plenty and mostly does not. On the part this was
  developed against the same page spread costs 5x under one and 1.36x under
  the other, which is why `machine/translation-penalty` makes the caller name
  the regime instead of guessing."
  ([machine] (translation-curve machine {}))
  ([machine {:keys [page-bytes reps warmup rows max-rsd]
             :or {reps 7 warmup 3 rows 512
                  max-rsd (:policy/max-relative-stdev pg/default-policy)}}]
   (let [page (or page-bytes (get-in machine [:page :base-bytes]) 4096)
         ;; constant 2048 lines across the whole dependent sweep
         chase-arms (for [[pages lpp] [[16 128] [32 64] [64 32] [128 16]
                                       [256 8] [512 4] [1024 2] [2048 1]]]
                      (let [a (chase-over pages lpp page 7)
                            ;; Long enough that one scheduler preemption is a
                            ;; small fraction of a sample. At 300k steps a
                            ;; sample ran 3-25 ms and a single ~5 ms migration
                            ;; moved it by tens of percent; at 3M it is 30-250
                            ;; ms and the same event is noise instead of the
                            ;; signal. This lowers spread by making the
                            ;; measurement longer, not by hiding anything --
                            ;; the alternative, relaxing the gate, would.
                            steps 3000000
                            f #(double (chase a 0 steps))
                            ts (samples f {:warmup warmup :reps reps})]
                        [pages (/ (arm-statistic ts) steps) ts]))
         ;; constant 512 KiB tile and constant 1 KiB run across every arm
         ;; Total matrix bytes held CONSTANT across the arms, by scaling the
         ;; row count inversely with the stride. Without this the arms differ
         ;; in footprint as well as in page spread -- 8 MiB at w=128 against
         ;; 1 GiB at w=4096 -- so a difference between them could be the
         ;; allocation rather than the translation, and the widest arm pays
         ;; page-fault and GC costs the narrowest never sees. Measured, that
         ;; showed up as streaming arms swinging 109-245% between runs while
         ;; the chase arms stayed at 10-35%.
         total-doubles (* 8192 4096)
         stream-arms (for [w [TILE-COLS (* TILE-COLS 4) 2048 4096]]
                       (let [h (quot total-doubles w)
                             a (double-array (* h w) 1.0)
                             f #(tile-scan a w rows)
                             ts (samples f {:warmup warmup :reps reps})
                             elems (* h TILE-COLS TILE-VISITS)
                             pages-per-tile (min rows
                                                 (long (Math/ceil (/ (* rows (* w 8.0)) page))))]
                         [pages-per-tile (/ (arm-statistic ts) elems) ts]))
         spread-of (fn [regime arms]
                     (into (sorted-map)
                           (for [[pages _ ts] arms]
                             [pages (:relative-stdev (pg/summarize ts))])))
         sample-spread {:dependent (spread-of :dependent chase-arms)
                        :streaming (spread-of :streaming stream-arms)}
         refusals (for [[regime by-pages] sample-spread
                        [pages rsd] by-pages
                        :when (> rsd max-rsd)]
                    {:regime regime :pages pages :relative-stdev rsd
                     :allowed max-rsd})
         refusals (vec refusals)]
     (when (seq refusals)
       ;; Two runs of this probe once produced 2.74x and 2.13x for the same
       ;; arm, and the verdict line flipped between them. A fact that changes
       ;; every run is not a fact, and emitting one with a straight face is
       ;; worse than emitting nothing -- `traversal` would size against it.
       (throw (ex-info "translation curve too noisy to emit"
                       {:phase :machine.bench/translation-curve
                        :refusals (vec refusals)
                        :note (str "quiet the machine. Taking more samples does NOT "
                                   "fix this: the gate tests per-sample relative "
                                   "stdev, which preemption does not average away -- "
                                   "measured here, going from 7 reps to 25 moved one "
                                   "arm from 0.166 to 0.507. More samples characterise "
                                   "the noise better rather than reducing it. perfgate "
                                   "refuses arms above " max-rsd " relative stdev.")})))
     ;; Provenance, not diagnostics. `machine` already requires :source and
     ;; :runtime because a figure nobody can place is a figure nobody can
     ;; trust; how well-determined each entry was belongs in the same
     ;; category, and a consumer deciding whether to plan against a 1.31x
     ;; penalty is better off knowing that entry sat at 0.12 spread.
     {:sample-spread sample-spread
      :penalty-by-pages
      {:dependent (normalise (into {} (map (fn [[p t _]] [p t]) chase-arms)))
       ;; later arms can land on the same page count once the stride passes a
       ;; page; keep the slower, which is the one a planner should hear about
       :streaming (normalise (reduce (fn [m [p t _]] (update m p (fnil max 0.0) t))
                                     {} stream-arms))}
      :source (str "machine.bench/translation-curve on "
                   (System/getProperty "java.vm.name") " "
                   (System/getProperty "java.version")
                   ": one line per page held at constant line count ("
                   page "-byte pages)")
      :runtime :jvm})))
