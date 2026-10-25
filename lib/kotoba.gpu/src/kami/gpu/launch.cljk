(ns kami.gpu.launch
  "Launch geometry: how a dispatch is shaped for the device it will run on.

  `kami.gpu` answers *can this backend run this pass* — compute shaders,
  storage buffers, instancing. That is a capability question and it is
  separate from this one, which is *given that it can, what shape should the
  dispatch be*. A pass that a backend can run at 8% of its bandwidth is still
  a pass the backend can run, and the tier table cannot tell you which one you
  have.

  Three things it computes, none of them from a constant:

  **Workgroup size**, from the device's own limits, reporting which constraint
  bound it. `256` is the number everyone writes down; it is right on some
  devices, wastes half the machine on others, and is illegal on a device whose
  maximum is 128. The plan says *why* it chose what it chose — subgroup floor,
  device maximum, shared-memory budget, or the problem simply being smaller
  than a workgroup — because that is the part a reader needs when the number
  looks wrong.

  **Coalescing**, as a computed utilization rather than a yes/no. A stride-2
  access is not \"uncoalesced\", it is 50% of the transaction wasted, and
  seeing 0.5 next to 0.03 is what tells you which access to fix first.

  **Workgroup swizzle** — visiting the tiles of a 2-D dispatch along a
  space-filling curve rather than row by row, so workgroups resident at the
  same time touch nearby memory and share L2. This is the same question
  `traversal` answers for a CPU cache, so it is the same code: no second
  Morton implementation living in a GPU file.

  Pure `.cljc`. No device is opened here; a host builds the descriptor."
  (:require [machine.core :as m]
            [traversal.core :as t]))

(def format-id :kami.gpu.launch/v1)

(defn- pow2-floor [n]
  (loop [p 1] (if (> (* 2 p) n) p (recur (* 2 p)))))

(defn workgroup-size
  "The largest legal workgroup for this device and this kernel.

  `:shared-bytes-per-invocation` is what one invocation needs in workgroup /
  threadgroup / `__shared__` memory — a reduction needs one accumulator each,
  a tiled matmul needs two tile elements. Zero for a kernel that uses none.

  Returns the size and the constraint that bound it, because a workgroup of
  32 on a device whose maximum is 1024 is either correct or a bug, and only
  the binding constraint distinguishes them."
  [machine {:keys [shared-bytes-per-invocation problem-size]
            :or {shared-bytes-per-invocation 0}}]
  (let [gpu (or (m/gpu machine)
                (throw (ex-info "machine declares no GPU"
                                {:phase :gpu.launch/workgroup
                                 :machine/id (:machine/id machine)})))
        {:keys [max-workgroup subgroup shared-bytes]} gpu
        ;; Only a constraint that was actually supplied may be named as the
        ;; binding one. Folding an absent shared-memory budget in as
        ;; `max-workgroup` and then reporting `:shared-memory` on the tie
        ;; would be a plan explaining itself with a reason that never applied.
        candidates (cond-> [[:device-maximum max-workgroup]]
                     (pos? shared-bytes-per-invocation)
                     (conj [:shared-memory
                            (pow2-floor (max 1 (quot shared-bytes shared-bytes-per-invocation)))])
                     problem-size
                     (conj [:problem-size (pow2-floor (max 1 problem-size))]))
        [bound raw] (first (sort-by second candidates))
        ;; A workgroup narrower than a subgroup wastes the lanes it cannot
        ;; fill, so the floor wins — and then whatever wanted it smaller is
        ;; the thing that has to give, which the report names.
        size (max raw subgroup)
        bound (if (< raw subgroup)
                (keyword (str "subgroup-floor-over-" (name bound)))
                bound)]
    {:size size
     :bound-by bound
     :subgroups (quot size subgroup)
     :shared-bytes-used (* size shared-bytes-per-invocation)
     :shared-bytes-available shared-bytes
     :over-shared-budget? (> (* size shared-bytes-per-invocation) shared-bytes)
     :device-maximum max-workgroup}))

(defn coalescing
  "How much of each memory transaction this access pattern actually uses.

  Reported as a fraction rather than a verdict: `1.0` is fully coalesced,
  `0.5` is a stride-2 access throwing away half of every transaction, and
  `0.03` is a column walk of a 32-wide row. Which of those to fix first is
  obvious from the numbers and invisible from a boolean.

  **Measured on an Apple M1 Max, this is pessimistic past about stride 2.**
  A kernel reading the same addresses in every arm -- identical footprint,
  identical load count, only the thread-to-address mapping permuted -- gave,
  relative to stride 1:

      stride     2      4      8     16     32
      model   0.50   0.25   0.13   0.06   0.03
      measured 0.57   0.65   0.39   0.19   0.13

  The direction holds and the magnitude does not: at stride 32 the model
  predicts 3% of peak and the hardware delivered 13%, so it over-states the
  penalty about fourfold. Something between the coalescer and the cache
  recovers part of what the model writes off.

  The formula is unchanged, because that measurement carries roughly 20%
  run-to-run spread and one noisy sweep is not a calibration -- and because
  the error is in the safe direction for a planner deciding whether to fix a
  strided access. Use it to rank access patterns, which is what it is for; do
  not use it to predict a speedup."
  [{:keys [stride element-bytes] :or {stride 1 element-bytes 4}}]
  (when-not (and (pos-int? stride) (pos-int? element-bytes))
    (throw (ex-info "coalescing needs a positive stride and element size"
                    {:phase :gpu.launch/coalescing :stride stride
                     :element-bytes element-bytes})))
  {:stride stride
   :element-bytes element-bytes
   :coalesced? (= 1 stride)
   :utilization (/ 1.0 stride)
   :bytes-fetched-per-useful-byte (double stride)})

(defn swizzled-tiles
  "The tile coordinates of a 2-D dispatch, in the order workgroups should be
  scheduled.

  `:row-major` is what a driver does by default. `:morton` and `:hilbert`
  visit tiles so that workgroups running at the same time are near each other
  in both dimensions, which is the reason a fast GEMM swizzles its
  threadblock index.

  A curve only covers a square power-of-two grid, so a ragged one is walked
  over the enclosing square and the out-of-range coordinates dropped. That is
  why this returns a *sequence* rather than an index formula: the host must
  use the sequence, because the dropped ids mean position N is not tile N."
  [[grid-w grid-h] order]
  (case order
    (:row-major :column-major)
    (t/visit-sequence order [grid-w grid-h])

    (:morton :hilbert)
    (let [side (loop [s 1] (if (>= s (max grid-w grid-h)) s (recur (* 2 s))))]
      (filterv (fn [[x y]] (and (< x grid-w) (< y grid-h)))
               (t/visit-sequence order [side side])))))

(defn swizzle-locality
  "What the swizzle bought, measured rather than asserted.

  `:same-block` is the fraction of side-by-side tiles that land in the same
  window of `block` consecutively-scheduled workgroups — i.e. how often two
  neighbouring tiles are actually resident together. Row-major separates
  vertically adjacent tiles by a whole grid row; the curves do not."
  [[grid-w grid-h] order block]
  (t/neighbour-locality order [grid-w grid-h] block))

(defn reduction-passes
  "How many dispatches a tree reduction over `n` elements needs.

  One pass per `log_workgroup(n)` level: each pass turns `workgroup` values
  into one partial. The last pass produces a single value, and the partials
  buffer must be sized for the *first* pass, not the last — sizing it for the
  final one is a buffer overrun that looks like a correctness bug."
  [n workgroup]
  (loop [remaining n passes 0 first-partials nil]
    (if (<= remaining 1)
      {:passes passes
       :partials-buffer-elements (or first-partials 1)
       :final-elements 1}
      (let [next (quot (+ remaining (dec workgroup)) workgroup)]
        (recur next (inc passes) (or first-partials next))))))

(defn plan
  "A complete launch: workgroup, grid, coalescing verdict and swizzle.

  `:tiles` is emitted only when a 2-D `:grid` AND a `:tile` edge are given: a
  1-D dispatch has no neighbourhood to preserve, and without a tile size there
  is no grid of tiles to order."
  [machine {:keys [problem-size grid tile access shared-bytes-per-invocation
                   swizzle reduction?]
            :or {swizzle :morton shared-bytes-per-invocation 0}}]
  (let [wg (workgroup-size machine {:shared-bytes-per-invocation shared-bytes-per-invocation
                                    :problem-size problem-size})
        n (or problem-size (when grid (apply * grid)) 1)
        workgroups (quot (+ n (dec (:size wg))) (:size wg))]
    (cond-> {:format format-id
             :machine (:machine/id machine)
             :gpu (m/gpu machine)
             :workgroup wg
             :problem-size n
             :workgroups workgroups
             :coalescing (coalescing (or access {}))}
      reduction?
      (assoc :reduction (reduction-passes n (:size wg)))

      (and grid (= 2 (count grid)) (pos-int? tile))
      (as-> p
            (let [gw (max 1 (quot (+ (first grid) (dec tile)) tile))
                  gh (max 1 (quot (+ (second grid) (dec tile)) tile))]
              (assoc p
                     :tile tile
                     :tile-grid [gw gh]
                     :swizzle swizzle
                     :tiles (swizzled-tiles [gw gh] swizzle)
                     ;; Both, so the swizzle is justified by a measurement in
                     ;; the plan rather than by a citation in a comment.
                     :swizzle-locality {:chosen (swizzle-locality [gw gh] swizzle 8)
                                        :row-major (swizzle-locality [gw gh] :row-major 8)}))))))
