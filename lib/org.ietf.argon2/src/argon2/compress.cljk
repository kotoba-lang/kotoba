(ns argon2.compress
  "The compression function G, RFC 9106 §3.5, and the permutation P under it.

  A block is 1024 bytes: 128 64-bit words, held as 256 lanes in the flat
  arrays `argon2.u32` describes. Word `w` of a block starting at lane `off`
  is at `off + 2w` (low half) and `off + 2w + 1` (high half).

  Everything here mutates in place and allocates nothing per call. That is
  not premature: at the OWASP-recommended 19 MiB this function runs about
  39,000 times, each doing 128 mixing steps, so an allocation per step is
  about five million objects per hash."
  (:require [argon2.u32 :as u]))

;; ── the mixing step ──────────────────────────────────────────────────────────

(defn- fbla!
  "`v[i] <- v[i] + v[j] + 2 * lo32(v[i]) * lo32(v[j])`, mod 2^64.

  RFC 9106 calls this fBlaMka. The multiplication is the reason this library
  cannot reuse a 32-bit-only word layer: the product of the two low halves is
  a genuine 64-bit quantity that both the addition and the following rotation
  depend on.

  `t` is a two-lane scratch the caller owns. Nothing here allocates — this
  runs about five million times per hash at the recommended parameters, and a
  two-element vector per call is five million objects."
  [v i j t]
  (let [ai (* 2 i) bi (* 2 j)
        alo (u/rd v ai) ahi (u/rd v (inc ai))
        blo (u/rd v bi) bhi (u/rd v (inc bi))]
    (u/mul32! t alo blo)
    (let [mhi (u/rd t 0) mlo (u/rd t 1)
          ;; 2m, as a shift across the lane boundary rather than `(* 2 m)`
          ;; on a value that does not fit one lane.
          m2hi (u/u32 (bit-or (bit-shift-left mhi 1) (unsigned-bit-shift-right mlo 31)))
          m2lo (u/u32 (bit-shift-left mlo 1))]
      (u/add64! t ahi alo bhi blo)
      (u/add64! t (u/rd t 0) (u/rd t 1) m2hi m2lo)
      (u/wr v ai (u/rd t 1))
      (u/wr v (inc ai) (u/rd t 0)))))

(defn- xor-rotr!
  "`v[i] <- rotr64(v[i] XOR v[j], n)`."
  [v i j n t]
  (let [ai (* 2 i) bi (* 2 j)
        xlo (u/u32 (bit-xor (u/rd v ai) (u/rd v bi)))
        xhi (u/u32 (bit-xor (u/rd v (inc ai)) (u/rd v (inc bi))))]
    (u/rotr64! t xhi xlo n)
    (u/wr v ai (u/rd t 1))
    (u/wr v (inc ai) (u/rd t 0))))

(defn- gb!
  "RFC 9106 §3.5, the GB function. BLAKE2b's mixing step with the plain
  additions replaced by fBlaMka and the final rotation widened to 63."
  [v a b c d t]
  (fbla! v a b t)     (xor-rotr! v d a 32 t)
  (fbla! v c d t)     (xor-rotr! v b c 24 t)
  (fbla! v a b t)     (xor-rotr! v d a 16 t)
  (fbla! v c d t)     (xor-rotr! v b c 63 t))

;; ── the permutation ──────────────────────────────────────────────────────────

(def ^:private rows
  "P is applied to eight rows of sixteen consecutive words."
  (mapv (fn [i] (mapv #(+ (* 16 i) %) (range 16))) (range 8)))

(def ^:private cols
  "…then to eight columns, each taking two words from every row: words
  2i, 2i+1, 2i+16, 2i+17, … 2i+112, 2i+113. The pairing is what makes the
  second pass mix across rows rather than repeat the first."
  (mapv (fn [i] (vec (mapcat (fn [r] [(+ (* 2 i) (* 16 r)) (+ (* 2 i) (* 16 r) 1)])
                             (range 8))))
        (range 8)))

(defn- permute!
  "P over the sixteen words named by `idx`, at lane offset `off`."
  [v off idx t]
  (let [g (fn [a b c d]
            (gb! v (+ off (nth idx a)) (+ off (nth idx b))
                 (+ off (nth idx c)) (+ off (nth idx d)) t))]
    (g 0 4 8 12) (g 1 5 9 13) (g 2 6 10 14) (g 3 7 11 15)
    (g 0 5 10 15) (g 1 6 11 12) (g 2 7 8 13) (g 3 4 9 14)))

;; ── G ────────────────────────────────────────────────────────────────────────

(def block-lanes 256)
(def block-words 128)
(def block-bytes 1024)

(defn fill-block!
  "`mem[dst] <- G(mem[x], mem[y])`, or XORed into the existing block when
  `with-xor?`.

  G is `R = X XOR Y`, then P rowwise, then P columnwise, then XOR with R
  again. `r` and `z` are 256-lane scratch arrays the caller owns and reuses;
  they hold R and the value being permuted into Z.

  The final XOR with R is not decoration — without it G would be invertible,
  and the whole memory-hardness argument rests on it not being."
  [mem x y dst with-xor? r z t]
  (dotimes [i block-lanes]
    (let [v (u/u32 (bit-xor (u/rd mem (+ x i)) (u/rd mem (+ y i))))]
      (u/wr r i v)
      (u/wr z i v)))
  (dotimes [i 8] (permute! z 0 (nth rows i) t))
  (dotimes [i 8] (permute! z 0 (nth cols i) t))
  (dotimes [i block-lanes]
    (let [v (u/u32 (bit-xor (u/rd z i) (u/rd r i)))]
      (u/wr mem (+ dst i)
            (if with-xor? (u/u32 (bit-xor v (u/rd mem (+ dst i)))) v))))
  nil)

;; ── byte views ───────────────────────────────────────────────────────────────

(defn bytes->block!
  "Load 1024 little-endian bytes into the block at lane offset `off`."
  [mem off bs]
  (dotimes [w block-words]
    (let [b (* 8 w)
          lo (+ (nth bs b)
                (* 256 (nth bs (+ b 1)))
                (* 65536 (nth bs (+ b 2)))
                (* 16777216 (nth bs (+ b 3))))
          hi (+ (nth bs (+ b 4))
                (* 256 (nth bs (+ b 5)))
                (* 65536 (nth bs (+ b 6)))
                (* 16777216 (nth bs (+ b 7))))]
      (u/wr mem (+ off (* 2 w)) lo)
      (u/wr mem (+ off (* 2 w) 1) hi)))
  nil)

(defn block->bytes
  "The block at lane offset `off` as 1024 little-endian bytes."
  [mem off]
  (into []
        (mapcat (fn [w]
                  (into (u/le32 (u/rd mem (+ off (* 2 w))))
                        (u/le32 (u/rd mem (+ off (* 2 w) 1))))))
        (range block-words)))

(defn word0
  "The first 64-bit word of the block at `off`, as `[hi lo]`. Argon2d takes
  its addressing from exactly this."
  [mem off]
  [(u/rd mem (inc off)) (u/rd mem off)])
