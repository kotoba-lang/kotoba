(ns h264.interp
  "H.264 sub-pixel motion-compensated interpolation:
   - Luma quarter-sample interpolation (ITU-T H.264 / ISO/IEC 14496-10
     §8.4.2.2.1 \"Luma sample interpolation process\"): a 6-tap FIR filter
     `(1,-5,20,20,-5,1)` for half-sample positions, then simple rounded
     averaging for quarter-sample positions.
   - Chroma sample interpolation (§8.4.2.2.2 \"Chroma sample interpolation
     process\", ChromaArrayType 1 / 4:2:0 only, matching this repo's whole
     chroma scope elsewhere): bilinear interpolation at 1/8-chroma-sample
     precision, since a chroma motion vector derived from a luma one
     (§8.4.1.4, ChromaArrayType 1: `mvCLX == mvLX`, see `mc-chroma-block`'s
     docstring for why no additional scaling is needed) lands on an
     eighth-chroma-sample grid.

   Pure functions over a flat row-major picture-boundary-extended plane —
   no bitstream/CAVLC dependency, independently callable/testable from
   `h264.decode`'s macroblock loop (which is the only caller).

   **Arithmetic cross-checked against FFmpeg's actual reference-decoder
   source** (`libavcodec/h264qpel_template.c` for luma six-tap + averaging,
   `libavcodec/h264chroma_template.c` for chroma bilinear —
   https://github.com/FFmpeg/FFmpeg, matching this repo's existing
   discipline in `h264.quant`/`h264.transform` of cross-checking dequant/
   transform arithmetic against the same reference source), NOT
   reconstructed from memory of the spec prose alone:

   - The 6-tap filter sum for a half-sample position (e.g. `b`, horizontal,
     between full-sample `G` and `H`) is `(G+H)*20 - (F+I)*5 + (E+J)` where
     E,F,G,H,I,J are the 6 consecutive full-samples centered on the
     G/H pair (2 samples further out on the F side, 3 further out on the I
     side) — rounded via `Clip1( (sum+16) >> 5 )`.
   - The center half-sample `j` (both directions half-sample) is NOT simply
     a 2-D convolution rounded once — per FFmpeg's own two-pass
     `h264_qpel_hv_lowpass` (horizontal 6-tap pass producing UNROUNDED,
     UNCLIPPED 16-bit-range intermediate sums at 6 rows, then a vertical
     6-tap pass over those same intermediate sums, rounded ONCE at the end
     via `Clip1( (sum+512) >> 10 )`), this ns computes `j` as a direct
     algebraic reassociation of that exact same two-pass integer sum
     (`center-j` below) — mathematically identical (finite integer
     addition/multiplication is associative/commutative; there is no
     intermediate rounding to reorder around), just without needing an
     explicit intermediate buffer since `sample` gives O(1) random access
     into the whole reference plane already. Getting this order wrong
     (e.g. clipping/rounding the horizontal pass before the vertical pass)
     would silently produce a plausible-looking but WRONG value — this is
     exactly the kind of \"intermediate bit-width/clipping-timing\" mistake
     the calling task's own instructions flagged as the well-known pitfall
     here, hence cross-checking against FFmpeg's source rather than
     reimplementing from a recalled formula.
   - Quarter-sample positions (`a,c,d,e,f,g,i,k,n,p,q,r`, §8.4.2.2.1 Figure
     8-4's naming) are ALL a plain rounded average of exactly two of
     {the integer sample, a half-sample} — `avg1` — never a 3- or 4-way
     average, never independently filtered.
   - Chroma bilinear interpolation (§8.4.2.2.2): weights `A=(8-x)(8-y)
     B=x(8-y) C=(8-x)y D=xy` (x,y = eighth-chroma-sample fractional parts,
     0..7) over the 2x2 integer-chroma-sample neighborhood, rounded via
     `(A*p00+B*p01+C*p10+D*p11+32) >> 6` — provably always in range 0..255
     given inputs in that range (weights sum to 64), matching why FFmpeg's
     own `op_put` for chroma has no explicit clip, though this ns still
     applies `clip8` defensively (spec's own `Clip1C` notation does, even
     though it's a mathematical no-op here).
   - Picture-boundary extension: reference samples at coordinates outside
     the decoded picture are substituted by the nearest picture-boundary
     sample (§8.4.2.2.1's boundary-sample derivation process) — implemented
     by `sample`'s coordinate clamping, needed whenever a motion vector (or
     the 6-tap filter's own +/-2/+3 reach) points outside the picture.

   ## `sample` is the hottest function in a P-frame encode, and copying the
   ## support region into an array does NOT help (measured, 2026-07-30)

   A sampling profile of one P-frame encode attributes **42.5%** of the whole
   frame to `sample` — more than motion estimation's own arithmetic, residual
   coding and entropy coding combined (`com-junkawasaki/root` ADR-2800002800).
   The obvious reading is that the read itself is expensive (a clamp plus a
   trie walk into a ~900k-element persistent vector) and that hoisting the
   block's whole support region into a dense array first would fix it.

   **It was implemented and it was 1.3x SLOWER** — measured by interleaving the
   two versions so both saw the same machine load, byte-identical output in
   every run, three rounds, no ambiguity. Two reasons, both worth knowing
   before trying again:

   - It relocates reads instead of removing them. Copying a 21x21 window costs
     441 plane reads plus 441 array writes, and the interpolators then still
     perform every one of their original reads, just against the copy.
   - The read pattern was already cache-friendly. A block's support region
     spans a few dozen 32-element vector leaves, all resident after the first
     pass, so the trie walk was predictable rather than miss-bound.

   Sizing the window per fraction (no padding when a fraction is zero) removed
   part of the loss but not all of it, because motion estimation's integer
   search — 289 of 338 candidates per macroblock at the default search range —
   reads each pixel exactly ONCE, so for the common case any copy is pure
   overhead.

   What the 42.5% actually reflects is the number of CALLS, not their cost:
   `center-j` evaluates `six-tap-h` at six rows for every output pixel, so one
   pixel costs 36 reads, and adjacent pixels re-read five of those six rows.
   Removing that means computing the horizontal pass ONCE into an intermediate
   buffer and running the vertical pass over it — exactly FFmpeg's two-pass
   `h264_qpel_hv_lowpass`, which the `center-j` note above describes and this
   namespace deliberately does not do. That, not a support window, is the
   change worth measuring next."
  )

(defn- clip8 [v] (max 0 (min 255 v)))

(defn- sample
  "Read one full-pel sample from flat row-major `plane` (dimensions `w`x`h`)
   at (x,y), clamping out-of-range coordinates to the nearest picture-
   boundary sample (see namespace docstring)."
  [plane w h x y]
  (let [cx (max 0 (min (dec w) x))
        cy (max 0 (min (dec h) y))]
    (nth plane (+ (* cy w) cx))))

(defn plane->array
  "Copy a flat row-major plane into a dense integer array.

   Motion estimation reads the reference plane on the order of a million times
   per frame, and a Clojure vector read is a bounds check, a trie walk and an
   unbox where an array read is one load. MEASURED on this repo's own 16x16 SAD,
   same numbers, changing only the representation:

     vector-of-row-vectors + nth   3051 ns/SAD   11.92 ns/px
     flat persistent vector + nth  4051 ns/SAD   15.83 ns/px
     int-array + aget               183 ns/SAD    0.72 ns/px   (16.6x)

   Converting is O(w*h) and happens ONCE per frame, against ~10^6 reads of it —
   which is the whole difference from the support-window scheme that was tried
   and reverted (see the namespace docstring): that COPIED plane data per
   candidate block and added work, this changes the representation the reads go
   through and removes work."
  [plane]
  #?(:clj (int-array plane) :cljs (into-array plane)))

(defn- sample-arr
  "`sample`, but reading an array plane. Separate rather than making `sample`
   itself array-only because `sample` is on the decoder's path too, and the
   `^ints` hint that makes `aget` non-reflective cannot be satisfied by a
   caller passing a vector."
  [^ints plane w h x y]
  (let [cx (max 0 (min (dec w) x))
        cy (max 0 (min (dec h) y))]
    (aget plane (+ (* cy w) cx))))

(defn- new-window
  "Dense integer array of `n` entries, for the precomputed planes below.
   `aget`/`aset` on it MUST be reached through an `^ints`-hinted local or
   parameter: unhinted, they compile to reflective array access, and measured
   that turned a one-second frame encode into minutes."
  [n]
  #?(:clj (int-array n) :cljs (make-array n)))

(defn- six-tap-h
  "Unrounded, unclipped horizontal 6-tap FIR sum (§8.4.2.2.1) centered
   between (x,y) and (x+1,y): (G+H)*20 - (F+I)*5 + (E+J)."
  [plane w h x y]
  (+ (* 20 (+ (sample plane w h x y) (sample plane w h (inc x) y)))
     (* -5 (+ (sample plane w h (dec x) y) (sample plane w h (+ x 2) y)))
     (sample plane w h (- x 2) y)
     (sample plane w h (+ x 3) y)))

(defn- six-tap-v
  "Same 6-tap FIR sum, vertical direction, centered between (x,y) and
   (x,y+1)."
  [plane w h x y]
  (+ (* 20 (+ (sample plane w h x y) (sample plane w h x (inc y))))
     (* -5 (+ (sample plane w h x (dec y)) (sample plane w h x (+ y 2))))
     (sample plane w h x (- y 2))
     (sample plane w h x (+ y 3))))

(defn- half-h
  "Half-sample horizontal position ('b'/'s' in Figure 8-4, depending on
   which row `y` is): `Clip1( (six-tap-h + 16) >> 5 )`."
  [plane w h x y]
  (clip8 (bit-shift-right (+ (six-tap-h plane w h x y) 16) 5)))

(defn- half-v
  "Half-sample vertical position ('h'/'m' in Figure 8-4, depending on which
   column `x` is): `Clip1( (six-tap-v + 16) >> 5 )`."
  [plane w h x y]
  (clip8 (bit-shift-right (+ (six-tap-v plane w h x y) 16) 5)))

(defn- center-j
  "Center half-sample position ('j' in Figure 8-4): the vertical 6-tap
   filter applied to the UNROUNDED horizontal 6-tap sums at the 6 rows
   y-2..y+3 (see namespace docstring for why this is exactly FFmpeg's
   two-pass `hv_lowpass`, not an approximation), rounded once via
   `Clip1( (sum + 512) >> 10 )`."
  [plane w h x y]
  (let [hs (fn [dy] (six-tap-h plane w h x (+ y dy)))]
    (clip8 (bit-shift-right
            (+ (* 20 (+ (hs 0) (hs 1)))
               (* -5 (+ (hs -1) (hs 2)))
               (hs -2) (hs 3)
               512)
            10))))

(defn- avg1
  "Rounded average of two already-clipped (0..255) sample values —
   `(a+b+1)>>1` — used for every quarter-sample position (§8.4.2.2.1: each
   quarter-sample is a plain 2-way average of an integer- or half-sample
   neighbor pair, never independently filtered)."
  [a b]
  (bit-shift-right (+ a b 1) 1))

(defn quarter-pel-luma
  "One interpolated luma sample (§8.4.2.2.1 Figure 8-4) at full-pel base
   position (x,y) with quarter-sample offset (fx,fy), each 0..3 (0 = the
   integer sample itself). Covers all 16 (fx,fy) combinations — see
   namespace docstring for the FFmpeg cross-check this table is built from."
  [plane w h x y fx fy]
  (cond
    (and (zero? fx) (zero? fy)) (sample plane w h x y)
    (and (= fx 2) (zero? fy)) (half-h plane w h x y)
    (and (zero? fx) (= fy 2)) (half-v plane w h x y)
    (and (= fx 2) (= fy 2)) (center-j plane w h x y)
    (and (= fx 1) (zero? fy)) (avg1 (sample plane w h x y) (half-h plane w h x y))
    (and (= fx 3) (zero? fy)) (avg1 (sample plane w h (inc x) y) (half-h plane w h x y))
    (and (zero? fx) (= fy 1)) (avg1 (sample plane w h x y) (half-v plane w h x y))
    (and (zero? fx) (= fy 3)) (avg1 (sample plane w h x (inc y)) (half-v plane w h x y))
    (and (= fx 1) (= fy 2)) (avg1 (half-v plane w h x y) (center-j plane w h x y))
    (and (= fx 3) (= fy 2)) (avg1 (center-j plane w h x y) (half-v plane w h (inc x) y))
    (and (= fx 2) (= fy 1)) (avg1 (half-h plane w h x y) (center-j plane w h x y))
    (and (= fx 2) (= fy 3)) (avg1 (center-j plane w h x y) (half-h plane w h x (inc y)))
    (and (= fx 1) (= fy 1)) (avg1 (half-h plane w h x y) (half-v plane w h x y))
    (and (= fx 3) (= fy 1)) (avg1 (half-h plane w h x y) (half-v plane w h (inc x) y))
    (and (= fx 1) (= fy 3)) (avg1 (half-v plane w h x y) (half-h plane w h x (inc y)))
    (and (= fx 3) (= fy 3)) (avg1 (half-v plane w h (inc x) y) (half-h plane w h x (inc y)))
    :else (throw (ex-info "h264.interp: invalid luma quarter-pel fraction (must be 0..3)" {:fx fx :fy fy}))))

(defn eighth-pel-chroma
  "One interpolated chroma sample (§8.4.2.2.2) — bilinear, NOT 6-tap — at
   full-pel base position (x,y) with eighth-sample offset (fx,fy), each
   0..7 (0 = the integer sample itself)."
  [plane w h x y fx fy]
  (let [a (* (- 8 fx) (- 8 fy))
        b (* fx (- 8 fy))
        c (* (- 8 fx) fy)
        d (* fx fy)
        p00 (sample plane w h x y)
        p01 (sample plane w h (inc x) y)
        p10 (sample plane w h x (inc y))
        p11 (sample plane w h (inc x) (inc y))]
    (clip8 (bit-shift-right (+ (* a p00) (* b p01) (* c p10) (* d p11) 32) 6))))

;; --- shared half-sample planes for a sub-pel search ---------------------
;;
;; `h264.encode/me-subpel-refine` evaluates 49 candidate vectors (+/-3 quarter
;; samples in each direction) around one integer vector, and measured by
;; caller attribution it was **~61% of a whole P-frame encode** — more than
;; the integer search, the residual coding and the final reconstruction put
;; together (`com-junkawasaki/root` ADR-2800002800).
;;
;; All 49 candidates read the SAME small integer neighbourhood: a quarter
;; offset of -3..+3 around a multiple of 4 lands on integer position `ix-1` or
;; `ix`, so the candidates' blocks span `size+1` integer positions, `size+2`
;; once the tables' own +1 reach is included. Every one of the 16 quarter-sample
;; positions is then either an integer sample or a rounded average of two of
;; three half-sample values at that neighbourhood (§8.4.2.2.1 Figure 8-4, which
;; is what `luma-at`'s table below says).
;;
;; So the three half-sample planes are computed ONCE per search instead of
;; being re-filtered per candidate per pixel. The horizontal 6-tap sums are
;; shared twice over: `half-h` is a rounding of them, and `center-j` is the
;; vertical 6-tap OVER them — which is also the two-pass form FFmpeg's
;; `h264_qpel_hv_lowpass` uses and that `center-j`'s note above describes.
;;
;; Reads of the reference plane, per macroblock, for the whole sub-pel stage:
;; **529**, against ~231,000 before (49 candidates x 256 pixels x an average of
;; 18.4 filter taps). Bit-identical: same formulas, same operand order, same
;; intermediate widths, evaluated once rather than repeatedly. Contrast the
;; support window that was tried and reverted (see the namespace docstring):
;; that relocated reads, this removes them.

(defn- window-idx [ww x y] (+ (* y ww) x))

(defn subpel-planes
  "Precompute the integer samples and the three half-sample planes covering
   every position a sub-pel search around `(x0,y0)` can read: a
   `(size+2)`-square region whose top-left is `(x0-1, y0-1)`.

   Returns `{:s :b :h :j :n :ox :oy}` — flat `n`-square arrays of the integer
   sample, half-h ('b'), half-v ('h') and centre 'j' values, with `:ox`/`:oy`
   the picture coordinate of the region's top-left. `quarter-pel-from-planes`
   reads them.

   `plane` must be an ARRAY (`plane->array`), not a vector — this is the one
   entry point in this namespace with that requirement, because it is the only
   one motion estimation calls per macroblock and therefore the only one where
   the representation shows up in the profile."
  [plane w h x0 y0 size]
  (let [n (+ size 2)
        ox (dec x0) oy (dec y0)
        ;; integer samples, extended by the 6-tap's -2/+3 reach on both axes
        sw (+ n 5) sox (- ox 2) soy (- oy 2)
        ^ints s-ext (new-window (* sw sw))
        _ (dotimes [yy sw]
            (let [row (* yy sw) py (+ soy yy)]
              (dotimes [xx sw]
                (aset s-ext (+ row xx) (int (sample-arr plane w h (+ sox xx) py))))))
        se (fn [x y] (aget s-ext (window-idx sw (- x sox) (- y soy))))
        ;; unrounded horizontal 6-tap sums, n wide by (n+5) tall — reused by
        ;; BOTH half-h (a rounding of them) and centre-j (a vertical 6-tap over
        ;; them), which is where most of the saving comes from
        hh (+ n 5) hoy (- oy 2)
        ^ints hs (new-window (* n hh))
        _ (dotimes [yy hh]
            (let [row (* yy n) py (+ hoy yy)]
              (dotimes [xx n]
                (let [px (+ ox xx)]
                  (aset hs (+ row xx)
                        (int (+ (* 20 (+ (se px py) (se (inc px) py)))
                                (* -5 (+ (se (dec px) py) (se (+ px 2) py)))
                                (se (- px 2) py)
                                (se (+ px 3) py))))))))
        hsat (fn [xx y] (aget hs (+ (* (- y hoy) n) xx)))
        ^ints s (new-window (* n n))
        ^ints b (new-window (* n n))
        ^ints hv (new-window (* n n))
        ^ints j (new-window (* n n))]
    (dotimes [yy n]
      (let [row (* yy n) py (+ oy yy)]
        (dotimes [xx n]
          (let [px (+ ox xx) i (+ row xx)]
            (aset s i (int (se px py)))
            (aset b i (int (clip8 (bit-shift-right (+ (hsat xx py) 16) 5))))
            (aset hv i (int (clip8 (bit-shift-right
                                    (+ (* 20 (+ (se px py) (se px (inc py))))
                                       (* -5 (+ (se px (dec py)) (se px (+ py 2))))
                                       (se px (- py 2))
                                       (se px (+ py 3))
                                       16)
                                    5))))
            (aset j i (int (clip8 (bit-shift-right
                                   (+ (* 20 (+ (hsat xx py) (hsat xx (inc py))))
                                      (* -5 (+ (hsat xx (dec py)) (hsat xx (+ py 2))))
                                      (hsat xx (- py 2))
                                      (hsat xx (+ py 3))
                                      512)
                                   10))))))))
    {:s s :b b :h hv :j j :n n :ox ox :oy oy}))

(defn subpel-selector
  "Resolve a quarter-sample fraction `(fx,fy)` into the plane lookups that
   produce it, ONCE, so a caller evaluating a whole block does not re-decide it
   per pixel: `{:a array :ao offset :b array-or-nil :bo offset}`, meaning
   `avg1(a[i+ao], b[i+bo])`, or just `a[i+ao]` when `:b` is nil, where `i` is
   the region index of the pixel.

   Every one of §8.4.2.2.1 Figure 8-4's sixteen positions has exactly this
   shape — an integer sample or a half-sample, or the rounded average of two of
   them — with the only variation being WHICH plane and whether the second
   operand comes from one column right (`+1`) or one row down (`+n`). Selecting
   it once turns the per-pixel sixteen-way `cond` into two array reads.

   Measured: after `subpel-planes` removed the plane reads from the sub-pel
   search, that `cond` was what remained (49 candidates x 256 pixels per
   macroblock, each walking up to sixteen tests)."
  [{:keys [s b h j n]} fx fy]
  (let [pair (fn [a ao bb bo] {:a a :ao ao :b bb :bo bo})
        one (fn [a] {:a a :ao 0 :b nil :bo 0})
        right 1
        down n]
    (cond
      (and (zero? fx) (zero? fy)) (one s)
      (and (= fx 2) (zero? fy)) (one b)
      (and (zero? fx) (= fy 2)) (one h)
      (and (= fx 2) (= fy 2)) (one j)
      (and (= fx 1) (zero? fy)) (pair s 0 b 0)
      (and (= fx 3) (zero? fy)) (pair s right b 0)
      (and (zero? fx) (= fy 1)) (pair s 0 h 0)
      (and (zero? fx) (= fy 3)) (pair s down h 0)
      (and (= fx 1) (= fy 2)) (pair h 0 j 0)
      (and (= fx 3) (= fy 2)) (pair j 0 h right)
      (and (= fx 2) (= fy 1)) (pair b 0 j 0)
      (and (= fx 2) (= fy 3)) (pair j 0 b down)
      (and (= fx 1) (= fy 1)) (pair b 0 h 0)
      (and (= fx 3) (= fy 1)) (pair b 0 h right)
      (and (= fx 1) (= fy 3)) (pair h 0 b down)
      (and (= fx 3) (= fy 3)) (pair h right b down)
      :else (throw (ex-info "h264.interp: invalid luma quarter-pel fraction (must be 0..3)"
                             {:fx fx :fy fy})))))

(defn quarter-pel-from-planes
  "`quarter-pel-luma` for a position inside a `subpel-planes` region, at
   region-relative `(x,y)`. Convenience form — it resolves the fraction per
   call, so a caller doing a whole block should hoist `subpel-selector` out of
   its loop instead (`h264.encode/sad-mc-planes` does)."
  [planes x y fx fy]
  (let [{:keys [a ao b bo]} (subpel-selector planes fx fy)
        i (window-idx (:n planes) x y)
        ^ints a a]
    (if (nil? b)
      (aget a (+ i ao))
      (let [^ints b b] (avg1 (aget a (+ i ao)) (aget b (+ i bo)))))))

(defn mc-luma-block
  "Motion-compensated `size`x`size` luma block from reference `plane`
   (dimensions `w`x`h`) at zero-motion top-left picture position (x0,y0)
   with motion vector `[mvx mvy]` (quarter-luma-sample units, §8.4.1).
   Returns a `size`x`size` row-vector grid (row-major, `[row][col]`).

   Full-pel/fractional split follows the spec's `>>`/`&` convention exactly
   (arithmetic right shift = floor division, matching two's-complement
   semantics both C and the JVM already use — `mvx & 3` is always 0..3
   even for negative `mvx`, no separate negative-number handling needed)."
  [plane w h x0 y0 [mvx mvy] size]
  (let [ix (bit-shift-right mvx 2) fx (bit-and mvx 3)
        iy (bit-shift-right mvy 2) fy (bit-and mvy 3)
        bx (+ x0 ix) by (+ y0 iy)]
    (vec (for [ry (range size)]
           (vec (for [rx (range size)]
                  (quarter-pel-luma plane w h (+ bx rx) (+ by ry) fx fy)))))))

(defn mc-chroma-block
  "Motion-compensated `size`x`size` chroma block from reference `plane`
   (chroma-plane dimensions `w`x`h`) at zero-motion top-left CHROMA-plane
   position (x0,y0) with the LUMA motion vector `[mvx mvy]` (quarter-luma-
   sample units). Returns a `size`x`size` row-vector grid.

   For ChromaArrayType 1 (4:2:0, this repo's only supported chroma format),
   §8.4.1.4 derives the chroma motion vector as `mvCLX == mvLX` — no
   scaling — because chroma sample spacing is exactly 2x luma sample
   spacing, which exactly cancels the 2x difference between luma's
   quarter-sample motion-vector unit and chroma's eighth-sample unit (a
   displacement of `mvx` quarter-LUMA-samples = `mvx/4` luma samples =
   `mvx/8` chroma samples = `mvx` eighth-CHROMA-samples — the same integer).
   So `mvx`/`mvy` here are the SAME values passed to `mc-luma-block`,
   reinterpreted as eighth-chroma-sample units directly (`>> 3`/`& 7`
   instead of luma's `>> 2`/`& 3`)."
  [plane w h x0 y0 [mvx mvy] size]
  (let [ix (bit-shift-right mvx 3) fx (bit-and mvx 7)
        iy (bit-shift-right mvy 3) fy (bit-and mvy 7)
        bx (+ x0 ix) by (+ y0 iy)]
    (vec (for [ry (range size)]
           (vec (for [rx (range size)]
                  (eighth-pel-chroma plane w h (+ bx rx) (+ by ry) fx fy)))))))
