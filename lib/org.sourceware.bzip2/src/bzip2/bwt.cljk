(ns bzip2.bwt
  "The Burrows-Wheeler transform, both directions.

   This is what makes bzip2 different from every other codec in this workspace:
   there is no match finder and no sliding window. A block is sorted by its
   rotations, which brings equal contexts together, and the *last column* of
   that sorted matrix is what gets entropy-coded. The transform is reversible
   from the last column plus the row index of the original string (`orig-ptr`)
   alone.

   `inverse` is O(n) and is the path that matters for reading real archives.
   `forward` sorts rotations by prefix doubling — O(n log n) comparisons over
   O(log n) rounds — which is not bzip2's own algorithm (a tuned radix/quicksort
   hybrid with a fallback sorter) but produces the identical permutation. It is
   correspondingly slower on large blocks; see the README.

   Rotations, not suffixes. For a block whose end repeats its beginning the two
   orders differ, and only the rotation order round-trips."
  (:refer-clojure :exclude [update]))

;; ---------------------------------------------------------------------------
;; Inverse — bzip2's own formulation
;; ---------------------------------------------------------------------------

(defn inverse
  "Undo the transform: `last-column` (a vector of unsigned bytes) plus
   `orig-ptr` → the original block.

   A counting sort gives the first column implicitly, and `T[i]` is then the
   position in the last column of the byte *preceding* `last-column[i]`.
   Walking that chain from `orig-ptr` emits the block in order."
  [last-column orig-ptr]
  (let [n (count last-column)]
    (when (or (neg? orig-ptr) (>= orig-ptr (max n 1)))
      (throw (ex-info "bzip2: BWT pointer outside the block"
                      {:reason :bad-orig-ptr :orig-ptr orig-ptr :block-size n})))
    (if (zero? n)
      []
      (let [counts (reduce (fn [c b] (assoc c b (inc (nth c b))))
                           (vec (repeat 256 0))
                           last-column)
            ;; cftab[b] = how many bytes of the block sort before b
            cftab (loop [b 0 acc 0 out (transient [])]
                    (if (= b 256)
                      (persistent! out)
                      (recur (inc b) (+ acc (nth counts b)) (conj! out acc))))
            tt (loop [i 0
                      t (transient (vec (repeat n 0)))
                      cf cftab]
                 (if (= i n)
                   (persistent! t)
                   (let [b (nth last-column i)
                         p (nth cf b)]
                     (recur (inc i) (assoc! t p i) (assoc cf b (inc p))))))]
        (loop [k 0 p (nth tt orig-ptr) out (transient [])]
          (if (= k n)
            (persistent! out)
            (recur (inc k) (nth tt p) (conj! out (nth last-column p)))))))))

;; ---------------------------------------------------------------------------
;; Forward — prefix doubling
;; ---------------------------------------------------------------------------

(defn- rotation-order
  "Sort every rotation of `block` by prefix doubling → a vector of starting
   offsets in sorted order.

   Ranks are combined into a single number (`r1 * n + r2`) rather than a pair,
   because comparing numbers instead of vectors is what keeps this usable at
   900,000 bytes. That packing is only valid while every rank is below `n`, so
   the *initial* ranks are the positions of the byte values in sorted order —
   not the byte values themselves. Seeding with raw bytes silently mis-sorts any
   block shorter than 256 bytes whose values are spread out, and a mis-sorted
   rotation order produces a block that fails its own CRC on the way back."
  [block n]
  (loop [ranks (let [order (vec (sort (distinct block)))
                     idx (zipmap order (range))]
                 (mapv idx block))
         k 1]
    (let [ks (mapv (fn [i] (+ (* n (nth ranks i)) (nth ranks (rem (+ i k) n))))
                   (range n))
          order (vec (sort-by #(nth ks %) (range n)))
          [ranks' distinct?]
          (loop [j 0 prev -1 r -1
                 out (transient (vec (repeat n 0)))
                 all-distinct true]
            (if (= j n)
              [(persistent! out) all-distinct]
              (let [i (nth order j)
                    kk (nth ks i)
                    same? (= kk prev)
                    r (if same? r (inc r))]
                (recur (inc j) kk r (assoc! out i r) (and all-distinct (not same?))))))]
      (if (or distinct? (>= k n))
        order
        (recur ranks' (* 2 k))))))

(defn forward
  "Apply the transform to `block` (a vector of unsigned bytes) →
   `{:last-column [...] :orig-ptr i}`."
  [block]
  (let [n (count block)]
    (if (zero? n)
      {:last-column [] :orig-ptr 0}
      (let [order (rotation-order block n)
            last-col (mapv #(nth block (rem (+ % (dec n)) n)) order)
            orig (loop [i 0]
                   (cond
                     (= i n) (throw (ex-info "bzip2: rotation 0 missing from the sort"
                                             {:reason :internal}))
                     (zero? (nth order i)) i
                     :else (recur (inc i))))]
        {:last-column last-col :orig-ptr orig}))))
