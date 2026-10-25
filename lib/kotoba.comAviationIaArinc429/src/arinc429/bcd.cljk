(ns arinc429.bcd
  "BCD — Binary-Coded Decimal — encoding of the 19-bit Data field.

  Layout (again: reconstructed from public tutorials, not the paid
  standard's own text — see the README): five decimal digits packed into
  19 bits as four 4-bit nibbles PLUS one 3-bit partial digit, least
  significant digit first (lowest field bits):

    field bits   0-3    4-7    8-11   12-15  16-18
    digit        D1     D2     D3     D4     D5
    range        0-9    0-9    0-9    0-9    0-7

  D5, the most significant digit, gets only 3 bits (4*4 + 3 = 19, filling
  the field exactly) and so can only be 0-7 — it structurally cannot
  represent 8 or 9. This asymmetry (why does the top digit get fewer bits
  than the others?) is exactly the kind of detail that is easy to
  'round off' when reimplementing from memory instead of the spec, so
  this namespace enforces the 0-7 limit on D5 as a distinct, specifically
  named error rather than silently accepting 8/9 and corrupting the field.

  Sign is NOT part of the BCD data field — ARINC 429 carries it in SSM
  (see `arinc429.ssm/bcd-table`), so this namespace only ever produces and
  consumes non-negative digit sequences.")

(def digit-widths [4 4 4 4 3])
(def digit-shifts (reductions + 0 (butlast digit-widths)))
(def digit-max [9 9 9 9 7])

(defn encode-digits
  "`[d1 d2 d3 d4 d5]`, least-significant digit first, `d1`..`d4` in 0-9
  and `d5` in 0-7 -> `[:ok data19]`.

  `[:error :arinc429/bcd-digit-count n]` if not exactly 5 digits given
  (pad with leading zero digits yourself — this namespace does not guess
  how many of the 5 slots you meant to use), or `[:error
  :arinc429/bcd-digit-out-of-range {:position i :digit d}]` naming which
  of the five digits is bad."
  [digits]
  (cond
    (not= 5 (count digits))
    [:error :arinc429/bcd-digit-count (count digits)]

    :else
    (if-let [bad (first (keep (fn [i]
                                 (let [d (nth digits i)]
                                   (when (or (neg? d) (> d (nth digit-max i)))
                                     {:position i :digit d})))
                               (range 5)))]
      [:error :arinc429/bcd-digit-out-of-range bad]
      [:ok (reduce (fn [acc i]
                     (bit-or acc (bit-shift-left (nth digits i) (nth digit-shifts i))))
                   0 (range 5))])))

(defn decode-digits
  "`data19` -> `[:ok [d1 d2 d3 d4 d5]]`, least-significant digit first."
  [data19]
  [:ok (mapv (fn [i]
               (bit-and (unsigned-bit-shift-right data19 (nth digit-shifts i))
                        (dec (bit-shift-left 1 (nth digit-widths i)))))
             (range 5))])

(defn encode-value
  "Non-negative integer `n` (0..79999) -> `[:ok data19]`, splitting `n`
  into its five decimal digits for you."
  [n]
  (if (or (neg? n) (> n 79999))
    [:error :arinc429/bcd-value-out-of-range n]
    (encode-digits [(mod n 10)
                    (mod (quot n 10) 10)
                    (mod (quot n 100) 10)
                    (mod (quot n 1000) 10)
                    (quot n 10000)])))

(defn decode-value
  "`data19` -> `[:ok n]`, the five digits recombined into one integer."
  [data19]
  (let [[_ [d1 d2 d3 d4 d5]] (decode-digits data19)]
    [:ok (+ d1 (* 10 d2) (* 100 d3) (* 1000 d4) (* 10000 d5))]))
