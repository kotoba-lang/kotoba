(ns aac.imdct
  "AAC-LC filterbank: IMDCT + windowing + 50% overlap-add, for ALL FOUR
   `window_sequence` values (ISO/IEC 14496-3:2005 §4.6.11 \"Filterbank and
   block switching\") — `ONLY_LONG_SEQUENCE` (0), `LONG_START_SEQUENCE` (1),
   `EIGHT_SHORT_SEQUENCE` (2) and `LONG_STOP_SEQUENCE` (3). Long sequences
   run one 2048-point IMDCT; `EIGHT_SHORT_SEQUENCE` runs eight 256-point
   IMDCTs whose windowed outputs are overlap-added among themselves at a
   128-sample hop before the frame's own overlap-add with its predecessor.

   ## IMDCT (§4.6.11.3.1, verbatim)

     x[i,n] = (2/N) * sum_{k=0}^{N/2-1} spec[i][k] * cos((2*pi/N)*(n+n0)*(k+0.5))
     n0 = (N/2 + 1) / 2

   N = 2048 for the long transform, 256 for each short one. This is a
   direct O(N^2) evaluation, not an FFT-accelerated one, since this repo
   decodes at most tens of frames in its test fixtures (performance is not
   a scope goal; see `aac.decode`'s namespace docstring). It IS folded onto
   the transform's own symmetry, which is exact algebra rather than an
   approximation — see `imdct` below and `aac.mdct-test`'s
   `imdct-fold-matches-reference`, which pins the folded evaluation against
   the literal formula (`imdct-reference`) so the fold cannot silently
   diverge from the spec text it is derived from.

   ## Sine window (§4.6.11.3.2, verbatim, window_shape == 0)

     W_SIN(n) = sin((pi/N) * (n + 0.5))

   with N = 2048 for the long window and 256 for the short one (so the
   half-length arrays this namespace stores are 1024 and 128 entries).

   Independently verified (development-time, not part of the committed
   test suite) against `kotoba-lang/org-iso-h264`'s sibling-repo precedent
   of cross-checking transcribed spec formulas against a real decoder's own
   numeric tables: this exact sine formula, evaluated at n=0..1023,
   reproduces FAAD2's (github.com/knik0/faad2) `sine_long_1024` table to
   full double precision, and at n=0..127 its `sine_short_128` table.

   ## Kaiser-Bessel Derived (KBD) window (§4.6.11.3.2, window_shape == 1)

   The ISO spec's own OCR'd formula for the KBD kernel W'(n,alpha)
   (a closed-form Kaiser window over an I0 Bessel ratio) could not be
   reconstructed unambiguously from the fetched spec text — the PDF's
   equation rendering for this one formula is genuinely garbled (nested
   fraction glyphs overlap in extraction) in a way the surrounding syntax
   tables and other formulas (IMDCT, sine window, dequantization, Huffman
   tables — all independently verified above) were not. Rather than guess
   at a fix and risk an unverifiable, hard-to-catch numeric error, this
   implementation uses the well-known ITERATIVE Kaiser-window construction
   documented independently by FFmpeg's `libavcodec/kbdwin.c`
   (`ff_kbd_window_init`, LGPL — only the ALGORITHM/formula was consulted
   and reimplemented from scratch here, no source text or data copied;
   see `aac.huffman`'s namespace docstring for this repo's general
   copy-vs-reimplement policy) and cross-verified independently: this
   from-scratch reimplementation's output for alpha=4.0, n=1024 matches
   BOTH FFmpeg's algorithm's own expected output AND FAAD2's independently
   precomputed `kbd_long_1024` table to ~3e-9 absolute error (float
   round-off) at every one of a spot-checked set of indices spanning the
   full window (0, 1, 100, 500, 512, 900, 1023) — i.e. two independently-
   developed real AAC decoders agree with this formula to double-precision
   floating point, which is about as strong a correctness signal as is
   available without the spec text itself resolving cleanly.

     alpha2 = 4 * (alpha*pi/n)^2                       (n = 1024, alpha = 4.0)
     kernel[i] = I0(sqrt(i*(n-i)*alpha2)),              i = 0..n/2
     scale = 1 / (1 + kernel[0] + kernel[n/2] + 2*sum(kernel[1..n/2-1]))
     window[i] = sqrt(scale * running-cumulative-sum-of-kernel), i=0..n-1
       (cumulative sum runs forward over kernel[0..n/2] for i=0..n/2, then
        continues by re-adding kernel[n-i] for i=n/2+1..n-1 — kernel[] is
        symmetric so this mirrors the first half without recomputing I0)

   The SHORT KBD window uses the same construction with half-length n=128
   and **alpha = 6.0**, not 4.0 (§4.6.11.3.2's window_shape table gives a
   different shape parameter per transform length; FFmpeg's
   `ff_kbd_window_init(ff_aac_kbd_short_128, 6.0, 128)` is the same pair).
   Getting this constant wrong would not throw — it would produce a window
   that still sums to a valid-looking envelope but violates the
   Princen-Bradley condition against its neighbours, so it is called out
   here explicitly.

   ## Windowing and block switching (§4.6.11.3.2)

   Every sequence produces the same shaped result: a 2048-sample windowed
   block `z`, of which the first 1024 samples are added to the previous
   frame's saved second half to make this frame's PCM output, and the
   second 1024 are saved for the next frame (`decode-frame` below). What
   differs is only how `z` is shaped:

     ONLY_LONG    z[n]      = x[n] * W_LEFT_LONG[n]              0    <= n < 1024
                  z[n]      = x[n] * W_RIGHT_LONG[n-1024]        1024 <= n < 2048

     LONG_START   z[n]      = x[n] * W_LEFT_LONG[n]              0    <= n < 1024
                  z[n]      = x[n]                               1024 <= n < 1472
                  z[n]      = x[n] * W_RIGHT_SHORT[n-1472]       1472 <= n < 1600
                  z[n]      = 0                                  1600 <= n < 2048

     LONG_STOP    z[n]      = 0                                  0    <= n < 448
                  z[n]      = x[n] * W_LEFT_SHORT[n-448]         448  <= n < 576
                  z[n]      = x[n]                               576  <= n < 1024
                  z[n]      = x[n] * W_RIGHT_LONG[n-1024]        1024 <= n < 2048

     EIGHT_SHORT  eight 256-sample transforms x_j (j = 0..7), each windowed

                  zj[m]     = xj[m] * W_LEFT_SHORT[m]            0    <= m < 128
                  zj[m]     = xj[m] * W_RIGHT_SHORT[m-128]       128  <= m < 256

                  and summed into z at offset 448 + 128*j (so the eight
                  blocks span [448,1600) and z is zero outside that range —
                  448 = (2048 - 8*128 - 128)/2).

   `W_LEFT_*` is the RISING half of the window built with the PREVIOUS
   block's `window_shape`; `W_RIGHT_*` is the FALLING half (the same array
   read backwards) built with THIS block's `window_shape`. The one
   exception, and it matters: under EIGHT_SHORT only the FIRST short block
   (j = 0) takes its rising half from the previous block's shape — blocks
   1..7 overlap each other inside this frame, so both of their halves come
   from this frame's own `window_shape` (cross-checked against FFmpeg's
   `imdct_and_windowing` in `libavcodec/aac/aacdec_*`, which passes
   `swindow_prev` only to the `saved`-to-block-0 butterfly and `swindow`
   to the other seven; algorithm only consulted, not copied — same policy
   as the KBD window above).

   The transition shapes are what make block switching work at all: a
   LONG_START's flat-then-short-falling right half is exactly the
   time-reverse of the following EIGHT_SHORT's zero-then-short-rising left
   half, so time-domain alias cancellation still holds across a window-size
   change. Frame-level continuity therefore constrains which sequences may
   follow which; this namespace does not enforce that (a stream whose
   encoder emitted an illegal transition decodes to whatever those windows
   produce rather than throwing), because the constraint is on the encoder
   and a decoder that refuses is less useful than one that reproduces the
   reference decoder's output."
  )

(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))
(defn- sqrt- [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))
(defn- pow- [x y] #?(:clj (Math/pow x y) :cljs (js/Math.pow x y)))
(defn- sin- [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn- cos- [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))

(defn- i0
  "Modified Bessel function of the first kind, order 0 — power series
   sum_k ((x^2/4)^k / (k!)^2), 40 terms (converges to double-precision for
   the |x| range this window construction needs, x up to ~pi*alpha*~1)."
  [x]
  (let [x2-4 (/ (* x x) 4.0)]
    (loop [k 0 term 1.0 sum 0.0]
      (if (>= k 40)
        sum
        (let [term' (if (zero? k) term (/ (* term x2-4) (* k k)))]
          (recur (inc k) term' (+ sum term')))))))

(defn kbd-window
  "Kaiser-Bessel Derived window, half-length `n` (1024 for the AAC-LC long
   window, 128 for the short one), shape parameter `alpha` (4.0 long /
   6.0 short, §4.6.11.3.2). Returns an `n`-length vector — see namespace
   docstring for the construction and its independent cross-verification
   against FAAD2/FFmpeg."
  [n alpha]
  (let [alpha2 (* 4.0 (pow- (/ (* alpha pi) n) 2))
        half (quot n 2)
        kernel (mapv (fn [i] (i0 (sqrt- (* i (- n i) alpha2)))) (range (inc half)))
        scale-sum (loop [i 0 s 0.0]
                    (if (> i half)
                      s
                      (recur (inc i) (+ s (* (nth kernel i) (if (and (pos? i) (< i half)) 2 1))))))
        scale (/ 1.0 (+ scale-sum 1.0))]
    (loop [i 0 running 0.0 out (transient (vec (repeat n 0.0)))]
      (if (>= i n)
        (persistent! out)
        (let [term (if (<= i half) (nth kernel i) (nth kernel (- n i)))
              running' (+ running term)]
          (recur (inc i) running' (assoc! out i (sqrt- (* running' scale)))))))))

(defn sine-window
  "Sine window, half-length `n` (1024 long / 128 short): sin(pi/(2n) *
   (i + 0.5)), i = 0..n-1 (verified against FAAD2's `sine_long_1024` /
   `sine_short_128` — see namespace docstring)."
  [n]
  (mapv (fn [i] (sin- (* (/ pi (* 2.0 n)) (+ i 0.5)))) (range n)))

(def ^:private sine-window-1024 (delay (sine-window 1024)))
(def ^:private kbd-window-1024 (delay (kbd-window 1024 4.0)))
(def ^:private sine-window-128 (delay (sine-window 128)))
(def ^:private kbd-window-128 (delay (kbd-window 128 6.0)))

(defn half-window
  "The half-length (1024) LONG window array for `window-shape` (0 = sine,
   1 = KBD), per §4.6.11.3.2 window_shape."
  [window-shape]
  (case window-shape
    0 @sine-window-1024
    1 @kbd-window-1024
    (throw (ex-info "aac.imdct: window_shape must be 0 or 1" {:window-shape window-shape}))))

(defn short-half-window
  "The half-length (128) SHORT window array for `window-shape` (0 = sine,
   1 = KBD with alpha 6.0 — see namespace docstring), used by
   EIGHT_SHORT_SEQUENCE and by LONG_START/LONG_STOP's transition halves."
  [window-shape]
  (case window-shape
    0 @sine-window-128
    1 @kbd-window-128
    (throw (ex-info "aac.imdct: window_shape must be 0 or 1" {:window-shape window-shape}))))

;; --- IMDCT --------------------------------------------------------------

(def ^:private long-transform-length 2048)
(def ^:private short-transform-length 256)

(defn imdct-reference
  "The §4.6.11.3.1 IMDCT written out literally, one `cos` call per (n,k)
   pair: `n` time samples from `n`/2 spectral coefficients. Kept as the
   reference `imdct` is pinned against (`aac.mdct-test`'s
   `imdct-fold-matches-reference`) rather than as the decode path, because
   at N=2048 it evaluates 2 million cosines per frame per channel."
  [spec n]
  (let [two-pi-over-n (/ (* 2.0 pi) n)
        n0 (/ (+ (/ n 2.0) 1) 2.0)]
    (mapv (fn [out-n]
            (let [angle-base (* two-pi-over-n (+ out-n n0))]
              (* (/ 2.0 n)
                 (reduce + (map-indexed (fn [k sk] (* sk (cos- (* angle-base (+ k 0.5))))) spec)))))
          (range n))))

;; The cosine kernel cos((2*pi/N)*c*(k+0.5)), c = n + n0, is even in `c`,
;; has period 2N in `c`, and negates under c -> N - c:
;;
;;   cos((2pi/N)(2N-c)(k+.5)) = cos(2pi(2k+1) - theta) =  cos(theta)
;;   cos((2pi/N)( N-c)(k+.5)) = cos( pi(2k+1) - theta) = -cos(theta)
;;
;; so every one of the N output indices folds onto one of just N/2 distinct
;; rows (c reduced into [0, N/2], where it is always a half-integer because
;; n0 is) with a sign. `imdct` evaluates those N/2 rows once each and then
;; reads the N outputs off them.
;;
;; Each row is a dot product against the spectrum whose cosine argument, for
;; reduced c = j + 0.5, is
;;
;;   (2pi/N)*(j+0.5)*(k+0.5) = 2*pi * (2j+1)*(2k+1) / (4N)
;;
;; i.e. always an integer multiple of 2*pi/(4N) — so ONE table of 4N cosines
;; serves every (j,k) pair, indexed by (2j+1)*(2k+1) mod 4N, which advances
;; by a constant 2*(2j+1) as k increments. That is the whole optimization:
;; 8192 cosines for the long transform instead of 2 million, and an inner
;; loop of one table read, one multiply-add and one conditional subtract.
;;
;; Both steps are exact algebra on the spec formula, not approximations. The
;; two agree to floating-point round-off, which `aac.mdct-test`'s
;; `imdct-fold-matches-reference` asserts against `imdct-reference` directly.

(defn- cos-quarter-table
  "cos(2*pi*m / (4N)) for m in [0, 4N) — every distinct cosine the IMDCT of
   length `n` can need (see the comment above)."
  [n]
  (let [period (* 4 n)
        a (double-array period)]
    (dotimes [m period]
      (aset ^doubles a m (double (cos- (/ (* 2.0 pi m) period)))))
    a))

(defn- fold-map
  "For each of the N output indices, which reduced row `j` it folds onto and
   with what sign. Returns [rows signs] (an int array and a double array)."
  [n]
  (let [half (quot n 2)
        n0 (/ (+ half 1) 2.0)
        rows (int-array n)
        signs (double-array n)]
    (dotimes [i n]
      (let [c (+ i n0)
            c (if (> c n) (- (* 2 n) c) c)
            neg? (> c half)
            c (if neg? (- n c) c)]
        (aset ^ints rows i (int (- c 0.5)))
        (aset ^doubles signs i (double (if neg? -1.0 1.0)))))
    [rows signs]))

(def ^:private kernels (atom {}))

(defn- kernel-for [n]
  (or (get @kernels n)
      (let [[rows signs] (fold-map n)
            k {:cos-tab (cos-quarter-table n) :rows rows :signs signs}]
        (swap! kernels assoc n k)
        k)))

(defn imdct
  "IMDCT of `n`/2 dequantized spectral coefficients `spec` -> `n` time-domain
   samples (§4.6.11.3.1). `n` is 2048 for the long transform, 256 for each
   of EIGHT_SHORT's eight. Symmetry-folded over a shared cosine table — see
   the comment above and `imdct-reference`, which this is pinned against."
  [spec n]
  (let [n (long n)
        half (long (quot n 2))
        _ (when-not (= half (count spec))
            (throw (ex-info "aac.imdct: spectrum length must be N/2"
                             {:n n :expected half :got (count spec)})))
        {:keys [cos-tab rows signs]} (kernel-for n)
        period (long (* 4 n))
        s (double-array spec)
        dots (double-array half)
        scale (/ 2.0 n)]
    (dotimes [j half]
      (let [odd (long (+ (* 2 j) 1))
            step (long (* 2 odd))]
        (aset ^doubles dots j
              (double
               (loop [k 0 m odd acc 0.0]
                 (if (= k half)
                   acc
                   (recur (inc k)
                          (let [m' (+ m step)] (if (>= m' period) (- m' period) m'))
                          (+ acc (* (aget ^doubles cos-tab m)
                                    (aget ^doubles s k))))))))))
    (mapv (fn [i] (* scale
                     (aget ^doubles signs i)
                     (aget ^doubles dots (aget ^ints rows i))))
          (range n))))

(defn imdct-long
  "IMDCT of 1024 dequantized spectral coefficients -> 2048 time-domain
   samples (the long transform, N = 2048)."
  [spec]
  (imdct spec long-transform-length))

;; --- windowing + overlap-add ---------------------------------------------

(def only-long-sequence 0)
(def long-start-sequence 1)
(def eight-short-sequence 2)
(def long-stop-sequence 3)

(def ^:private frame-length 1024)          ;; N/2 for the long transform
(def ^:private short-half 128)             ;; N/2 for a short transform

(def ^:private short-offset
  "Where the eight short blocks begin inside the 2048-sample block:
   (2048 - 8*128 - 128) / 2 = 448. Equivalently 2*448 + 128 = 1024, which is
   why the same number is also the length of LONG_START's and LONG_STOP's
   flat (unwindowed) regions — those are the parts of the long transform
   that lie outside the short blocks' reach on either side."
  448)

(def ^:private flat-length (- frame-length short-offset short-half)) ;; also 448

(defn- windowed-block
  "The 2048-sample windowed block `z` for one frame, per the table in the
   namespace docstring. `spec` is 1024 dequantized coefficients in TRANSFORM
   order — for EIGHT_SHORT_SEQUENCE that means the eight 128-line blocks
   laid end to end, already de-interleaved out of the bitstream's grouped
   order by `aac.ics/deinterleave-short-spectrum` (this namespace never sees
   window grouping; grouping is a noiseless-coding concern, §4.6.11.3.1's
   filterbank is not aware of it)."
  [spec window-sequence window-shape prev-window-shape]
  (let [z (double-array (* 2 frame-length) 0.0)
        sw-prev (short-half-window prev-window-shape)
        sw-cur (short-half-window window-shape)]
    (if (= window-sequence eight-short-sequence)
      (dotimes [j 8]
        (let [x (imdct (subvec spec (* short-half j) (* short-half (inc j))) short-transform-length)
              rising (if (zero? j) sw-prev sw-cur)
              base (+ short-offset (* short-half j))]
          (dotimes [m short-half]
            (let [i (+ base m)]
              (aset ^doubles z i (double (+ (aget ^doubles z i)
                                            (* (nth x m) (nth rising m)))))))
          (dotimes [m short-half]
            (let [i (+ base short-half m)]
              (aset ^doubles z i (double (+ (aget ^doubles z i)
                                            (* (nth x (+ short-half m))
                                               (nth sw-cur (- short-half 1 m))))))))))
      (let [x (imdct spec long-transform-length)
            lw-prev (half-window prev-window-shape)
            lw-cur (half-window window-shape)]
        ;; rising (first) half
        (if (= window-sequence long-stop-sequence)
          (do (dotimes [m short-half]
                (let [i (+ short-offset m)]
                  (aset ^doubles z i (double (* (nth x i) (nth sw-prev m))))))
              (dotimes [m flat-length]
                (let [i (+ short-offset short-half m)]
                  (aset ^doubles z i (double (nth x i))))))
          (dotimes [m frame-length]
            (aset ^doubles z m (double (* (nth x m) (nth lw-prev m))))))
        ;; falling (second) half
        (if (= window-sequence long-start-sequence)
          (do (dotimes [m short-offset]
                (let [i (+ frame-length m)]
                  (aset ^doubles z i (double (nth x i)))))
              (dotimes [m short-half]
                (let [i (+ frame-length short-offset m)]
                  (aset ^doubles z i (double (* (nth x i) (nth sw-cur (- short-half 1 m))))))))
          (dotimes [m frame-length]
            (let [i (+ frame-length m)]
              (aset ^doubles z i (double (* (nth x i) (nth lw-cur (- frame-length 1 m))))))))))
    (vec z)))

(defn decode-frame
  "One filterbank step (§4.6.11.3.1/4.6.11.3.2), any `window-sequence`:
   transform + window `spec` into the 2048-sample block `z` (see
   `windowed-block` and the namespace docstring's per-sequence table), then
   `out[n] = z[n] + z_prev[n+1024]` — i.e. add `prev-overlap` (the previous
   frame's saved second half, or `zero-overlap` for the first frame in a
   stream, §4.6.11.3.1's implicit zero history at stream start). `spec` is
   1024 dequantized coefficients in TRANSFORM order. `window-shape` is this
   frame's, `prev-window-shape` the previous frame's (it selects the RISING
   half's shape, and under EIGHT_SHORT only the first of the eight blocks').
   Returns {:pcm [1024 floats] :overlap [1024 floats]} — the latter is this
   frame's own second half, to feed as `prev-overlap` for the NEXT frame."
  [spec window-sequence window-shape prev-window-shape prev-overlap]
  (let [z (windowed-block spec window-sequence window-shape prev-window-shape)]
    {:pcm (mapv (fn [i] (+ (nth prev-overlap i) (nth z i))) (range frame-length))
     :overlap (subvec z frame-length)}))

(def zero-overlap
  "1024-length all-zero vector — the implicit overlap history for the first
   frame of a stream (§4.6.11.3.1)."
  (vec (repeat 1024 0.0)))
