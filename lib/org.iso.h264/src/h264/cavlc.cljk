(ns h264.cavlc
  "H.264 baseline-profile CAVLC residual entropy decode (ITU-T H.264 /
   ISO/IEC 14496-10 §9.2 \"CAVLC parsing process for transform coefficient
   levels\"). Scope: luma blocks (the Intra16x16 DC block, maxNumCoeff
   16, and regular/AC 4x4 blocks, maxNumCoeff 15 or 16) AND the ChromaArrayType
   1 (4:2:0) chroma DC special case (§9.2.1's `nC == -1`, maxNumCoeff 4,
   `residual-block!` invoked with `nc` = `:chroma-dc`) — chroma AC 4x4
   blocks reuse the SAME regular luma-shaped VLC tables/path (chroma AC
   blocks are neighbor-derived like any other 4x4 block, per spec; only
   the chroma DC block has its own nC==-1 special tables). ChromaArrayType
   2/3 (4:2:2/4:4:4) chroma DC (`nC == -2`) is NOT implemented (this repo's
   decode scope is 4:2:0 only, see `h264.decode`).

   All VLC tables (`coeff-token-len`/`coeff-token-bits` for the 4 nC
   classes, `total-zeros-len`/`total-zeros-bits`, `run-len`/`run-bits`,
   `chroma-dc-coeff-token-len`/`-bits`, `chroma-dc-total-zeros-len`/`-bits`)
   are transcribed byte-for-byte from FFmpeg's reference decoder
   (`libavcodec/h264_cavlc.c`, https://github.com/FFmpeg/FFmpeg — these
   are themselves direct transcriptions of ITU-T H.264 Tables 9-5, 9-7,
   9-10). The decode algorithm (`residual-block!`) follows spec §9.2.1's
   pseudocode (coeff_token → trailing-ones sign bits → level_prefix/suffix
   → total_zeros → run_before → position reconstruction), cross-checked
   against `h264_cavlc.c`'s `decode_residual`.

   New implementation as part of the kotoba-lang reverse-domain
   media/graphics standards-substrate split (com-junkawasaki/root)."
  (:require [h264.expgolomb :as eg]))

;; --- coeff_token VLC tables, Table 9-5 (4 nC classes: 0<=nC<2, 2<=nC<4,
;;     4<=nC<8, nC>=8). Row-major [TotalCoeff 0..16][TrailingOnes 0..3]. ---

(def coeff-token-len
  [[1 0 0 0
    6 2 0 0    8 6 3 0    9 8 7 5    10 9 8 6
    11 10 9 7  13 11 10 8 13 13 11 9 13 13 13 10
    14 14 13 11 14 14 14 13 15 15 14 14 15 15 15 14
    16 15 15 15 16 16 16 15 16 16 16 16 16 16 16 16]
   [2 0 0 0
    6 2 0 0    6 5 3 0    7 6 6 4    8 6 6 4
    8 7 7 5    9 8 8 6    11 9 9 6   11 11 11 7
    12 11 11 9 12 12 12 11 12 12 12 11 13 13 13 12
    13 13 13 13 13 14 13 13 14 14 14 13 14 14 14 14]
   [4 0 0 0
    6 4 0 0    6 5 4 0    6 5 5 4    7 5 5 4
    7 5 5 4    7 6 6 4    7 6 6 4    8 7 7 5
    8 8 7 6    9 8 8 7    9 9 8 8    9 9 9 8
    10 9 9 9   10 10 10 10 10 10 10 10 10 10 10 10]
   [6 0 0 0
    6 6 0 0    6 6 6 0    6 6 6 6    6 6 6 6
    6 6 6 6    6 6 6 6    6 6 6 6    6 6 6 6
    6 6 6 6    6 6 6 6    6 6 6 6    6 6 6 6
    6 6 6 6    6 6 6 6    6 6 6 6    6 6 6 6]])

(def coeff-token-bits
  [[1 0 0 0
    5 1 0 0    7 4 1 0    7 6 5 3    7 6 5 3
    7 6 5 4    15 6 5 4   11 14 5 4  8 10 13 4
    15 14 9 4  11 10 13 12 15 14 9 12 11 10 13 8
    15 1 9 12  11 14 13 8 7 10 9 12 4 6 5 8]
   [3 0 0 0
    11 2 0 0   7 7 3 0    7 10 9 5   7 6 5 4
    4 6 5 6    7 6 5 8    15 6 5 4   11 14 13 4
    15 10 9 4  11 14 13 12 8 10 9 8  15 14 13 12
    11 10 9 12 7 11 6 8   9 8 10 1   7 6 5 4]
   [15 0 0 0
    15 14 0 0  11 15 13 0 8 12 14 12 15 10 11 11
    11 8 9 10  9 14 13 9  8 10 9 8   15 14 13 13
    11 14 10 12 15 10 13 12 11 14 9 12 8 10 13 8
    13 7 9 12  9 12 11 10 5 8 7 6    1 4 3 2]
   [3 0 0 0
    0 1 0 0    4 5 6 0    8 9 10 11  12 13 14 15
    16 17 18 19 20 21 22 23 24 25 26 27 28 29 30 31
    32 33 34 35 36 37 38 39 40 41 42 43 44 45 46 47
    48 49 50 51 52 53 54 55 56 57 58 59 60 61 62 63]])

;; --- chroma DC coeff_token VLC, Table 9-5 nC==-1 special case (ChromaArrayType
;;     1 / 4:2:0 only — one fixed table, no neighbor-derived nC class since the
;;     chroma DC block always uses this same table regardless of neighbors).
;;     Row-major [TotalCoeff 0..4][TrailingOnes 0..3]. ---

(def chroma-dc-coeff-token-len
  [2 0 0 0
   6 1 0 0
   6 6 3 0
   6 7 7 6
   6 8 8 7])

(def chroma-dc-coeff-token-bits
  [1 0 0 0
   7 1 0 0
   4 6 1 0
   3 3 2 5
   2 3 2 0])

;; --- chroma DC total_zeros VLC, Table 9-9b (ChromaArrayType 1 / 4:2:0,
;;     maxNumCoeff 4; row index = TotalCoeff-1, 1..3). ---

(def chroma-dc-total-zeros-len
  [[1 2 3 3]
   [1 2 2]
   [1 1]])

(def chroma-dc-total-zeros-bits
  [[1 1 1 0]
   [1 1 0]
   [1 0]])

(defn- nc-class
  "nC → coeff_token VLC table row index (0: nC<2, 1: 2<=nC<4, 2: 4<=nC<8,
   3: nC>=8)."
  [nc]
  (cond (< nc 2) 0 (< nc 4) 1 (< nc 8) 2 :else 3))

(defn- decode-coeff-token-generic!
  "Reads coeff_token via linear VLC search over a flat, row-major
   [TotalCoeff 0..max-tc][TrailingOnes 0..3] `lens`/`bits` table. Returns
   [total-coeff trailing-ones]. Shared by the regular (luma / chroma AC,
   max-tc=16) and chroma-DC (nC==-1, max-tc=4) coeff_token tables — the
   search algorithm is identical, only the table and its TotalCoeff bound
   differ."
  [r lens bits max-tc]
  (let [start-byte @(:bytepos r) start-bit @(:bitpos r)
        max-len (apply max lens)]
    (loop [len 1]
      (when (> len max-len)
        (throw (ex-info "h264.cavlc: no coeff_token VLC match" {})))
      (reset! (:bytepos r) start-byte) (reset! (:bitpos r) start-bit)
      (let [code (eg/bits! r len)
            hit (loop [tc 0]
                  (if (> tc max-tc)
                    nil
                    (let [to-match
                          (loop [to 0]
                            (if (> to 3)
                              nil
                              (let [idx (+ (* tc 4) to)]
                                (if (and (not (and (zero? tc) (pos? to)))
                                         (= (nth lens idx) len)
                                         (= (nth bits idx) code))
                                  to
                                  (recur (inc to))))))]
                      (if to-match [tc to-match] (recur (inc tc))))))]
        (if hit
          (do (reset! (:bytepos r) start-byte) (reset! (:bitpos r) start-bit)
              (eg/bits! r len)
              hit)
          (recur (inc len)))))))

(defn- decode-coeff-token!
  "Reads coeff_token for a regular (luma or chroma AC) 4x4/16-coeff block
   via linear VLC search over `coeff-token-len`/`-bits` for the given nC.
   Returns [total-coeff trailing-ones]."
  [r nc]
  (let [class (nc-class nc)]
    (decode-coeff-token-generic! r (nth coeff-token-len class) (nth coeff-token-bits class) 16)))

(defn- decode-chroma-dc-coeff-token!
  "Reads coeff_token for the ChromaArrayType 1 (4:2:0) chroma DC block
   (nC==-1 special case, §9.2.1) — a single fixed table, not neighbor-
   derived. Returns [total-coeff trailing-ones]."
  [r]
  (decode-coeff-token-generic! r chroma-dc-coeff-token-len chroma-dc-coeff-token-bits 4))

;; --- total_zeros VLC, Table 9-7 (maxNumCoeff 16 — also used for the
;;     Intra16x16 luma DC block and luma AC (maxNumCoeff 15) blocks per
;;     spec; row index = TotalCoeff-1, 1..15). ---

(def total-zeros-len
  [[1 3 3 4 4 5 5 6 6 7 7 8 8 9 9 9]
   [3 3 3 3 3 4 4 4 4 5 5 6 6 6 6]
   [4 3 3 3 4 4 3 3 4 5 5 6 5 6]
   [5 3 4 4 3 3 3 4 3 4 5 5 5]
   [4 4 4 3 3 3 3 3 4 5 4 5]
   [6 5 3 3 3 3 3 3 4 3 6]
   [6 5 3 3 3 2 3 4 3 6]
   [6 4 5 3 2 2 3 3 6]
   [6 6 4 2 2 3 2 5]
   [5 5 3 2 2 2 4]
   [4 4 3 3 1 3]
   [4 4 2 1 3]
   [3 3 1 2]
   [2 2 1]
   [1 1]])

(def total-zeros-bits
  [[1 3 2 3 2 3 2 3 2 3 2 3 2 3 2 1]
   [7 6 5 4 3 5 4 3 2 3 2 3 2 1 0]
   [5 7 6 5 4 3 4 3 2 3 2 1 1 0]
   [3 7 5 4 6 5 4 3 3 2 2 1 0]
   [5 4 3 7 6 5 4 3 2 1 1 0]
   [1 1 7 6 5 4 3 2 1 1 0]
   [1 1 5 4 3 3 2 1 1 0]
   [1 1 1 3 3 2 2 1 0]
   [1 0 1 3 2 1 1 1]
   [1 0 1 3 2 1 1]
   [0 1 1 2 1 3]
   [0 1 1 1 1]
   [0 1 1 1]
   [0 1 1]
   [0 1]])

;; --- run_before VLC, Table 9-10 (row index = min(zerosLeft,7)-1). ---

(def run-len
  [[1 1]
   [1 2 2]
   [2 2 2 2]
   [2 2 2 3 3]
   [2 2 3 3 3 3]
   [2 3 3 3 3 3 3]
   [3 3 3 3 3 3 3 4 5 6 7 8 9 10 11]])

(def run-bits
  [[1 0]
   [1 1 0]
   [3 2 1 0]
   [3 2 1 1 0]
   [3 2 3 2 1 0]
   [3 0 1 3 2 5 4]
   [7 6 5 4 3 2 1 1 1 1 1 1 1 1 1]])

(defn- decode-flatlist-vlc!
  [r lens bits]
  (let [start-byte @(:bytepos r) start-bit @(:bitpos r)
        max-len (apply max lens)]
    (loop [len 1]
      (when (> len max-len)
        (throw (ex-info "h264.cavlc: no VLC match" {})))
      (reset! (:bytepos r) start-byte) (reset! (:bitpos r) start-bit)
      (let [code (eg/bits! r len)
            idx (loop [i 0]
                  (cond (>= i (count lens)) nil
                        (and (= (nth lens i) len) (= (nth bits i) code)) i
                        :else (recur (inc i))))]
        (if idx
          (do (reset! (:bytepos r) start-byte) (reset! (:bitpos r) start-bit)
              (eg/bits! r len)
              idx)
          (recur (inc len)))))))

(defn residual-block!
  "Decode one CAVLC residual_block (spec §9.2.1/9.2.2/9.2.3) from reader
   `r`. `nc` selects the coeff_token VLC class (already resolved by the
   caller from neighbor total_coeff per §9.2.1 clause 9.2.1) — OR the
   keyword `:chroma-dc` to select the fixed nC==-1 chroma-DC table
   (§9.2.1's special case; `max-num-coeff` must be 4 in that case, and no
   neighbor derivation applies). `max-num-coeff` is 16 for the Intra16x16
   luma DC block and regular 4x4 luma/chroma-AC blocks, 15 for Intra16x16
   luma AC / chroma AC blocks, 4 for the chroma DC block.

   Returns {:coeffs (vector of `max-num-coeff` ints, SCAN-ORDER — the
   caller unscans via `codec-primitives.scan`) :total-coeff int}."
  [r nc max-num-coeff]
  (let [[total-coeff trailing-ones] (if (= nc :chroma-dc)
                                       (decode-chroma-dc-coeff-token! r)
                                       (decode-coeff-token! r nc))]
    (if (zero? total-coeff)
      {:coeffs (vec (repeat max-num-coeff 0)) :total-coeff 0}
      (let [;; --- levels ---
            levels
            (loop [i 0 suffix-length (if (and (> total-coeff 10) (< trailing-ones 3)) 1 0)
                   acc []]
              (if (= i total-coeff)
                acc
                (if (< i trailing-ones)
                  (let [sign (eg/bit! r)]
                    (recur (inc i) suffix-length (conj acc (if (zero? sign) 1 -1))))
                  (let [level-prefix (loop [lz 0] (if (zero? (eg/bit! r)) (recur (inc lz)) lz))
                        level-suffix-size (cond (and (= level-prefix 14) (zero? suffix-length)) 4
                                                 (>= level-prefix 15) (- level-prefix 3)
                                                 :else suffix-length)
                        level-suffix (if (pos? level-suffix-size) (eg/bits! r level-suffix-size) 0)
                        level-code (+ (bit-shift-left (min 15 level-prefix) suffix-length) level-suffix)
                        level-code (if (and (>= level-prefix 15) (zero? suffix-length)) (+ level-code 15) level-code)
                        level-code (if (>= level-prefix 16) (+ level-code (- (bit-shift-left 1 (- level-prefix 3)) 4096)) level-code)
                        level-code (if (and (= i trailing-ones) (< trailing-ones 3)) (+ level-code 2) level-code)
                        v (if (even? level-code) (quot (+ level-code 2) 2) (quot (- (- level-code) 1) 2))
                        suffix-length' (if (zero? suffix-length) 1 suffix-length)
                        abs-v (if (neg? v) (- v) v)
                        suffix-length'' (if (and (> abs-v (bit-shift-left 3 (dec suffix-length'))) (< suffix-length' 6))
                                          (inc suffix-length') suffix-length')]
                    (recur (inc i) suffix-length'' (conj acc v))))))
            zeros-left (if (= total-coeff max-num-coeff)
                         0
                         (if (= nc :chroma-dc)
                           (decode-flatlist-vlc! r (nth chroma-dc-total-zeros-len (dec total-coeff))
                                                 (nth chroma-dc-total-zeros-bits (dec total-coeff)))
                           (decode-flatlist-vlc! r (nth total-zeros-len (dec total-coeff))
                                                 (nth total-zeros-bits (dec total-coeff)))))
            run-vals
            (loop [i 0 zl zeros-left acc []]
              (if (= i (dec total-coeff))
                (conj acc zl)
                (if (pos? zl)
                  (let [zl-idx (min (dec zl) 6)
                        rb (decode-flatlist-vlc! r (nth run-len zl-idx) (nth run-bits zl-idx))]
                    (recur (inc i) (- zl rb) (conj acc rb)))
                  (recur (inc i) zl (conj acc 0)))))
            coeffs (vec (repeat max-num-coeff 0))
            coeffs (loop [i (dec total-coeff) coeff-num -1 acc coeffs]
                     (if (neg? i)
                       acc
                       (let [coeff-num' (+ coeff-num (nth run-vals i) 1)]
                         (recur (dec i) coeff-num' (assoc acc coeff-num' (nth levels i))))))]
        {:coeffs coeffs :total-coeff total-coeff}))))

;; --- encode side (ADR-2607122000 Migration step 8) ---
;;
;; Writes the SAME syntax `residual-block!` reads, reusing its VLC tables
;; as reverse-lookup tables (linear scan for the matching [len,bits] row —
;; simple and correct; performance doesn't matter for this non-realtime
;; reference encoder). The trickiest part is `encode-level!`, the exact
;; mechanical inverse of `residual-block!`'s level_prefix/level_suffix/
;; level_code state machine (suffix_length escalation) — derived by tracing
;; that decode loop step-by-step (not from a separately memorized spec
;; description) and verified via `cavlc_test.clj`'s round-trip tests
;; (encode then decode with THIS SAME repo's `residual-block!`, covering
;; trailing-ones, escape-range levels, and the suffix_length escalation
;; path).

(defn- write-unary-prefix!
  "Write `n` zero bits then a terminating 1 bit — the exact inverse of the
   `(loop [lz 0] (if (zero? (eg/bit! r)) (recur (inc lz)) lz))` leading-zero
   count read used throughout this ns (level_prefix here, and implicitly by
   `decode-flatlist-vlc!`'s underlying bit reads elsewhere)."
  [w n]
  (dotimes [_ n] (eg/write-bit! w 0))
  (eg/write-bit! w 1))

(defn- find-flat-vlc-code
  "Reverse-lookup: the [len bits] entry at `idx` in parallel `lens`/`bits`
   vectors — the exact inverse of `decode-flatlist-vlc!`'s linear search
   (that fn finds `idx` given a bit-matched len/code; this does the
   opposite: given `idx`, returns the code to write)."
  [lens bits idx]
  [(nth lens idx) (nth bits idx)])

(defn- encode-coeff-token!
  "Write coeff_token for a regular (luma or chroma AC) block, given `nc`
   (same neighbor-derived value the decode side would compute) and
   `total-coeff`/`trailing-ones`. Reverse lookup into `coeff-token-len`/
   `-bits` for the nC class — exact inverse of `decode-coeff-token!`."
  [w nc total-coeff trailing-ones]
  (let [class (nc-class nc)
        idx (+ (* total-coeff 4) trailing-ones)
        [len bits] (find-flat-vlc-code (nth coeff-token-len class) (nth coeff-token-bits class) idx)]
    (eg/write-bits! w len bits)))

(defn- encode-chroma-dc-coeff-token!
  "Write coeff_token for the ChromaArrayType 1 (4:2:0) chroma DC block
   (nC==-1 special case) — exact inverse of `decode-chroma-dc-coeff-token!`."
  [w total-coeff trailing-ones]
  (let [idx (+ (* total-coeff 4) trailing-ones)
        [len bits] (find-flat-vlc-code chroma-dc-coeff-token-len chroma-dc-coeff-token-bits idx)]
    (eg/write-bits! w len bits)))

(defn- encode-total-zeros!
  [w nc total-coeff total-zeros]
  (let [[lens bits] (if (= nc :chroma-dc)
                       [(nth chroma-dc-total-zeros-len (dec total-coeff))
                        (nth chroma-dc-total-zeros-bits (dec total-coeff))]
                       [(nth total-zeros-len (dec total-coeff))
                        (nth total-zeros-bits (dec total-coeff))])
        [len code] (find-flat-vlc-code lens bits total-zeros)]
    (eg/write-bits! w len code)))

(defn- encode-run-before!
  [w zeros-left run]
  (let [zl-idx (min (dec zeros-left) 6)
        [len code] (find-flat-vlc-code (nth run-len zl-idx) (nth run-bits zl-idx) run)]
    (eg/write-bits! w len code)))

(defn- level-code->prefix-suffix
  "Given a target `level-code` (already inverse-mapped from the signed
   level per `level-code<->v` below) and the CURRENT `suffix-length` state,
   returns `[level-prefix level-suffix level-suffix-size]` — the exact
   mechanical inverse of `residual-block!`'s
   `level-code (+ (bit-shift-left (min 15 level-prefix) suffix-length) level-suffix)`
   (plus its `>=15`/`>=16` escape-range adjustments), derived by case
   analysis on that decode formula rather than a separately memorized
   description."
  [level-code suffix-length]
  (cond
    ;; suffix-length = 0, level-prefix < 14: level-code = level-prefix directly (no suffix bits)
    (and (zero? suffix-length) (< level-code 14))
    [level-code 0 0]

    ;; suffix-length = 0, level-prefix == 14 special case (level-suffix-size forced to 4
    ;; even though suffix-length is 0): level-code = 14 + level-suffix, level-suffix in 0..15
    (and (zero? suffix-length) (< level-code 30))
    [14 (- level-code 14) 4]

    ;; suffix-length = 0, escape range (level-prefix >= 15): level-code = 15 + level-suffix
    ;; (the ">=15 && suffix-length==0" "+15" adjustment), level-suffix-size = level-prefix-3
    (zero? suffix-length)
    (let [suffix-val (- level-code 30)
          prefix (loop [p 15] (if (< suffix-val (bit-shift-left 1 (- p 3))) p (recur (inc p))))]
      [prefix suffix-val (- prefix 3)])

    :else
    ;; suffix-length > 0 (normal case): level-prefix = level-code >> suffix-length (if < 15)
    (let [prefix-guess (bit-shift-right level-code suffix-length)]
      (if (< prefix-guess 15)
        [prefix-guess (bit-and level-code (dec (bit-shift-left 1 suffix-length))) suffix-length]
        ;; escape (level-prefix >= 15): level-code = (15<<suffix-length) + level-suffix
        (let [over (- level-code (bit-shift-left 15 suffix-length))
              prefix (loop [p 15] (if (< over (bit-shift-left 1 (- p 3))) p (recur (inc p))))]
          [prefix over (- prefix 3)])))))

(defn- v->level-code
  "Signed level `v` → `level-code`, the exact inverse of `residual-block!`'s
   `v = if (even? level-code) (quot (+ level-code 2) 2) (quot (- (- level-code) 1) 2))`."
  [v]
  (if (pos? v) (- (* 2 v) 2) (- (* -2 v) 1)))

(defn- encode-level!
  "Write one level_prefix/level_suffix for signed level `v` (a non-trailing-
   one level, i.e. `i >= trailing-ones` in `residual-block!`'s loop) at
   read-order index `i`, given the running `suffix-length` state and
   `trailing-ones`. Returns the UPDATED suffix-length (mirrors
   `residual-block!`'s `suffix-length''` computation exactly, so callers can
   thread it through the same way decode does). Handles the `i ==
   trailing-ones && trailing-ones < 3` \"+2\" adjustment (undone before
   deriving prefix/suffix) — this repo's encoder never produces `abs(v)=1`
   at that position (that would have made it a 4th trailing-one instead, an
   invariant enforced by `h264.encode`'s CAVLC-shaping)."
  [w v i trailing-ones suffix-length]
  (let [level-code (v->level-code v)
        level-code (if (and (= i trailing-ones) (< trailing-ones 3)) (- level-code 2) level-code)
        _ (when (neg? level-code)
            (throw (ex-info "h264.cavlc/encode-level!: level-code went negative after removing the trailing-ones +2 adjustment — caller produced abs(v)=1 right after a <3 run of trailing ones, which decode would have read as a 4th trailing one instead"
                             {:v v :i i :trailing-ones trailing-ones})))
        [level-prefix level-suffix level-suffix-size] (level-code->prefix-suffix level-code suffix-length)]
    (write-unary-prefix! w level-prefix)
    (when (pos? level-suffix-size) (eg/write-bits! w level-suffix-size level-suffix))
    (let [suffix-length' (if (zero? suffix-length) 1 suffix-length)
          abs-v (if (neg? v) (- v) v)]
      (if (and (> abs-v (bit-shift-left 3 (dec suffix-length'))) (< suffix-length' 6))
        (inc suffix-length')
        suffix-length'))))

(defn encode-residual-block!
  "Write one CAVLC residual_block for `coeffs` (a `max-num-coeff`-length
   SCAN-ORDER vector, same shape `residual-block!` returns as `:coeffs` —
   i.e. the caller has already zigzag-SCANNED a raster coefficient array).
   `nc` is the coeff_token VLC class selector (a real neighbor-derived nC,
   OR `:chroma-dc` for the ChromaArrayType 1 chroma-DC nC==-1 special
   case) — MUST be derived by the caller using the exact same neighbor
   logic `h264.decode` uses, or the encoded stream will decode to the wrong
   values even though it's syntactically well-formed.

   Returns `total-coeff` (the same value decode's `residual-block!` would
   report — feeds this block's own neighbor-nC contribution for MBs to the
   right/below, mirroring `h264.decode`'s bookkeeping)."
  [w nc max-num-coeff coeffs]
  (let [nonzero (vec (keep-indexed (fn [pos v] (when-not (zero? v) [pos v])) coeffs))
        total-coeff (count nonzero)]
    (if (zero? total-coeff)
      (do (if (= nc :chroma-dc)
            (encode-chroma-dc-coeff-token! w 0 0)
            (encode-coeff-token! w nc 0 0))
          0)
      (let [;; trailing-ones: consecutive |v|=1 entries at the HIGH end (last
            ;; in scan order = highest scan position), capped at 3
            trailing-ones (loop [k 0]
                             (if (>= k (min 3 total-coeff))
                               k
                               (let [[_ v] (nth nonzero (- total-coeff 1 k))]
                                 (if (= 1 (if (neg? v) (- v) v)) (recur (inc k)) k))))
            ;; levels[i] for i=0..total-coeff-1, i=0 = HIGHEST scan-position
            ;; value (read first in bitstream), i=total-coeff-1 = LOWEST
            ;; scan-position value (read last) -- see cavlc.cljc encode-side
            ;; docstring / decode trace.
            levels (mapv (fn [i] (nth nonzero (- total-coeff 1 i))) (range total-coeff))
            positions (mapv first levels)
            values (mapv second levels)
            ;; positions[0] = highest (P[k]) nonzero scan position; total
            ;; zeros preceding it (spec's total_zeros) = P[k]+1-total_coeff.
            zeros-left (- (first positions) (dec total-coeff))]
        (when (= nc :chroma-dc)
          (encode-chroma-dc-coeff-token! w total-coeff trailing-ones))
        (when-not (= nc :chroma-dc)
          (encode-coeff-token! w nc total-coeff trailing-ones))
        ;; levels (signs for trailing ones, full level_prefix/suffix otherwise)
        (loop [i 0 suffix-length (if (and (> total-coeff 10) (< trailing-ones 3)) 1 0)]
          (when (< i total-coeff)
            (let [v (nth values i)]
              (if (< i trailing-ones)
                (do (eg/write-bit! w (if (pos? v) 0 1))
                    (recur (inc i) suffix-length))
                (let [suffix-length' (encode-level! w v i trailing-ones suffix-length)]
                  (recur (inc i) suffix-length'))))))
        ;; total_zeros (only if fewer nonzero than max — matches decode)
        (when (< total-coeff max-num-coeff)
          (encode-total-zeros! w nc total-coeff zeros-left))
        ;; run_before, for i=0..total-coeff-2 (matches decode: last one is
        ;; inferred as whatever zeros remain, no bits written). run_vals[i]
        ;; = positions[i] - positions[i+1] - 1 (the zero-gap between the
        ;; i-th and (i+1)-th read coefficient, in bitstream/high-to-low
        ;; scan-position read order — see positions' construction above).
        (loop [i 0 zl zeros-left]
          (when (< i (dec total-coeff))
            (if (pos? zl)
              (let [run (- (nth positions i) (nth positions (inc i)) 1)]
                (encode-run-before! w zl run)
                (recur (inc i) (- zl run)))
              (recur (inc i) zl))))
        total-coeff))))
