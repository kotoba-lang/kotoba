(ns layout.core
  "Where the bytes of an aggregate go, planned against a real machine.

  The canonical example: a particle with `x y z mass`. Held as an array of
  structs, a pass that reads only `x` still pulls `y z mass` into every cache
  line it touches. Held as a struct of arrays, `x` is contiguous and the line
  is all payload. Neither is universally right — a pass that touches *every*
  field of one element wants the struct back — so this namespace does not
  pick a winner in the abstract. It computes what each layout costs for a
  stated access pattern on a stated machine, and reports the model it used.

  Two things here are not decoration.

  **The cost model is a value.** `cost` returns `:cost/model` alongside the
  numbers, and `recommend` returns the losers as well as the winner. A layout
  choice whose justification cannot be printed is how a team ends up with an
  optimization nobody can re-derive and nobody dares delete.

  **Reordering fields breaks the ABI.** Sorting fields by descending
  alignment is the standard way to squeeze padding out of a struct, and it
  changes the byte offsets that `kotoba-wasm`'s Canonical ABI fixes by
  declaration order. So every plan carries `:layout/abi-canonical?` and
  `:layout/scope`, and `abi-guard!` throws rather than letting an
  internal-only layout leak across a component boundary. Silently shipping a
  reordered struct through a Canonical ABI lift is a wire-format bug that
  presents as data corruption.

  Pure `.cljc`. Depends only on `kotoba-lang/machine`."
  (:require [machine.core :as m]))

(def format-id :kotoba.layout/v1)

(def kinds
  "`:aos` array-of-structs, `:soa` struct-of-arrays, `:aosoa` blocked hybrid."
  #{:aos :soa :aosoa})

;; ── field checking ───────────────────────────────────────────────────────

(defn- pow2? [n] (and (integer? n) (pos? n) (zero? (bit-and n (dec n)))))

(defn field-errors
  "Every reason `fields` is not a usable field list."
  [fields]
  (vec
   (concat
    (when-not (and (vector? fields) (seq fields))
      [{:error :empty-field-list :fields fields}])
    (when (and (vector? fields) (seq fields))
      (concat
       (for [[i f] (map-indexed vector fields)
             e (cond-> []
                 (not (keyword? (:name f)))  (conj :invalid-field-name)
                 (not (pos-int? (:bytes f))) (conj :invalid-field-bytes)
                 (not (pow2? (:align f)))    (conj :invalid-field-align))]
         {:error e :index i :field f})
       (let [names (map :name fields)]
         (when-not (= (count names) (count (set names)))
           [{:error :duplicate-field-name :names (vec names)}])))))))

(defn- check-fields! [fields]
  (let [errs (field-errors fields)]
    (when (seq errs)
      (throw (ex-info "invalid field list" {:phase :layout/fields :errors errs})))
    fields))

(defn- align-up [v a] (* a (quot (+ v (dec a)) a)))

(defn- line!
  "The line width, or a throw naming what was missing. Planners must ask out
  loud rather than defaulting to 64 — see `machine.core/require-fact`."
  [machine]
  (m/require-fact machine [:cpu :cache] "a cache hierarchy (needed for line width)")
  (or (m/line-bytes machine)
      (throw (ex-info "machine declares caches but no line width"
                      {:phase :layout/line :machine/id (:machine/id machine)}))))

;; ── the three layouts ────────────────────────────────────────────────────

(defn- pack
  "Lay `fields` out consecutively with natural alignment."
  [fields]
  (let [{:keys [placed end]}
        (reduce (fn [acc f]
                  (let [off (align-up (:end acc) (:align f))]
                    {:placed (conj (:placed acc) (assoc f :offset off))
                     :end (+ off (:bytes f))}))
                {:placed [] :end 0}
                fields)
        agg-align (apply max (map :align fields))
        payload (reduce + (map :bytes fields))
        size (align-up end agg-align)]
    {:fields placed :align agg-align :size size
     :payload-bytes payload :padding-bytes (- size payload)}))

(defn- by-descending-alignment
  "Stable: ties keep declaration order, so the packing is deterministic."
  [fields]
  (->> (map-indexed (fn [i f] [i f]) fields)
       (sort-by (fn [[i f]] [(- (:align f)) i]))
       (mapv second)))

(defn aos
  "Array of structs.

  `:reorder? true` sorts fields by descending alignment before packing — the
  standard padding squeeze — which makes the plan NOT ABI-canonical.

  `:pad-to-line? true` rounds the struct up to a full cache line. That is the
  false-sharing fix when distinct threads write distinct elements, and it is
  a memory-footprint tax the plan reports rather than hides."
  ([machine fields] (aos machine fields {}))
  ([machine fields {:keys [reorder? pad-to-line?] :or {reorder? false pad-to-line? false}}]
   (check-fields! fields)
   (let [packed (pack (if reorder? (by-descending-alignment fields) fields))
         line (when pad-to-line? (line! machine))
         size (if pad-to-line? (align-up (:size packed) line) (:size packed))
         canonical? (and (not reorder?) (not pad-to-line?))]
     {:format format-id
      :layout/kind :aos
      :layout/fields (:fields packed)
      :layout/align (if pad-to-line? (max (:align packed) line) (:align packed))
      :layout/element-bytes size
      :layout/write-stride-bytes size
      :layout/payload-bytes (:payload-bytes packed)
      :layout/padding-bytes (- size (:payload-bytes packed))
      :layout/abi-canonical? canonical?
      :layout/scope (if canonical? :abi-boundary :internal-only)
      :layout/machine (:machine/id machine)})))

(defn soa
  "Struct of arrays: one array per field, each array base aligned to a line so
  a scan of one field never straddles into another's."
  [machine fields]
  (check-fields! fields)
  (let [line (line! machine)
        payload (reduce + (map :bytes fields))]
    {:format format-id
     :layout/kind :soa
     :layout/fields (mapv #(assoc % :array-align line) fields)
     :layout/align line
     :layout/element-bytes payload
     ;; Two threads writing the same field of adjacent elements are
     ;; `bytes` apart, not `element-bytes` apart. That distance, not the
     ;; struct size, is what decides false sharing here.
     :layout/write-stride-bytes (apply min (map :bytes fields))
     :layout/payload-bytes payload
     :layout/padding-bytes 0
     ;; A struct-of-arrays has no struct, so there is nothing for a Canonical
     ;; ABI record lift to point at. Internal by construction, not by choice.
     :layout/abi-canonical? false
     :layout/scope :internal-only
     :layout/machine (:machine/id machine)}))

(defn default-block
  "Block width for `aosoa`.

  Chosen so each field's sub-array is a whole number of cache lines:
  `line / narrowest-field`. That holds exactly when field widths are
  multiples of the narrowest, which is the normal case (1/2/4/8). Floored at
  the SIMD lane count for the widest field, so one block always holds at
  least one full vector operation's worth."
  [machine fields]
  (let [line (m/line-bytes machine)
        narrowest (apply min (map :bytes fields))
        widest (apply max (map :bytes fields))
        lanes (m/simd-lanes machine widest)]
    (max 1
         (or lanes 1)
         (if line (quot line narrowest) 1))))

(defn aosoa
  "Blocked hybrid: `block` elements' worth of each field, contiguous, then the
  next field. Keeps a field's values adjacent inside a block (so a lane-wide
  load is one line) while keeping a whole element inside one block (so a
  full-element pass stays local)."
  ([machine fields] (aosoa machine fields nil))
  ([machine fields block]
   (check-fields! fields)
   (let [block (or block (default-block machine fields))
         _ (when-not (pos-int? block)
             (throw (ex-info "aosoa block must be a positive integer"
                             {:phase :layout/aosoa :block block})))
         line (line! machine)
         subs (reduce (fn [acc f]
                        (let [off (align-up (:end acc) (:align f))]
                          {:placed (conj (:placed acc)
                                         (assoc f :block-offset off
                                                  :block-bytes (* block (:bytes f))))
                           :end (+ off (* block (:bytes f)))}))
                      {:placed [] :end 0}
                      fields)
         block-bytes (align-up (:end subs) line)
         payload (reduce + (map :bytes fields))]
     {:format format-id
      :layout/kind :aosoa
      :layout/block block
      :layout/fields (:placed subs)
      :layout/align line
      :layout/block-bytes block-bytes
      ;; Amortized, and a double on purpose: block padding rarely divides
      ;; evenly by the block width, and rounding it to an integer would
      ;; understate the footprint of a small block.
      :layout/element-bytes (double (/ block-bytes block))
      :layout/write-stride-bytes (apply min (map :bytes fields))
      :layout/payload-bytes payload
      :layout/padding-bytes (- (double (/ block-bytes block)) payload)
      :layout/abi-canonical? false
      :layout/scope :internal-only
      :layout/machine (:machine/id machine)})))

;; ── cost ─────────────────────────────────────────────────────────────────

(defn lines-for-strided-run
  "Cache lines pulled by touching every `step`-th of `n` items of `width`
  bytes laid consecutively.

  Two regimes, and the boundary between them is the whole point of a stride:

  - `step * width >= line` — touched items land on distinct lines, so each
    costs its own `ceil(width/line)`. This is where a stride gets expensive:
    you pay for the bytes you skipped.
  - otherwise — consecutive touched items share lines, so the run costs the
    whole span. Skipping is free here, because the line came in anyway."
  [n width step line]
  (let [n (max 0 n)
        ceil-div (fn [a b] (quot (+ a (dec b)) b))]
    (cond
      (zero? n) 0
      (>= (* step width) line) (* (ceil-div n step) (ceil-div width line))
      :else (ceil-div (* n width) line))))

(def cost-model
  "The model `cost` applies, as data, so a layout decision can print its own
  justification. Deliberately coarse: it counts compulsory line fills for one
  linear pass and nothing else. Stating what it does NOT model is the part
  that keeps it honest."
  {:model/id :kotoba.layout.cost/compulsory-lines-v1
   :model/bounds :layout-only
   :model/counts [:cache-lines-filled :bytes-fetched :bytes-useful :sequential-streams]
   :model/assumes
   ["one linear pass over `count` elements, cold cache"
    "a line fetched once is not refetched (no capacity or conflict misses)"
    "no hardware-prefetch credit, so a sequential AoS pass is charged pessimistically"
    "no TLB, no NUMA, no DRAM row-buffer effects"]
   :model/does-not-model
   [:capacity-misses :conflict-misses :prefetch :write-allocate :store-buffers :tlb :numa]
   ;; Measured, not asserted. The line ratio is an UPPER BOUND on the wall-clock
   ;; ratio, and on a machine with a deep prefetcher and bandwidth to spare the
   ;; realized fraction is small. Recorded here with the machine it was taken
   ;; on, because a calibration without one is the fossil this stack exists to
   ;; prevent.
   :model/calibration
   [{:machine "Apple M1 Max/performance (128 B line, 16 KiB page, 12 MiB L2 shared by 4)"
     :date "2026-08-03"
     :workload "sequential sum of one f64 field, 2e6 elements, 16 doubles per AoS element"
     :predicted-line-ratio 16.0
     :measured-wall-ratio 2.02
     :realized-fraction 0.126
     :note "The model does not model prefetch, and this is what that costs. A
            sequential scan lets the hardware prefetcher hide the latency, so
            only the bandwidth difference survives -- and on 400 GB/s there is
            enough of it that 244 MiB versus 16 MiB is a 2x wall-clock gap, not
            a 16x one. Treat :cost/lines as a ceiling on the achievable
            speedup, not an estimate of it."}
    {:machine "Apple M1 Max/performance"
     :date "2026-08-03"
     :workload "same 16-wide element, loop rewritten with four independent accumulators"
     :measured-wall-ratio 6.63
     :note "The serial loop ran at floating-point add LATENCY, because every
            add waited on the previous one -- 2.87 ns/element for one load and
            one add, about ten cycles. Four independent accumulators took it to
            0.87 ns and moved the measured AoS/SoA ratio from 2.12x to 6.63x.
            The layout was never the thing being measured; the dependency
            chain was. At n=8e6 the same change reached 20.2x, ABOVE the byte
            model's 16x, because a 1 GiB array runs out of TLB reach -- an
            effect this model also declines to model, in the other direction."}
    {:machine "Apple M1 Max/performance"
     :date "2026-08-03"
     :correction true
     :note "The 2.02x and 6.63x agreements between `achievable-ratio` and
            measurement, reported earlier the same day, are NOT validations.
            Both inputs were derived from the two arms being explained, so the
            formula returns their ratio by construction wherever neither term
            clamps. See the held-out test below for the one that counts."}
    {:machine "Apple M1 Max/performance"
     :date "2026-08-03"
     :bug-found true
     :note "`cost` charged ceil(element-bytes / line) lines per AoS element
            unconditionally -- \"AoS pulls the whole struct\". That holds while
            the struct fits a line or two, because the line holding one field
            also holds the neighbours the pass is about to touch. It is simply
            false past that: reading one f64 out of a 4 KiB element pulls ONE
            line, not thirty-two. The model over-counted a 4 KiB element by 32x
            and reported a 512x AoS/SoA ratio where 16x is the truth. Every
            fixture used elements of a line or less, so it never showed.
            Fixed: wide elements are charged the lines their touched fields
            actually sit on, and the narrow case keeps the span formula
            unchanged. Reading ALL fields of a wide element still gives
            ceil(element/line), so the fix degrades correctly."}
    {:machine "Apple M1 Max/performance"
     :date "2026-08-03"
     :per-arm-bandwidth-test true
     :configuration "2e6 elements of 128 doubles (1 KiB), reading one field.
                     1953 MiB as AoS against 15 MiB as SoA, JVM, curve measured
                     on the same run."
     :one-constant "predicted ratio 16.00x — 10% from measured"
     :per-arm "predicted ratio 18.22x — 4% from measured"
     :measured-ratio "17.56x"
     :verdict "Per-arm lookup halves the ratio error. Real, and in the claimed
               direction."
     :how-weak-this-test-is
     "Three things a reader should know before treating this as strong.
      (1) The arms' bandwidths differed by only 1.14x here (6.3 against 7.2
          GB/s) because the JVM curve is compressed at short strides — the
          change was designed for the 2.5x gaps the C curve shows, and this
          did not exercise that.
      (2) The absolute times are 15-20% out under BOTH schemes; per-arm is
          better on the ratio and slightly WORSE on the AoS arm alone (40.7 ms
          predicted against 33.9 measured, where one constant gave 35.8).
          `achievable-ratio` is named for the ratio and that is what improved.
      (3) One configuration, one machine, one runtime."
     :constants "loop floor 0.771 ns/element measured on a 16 KiB L1-resident
                 array; bandwidth 30.1 GB/s measured on a line-strided scan of
                 a 45 MiB array. Different size, stride and element width from
                 the configuration predicted."
     :predicted "4e6 elements x 8 doubles, reading one field: AoS 8.501 ms,
                 SoA 3.084 ms, ratio 2.76x"
     :measured "AoS 6.848 ms, SoA 2.804 ms, ratio 2.44x"
     :error "AoS -19.4%, SoA -9.1%, ratio -11.4% (the model over-predicts both
             arms, so it errs toward pessimism)"
     :note "This one is a real test: the constants came from measurements the
            predicted configuration does not share, so the formula could have
            been wrong and was not. It failed first at 65%, and the fault was
            the calibration rather than the model — bandwidth had been measured
            with a contiguous f64 sum, whose 8-byte-per-iteration loop caps at
            10.4 GB/s and therefore reports the loop floor in different units.
            Measure bandwidth where the loop is NOT the bottleneck.
            Within 19% on held-out data, `achievable-ratio` is usable as a
            planning estimate and not merely as a ceiling."}
    {:machine "Apple M1 Max/performance"
     :date "2026-08-03"
     :workload "same, but 4 doubles per AoS element (32 B)"
     :predicted-line-ratio 4.0
     :measured-wall-ratio 1.01
     :realized-fraction 0.0025
     :note "At this element width the layout difference is not measurable at
            all: the loop cost per element is roughly fifty times the memory
            cost, so the memory system never becomes the bottleneck. perfgate
            refused the claim, which is the correct outcome and the reason to
            keep the refusal path."}]
   :model/known-consequences
   [;; Worth stating, because it is the result people expect to be false.
    "With NO struct padding and a pass that touches EVERY field, AoS and SoA
     fetch exactly the same bytes — this model cannot separate them. The
     separation appears only when the pass touches a subset, or when the
     struct carries padding SoA does not pay."
    ;; And the reason a line count alone must not decide the matter.
    "A line count says nothing about how many concurrent sequential streams a
     layout opens. Hardware prefetchers track a bounded number of them, so a
     SoA over many fields is not free even where the line count says it is —
     hence `:cost/streams`."]})

(defn cost
  "What one pass of `access` over `n` elements costs under `plan`.

  `access` is `{:access/fields #{…} :access/stride k}`; an empty or absent
  field set means the pass touches every field. `:cost/utilization` — useful
  bytes over fetched bytes — is the number that actually decides layouts."
  [machine plan n {:access/keys [fields stride] :or {stride 1}}]
  (let [line (line! machine)
        all (:layout/fields plan)
        touched (if (seq fields) (filterv #(contains? fields (:name %)) all) (vec all))
        ceil-div (fn [a b] (quot (+ a (dec b)) b))
        useful (* (ceil-div n stride) (reduce + 0 (map :bytes touched)))
        ;; Lines an AoS element actually contributes.
        ;;
        ;; "AoS pulls the whole struct" is true only while the struct fits in
        ;; a line or two -- then the line containing one field also contains
        ;; the neighbours the pass is about to touch anyway. Past that it is
        ;; simply false: reading one f64 out of a 4 KiB element pulls ONE
        ;; line, not thirty-two. The old formula charged ceil(element/line)
        ;; per element unconditionally and over-counted a 4 KiB element by
        ;; 32x, which never showed because every fixture used elements of a
        ;; line or less.
        aos-lines-per-element
        (fn [element-bytes]
          (when (> element-bytes line)
            (count (distinct (mapcat (fn [f]
                                       (let [o (:offset f 0) b (:bytes f)]
                                         (range (quot o line)
                                                (inc (quot (dec (+ o b)) line)))))
                                     touched)))))
        lines
        (case (:layout/kind plan)
          :aos   (let [e (:layout/element-bytes plan)]
                   (if-let [per (aos-lines-per-element e)]
                     ;; Wide element: only the lines the touched fields sit on.
                     (* (ceil-div n stride) per)
                     ;; Narrow element: consecutive elements share lines, so
                     ;; the span formula is right and stays.
                     (lines-for-strided-run n e stride line)))
          :soa   (reduce + 0 (map #(lines-for-strided-run n (:bytes %) stride line) touched))
          :aosoa (let [b (:layout/block plan)
                       blocks (ceil-div n b)
                       per-block (reduce + 0 (map #(lines-for-strided-run b (:bytes %) stride line)
                                                  touched))]
                   (* blocks per-block)))]
    {:cost/lines lines
     :cost/bytes-fetched (* lines line)
     :cost/bytes-useful useful
     :cost/utilization (if (pos? lines) (double (/ useful (* lines line))) 0.0)
     ;; Concurrent sequential streams the pass opens. One for AoS and AoSoA
     ;; (the walk stays inside one region); one per touched field for SoA.
     ;; A prefetcher tracks a bounded number, so this is where a wide SoA
     ;; stops being free even when `:cost/lines` says it is.
     :cost/streams (case (:layout/kind plan)
                     :soa (count touched)
                     1)
     :cost/model cost-model
     :cost/machine (:machine/id machine)}))

(defn recommend
  "Cost every candidate layout for this access pattern and return them ranked,
  cheapest first — with the losers attached.

  Returning the alternatives is the point. A bare answer (\"use SoA\") is
  unfalsifiable six months later; a ranked list with a printed model can be
  re-derived, argued with, and invalidated when the access pattern changes."
  [machine fields n access]
  (check-fields! fields)
  (let [candidates [[:aos (aos machine fields)]
                    [:aos-reordered (aos machine fields {:reorder? true})]
                    [:soa (soa machine fields)]
                    [:aosoa (aosoa machine fields)]]
        scored (mapv (fn [[id plan]]
                       {:candidate id :plan plan :cost (cost machine plan n access)})
                     candidates)
        ;; Fewest lines first; then fewest prefetch streams, because a tie on
        ;; bytes is broken by the thing this model cannot price; then least
        ;; padding; then the name, so the ranking is total and deterministic.
        ranked (vec (sort-by (juxt (comp :cost/lines :cost)
                                   (comp :cost/streams :cost)
                                   (comp double :layout/padding-bytes :plan)
                                   (comp name :candidate))
                             scored))]
    {:format format-id
     :recommend/access access
     :recommend/count n
     :recommend/chosen (first ranked)
     :recommend/ranked ranked
     :recommend/model cost-model}))

;; ── false sharing ────────────────────────────────────────────────────────

(defn false-sharing-risk
  "Do distinct threads writing distinct elements collide on a line?

  The distance that matters is `:layout/write-stride-bytes` — how far apart
  two threads' writes land — which is the struct size for AoS but the field
  width for SoA and AoSoA. Risk exists only when that distance is under a
  line, which is the common case, and why the symptom (a parallel loop that
  gets *slower* with more threads) is so often misread as lock contention."
  [machine plan {:keys [concurrent-writers] :or {concurrent-writers 1}}]
  (let [line (m/line-bytes machine)
        w (:layout/write-stride-bytes plan)]
    (cond
      (nil? line) {:risk :unknown :reason :machine-declares-no-line-width}
      (<= concurrent-writers 1) {:risk :none :reason :single-writer}
      (>= w line) {:risk :none :reason :write-stride-spans-a-line
                   :write-stride-bytes w :line-bytes line}
      :else {:risk :present
             :reason :multiple-writes-share-a-line
             :writes-per-line (quot line w)
             :write-stride-bytes w :line-bytes line
             :fix :pad-to-line
             :footprint-multiplier (double (/ line w))})))

;; ── ABI boundary ─────────────────────────────────────────────────────────

(defn abi-canonical?
  "May this plan describe bytes that cross a Canonical ABI boundary?

  Only a declaration-ordered, unpadded AoS may. Anything else has moved or
  spread the fields, and a Canonical ABI lift reading it as a record would
  read the wrong offsets."
  [plan]
  (boolean (:layout/abi-canonical? plan)))

(defn abi-guard!
  "Throw unless `plan` may cross a component boundary.

  Call this at the lift/lower site, not at the plan site. An internal layout
  is a legitimate thing to have — it just may not be the thing one component
  hands to another."
  [plan where]
  (when-not (abi-canonical? plan)
    (throw (ex-info "non-canonical layout at an ABI boundary"
                    {:phase :layout/abi-guard
                     :where where
                     :layout/kind (:layout/kind plan)
                     :layout/scope (:layout/scope plan)
                     :remedy "use (aos machine fields) — declaration order, no line padding"})))
  plan)

;; ── from bytes to time ───────────────────────────────────────────────────

(def roofline-model
  {:model/id :kotoba.layout.roofline/v1
   :model/rule "per-arm time = max(loop-ns-per-element * n, bytes-fetched / bandwidth)"
   ;; Which lever this bounds, stated rather than left to be inferred. A bound
   ;; constrains one lever, and comparing it against a measurement that moved a
   ;; different one is not conservative, it is meaningless -- `paging` reports
   ;; :bounds :replacement-only and `ioplan` :bounds :merging-and-ordering for
   ;; the same reason, each after a planner appeared to beat its own floor.
   :model/bounds :layout-only
   :model/assumes
   ["a loop has a floor cost per element that no layout can remove"
    "a machine delivers a finite bandwidth to the thread doing the fetching"
    "the two overlap perfectly, so the slower one is the whole cost"]
   ;; Inherited, and worth restating: `bytes-fetched` comes from `cost`, which
   ;; counts COMPULSORY lines. So this ratio cannot see a change that works by
   ;; altering reuse rather than layout. Blocking is the obvious one -- measured
   ;; clock-free on a matmul page trace, tiling moved miss counts by up to 23x,
   ;; none of which is visible here. Feeding this a tiled-vs-untiled comparison
   ;; asks a layout bound about a capacity lever.
   :model/does-not-model [:latency-bound-random-access :nuca :contention-between-threads
                          :capacity-misses :reuse-from-blocking]})

(defn touch-stride-bytes
  "Distance in bytes between the items a pass consecutively touches.

  **The two arms of a layout comparison do not share this.** Reading one field
  of a 128-byte AoS element walks 128 bytes at a time; the same field in a SoA
  walks 8. That is a different point on the machine's bandwidth curve — three
  times apart on the part this was calibrated against — and handing both arms
  one bandwidth figure is the error that made two models wrong in one
  afternoon."
  [plan access]
  (let [stride (get access :access/stride 1)
        fields (get access :access/fields)
        touched (if (seq fields)
                  (filterv #(contains? fields (:name %)) (:layout/fields plan))
                  (:layout/fields plan))]
    (* stride
       (case (:layout/kind plan)
         ;; A whole element is skipped per step whatever the pass reads.
         :aos (:layout/element-bytes plan)
         ;; Each field array is walked independently at its own width; the
         ;; narrowest is the one whose stride is hardest on the prefetcher.
         :soa (apply min (map :bytes touched))
         ;; Within a block a field is contiguous, so the field width governs.
         :aosoa (apply min (map :bytes touched))))))

(defn achievable-ratio
  "The speedup a layout change can actually deliver, in time rather than bytes.

  `cost` counts bytes, and a bytes ratio is only realized as a time ratio when
  BOTH arms are memory-bound. The moment one arm's per-element loop cost
  exceeds its memory cost, that arm stops getting faster and the ratio is
  capped — which is why a 16x line ratio measured 2.0x on the machine this was
  written against, and why the surprise was in the question, not the answer.

  `loop-ns-per-element` is the floor: the time the pass takes when its data is
  already in registers. Measure it as the fastest arm's time divided by n.
  `bandwidth-bytes-per-ns` is what one thread actually observes, not the
  datasheet peak — those differ by more than an order of magnitude.

  **`bandwidth-bytes-per-ns` must match the stride being modelled.** It is a
  property of the machine AND the access pattern, never of the machine alone.
  Measured on the machine this was calibrated against, one f64 touched every
  S bytes over a 256 MiB working set:

      stride    128 B   256 B   512 B   1 KiB   4 KiB   16 KiB   64 KiB
      GB/s       24.1    29.7    27.6    34.3    14.5     11.5     14.2

  A 3x spread, with the floor at the 16 KiB page size where the TLB gives out.
  Handing the 34 GB/s figure to a plan about a page-strided walk is the same
  error that made `traversal/tiling-benefit` v1 predict 1.00x where measurement
  gave 2.69x.

  **Do not derive both inputs from the run you are explaining.** Taking
  `loop-ns-per-element` from the candidate arm and `bandwidth-bytes-per-ns`
  from the baseline arm makes this reproduce those two timings by
  construction — an identity dressed as a prediction, and it was reported as
  a successful validation here on 2026-08-03 before the circularity was
  noticed. To actually test the model, measure the loop floor on a working
  set that fits in L1 (where memory is free) and the bandwidth on a streaming
  read, then predict an unseen configuration.

  Both are measurements, so this returns a ceiling you can check against a
  `perfgate` claim rather than a number to quote."
  [machine {:keys [baseline candidate n access loop-ns-per-element bandwidth-bytes-per-ns]}]
  (let [arm (fn [plan]
              (let [c (cost machine plan n access)
                    stride-bytes (touch-stride-bytes plan access)
                    ;; An explicit figure still wins -- a caller who measured
                    ;; this exact pass knows better than a curve. Without one,
                    ;; the machine's curve is read AT THIS ARM'S STRIDE rather
                    ;; than shared with the other arm.
                    bw (or bandwidth-bytes-per-ns
                           (m/bandwidth-at-stride machine stride-bytes)
                           (throw (ex-info "no bandwidth for this arm"
                                           {:phase :layout/achievable-ratio
                                            :machine/id (:machine/id machine)
                                            :stride-bytes stride-bytes
                                            :remedy "pass :bandwidth-bytes-per-ns, or give the machine a measured :bandwidth curve"})))
                    mem-ns (/ (double (:cost/bytes-fetched c)) bw)
                    loop-ns (* loop-ns-per-element (double n))]
                {:plan (:layout/kind plan)
                 :stride-bytes stride-bytes
                 :bandwidth-bytes-per-ns bw
                 :bytes-fetched (:cost/bytes-fetched c)
                 :memory-ns mem-ns
                 :loop-ns loop-ns
                 :time-ns (max mem-ns loop-ns)
                 :bound-by (if (> mem-ns loop-ns) :memory :loop)}))
        b (arm baseline)
        c (arm candidate)]
    {:format format-id
     :baseline b
     :candidate c
     :bytes-ratio (double (/ (:bytes-fetched b) (:bytes-fetched c)))
     :achievable-ratio (/ (:time-ns b) (:time-ns c))
     ;; The whole point in one field. When this is false the bytes ratio is
     ;; unreachable no matter how good the layout is, and a plan that promises
     ;; it is promising something the loop will not allow.
     :both-memory-bound? (= :memory (:bound-by b) (:bound-by c))
     :model roofline-model
     :machine (:machine/id machine)}))
