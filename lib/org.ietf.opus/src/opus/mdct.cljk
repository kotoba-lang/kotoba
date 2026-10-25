(ns opus.mdct
  "Opus (IETF RFC 6716) CELT inverse MDCT and synthesis window -- RFC 6716
   Section 4.3.7 'Inverse MDCT'. Implements the transform via its direct
   mathematical definition (a standard, well-known TDAC inverse-MDCT sum)
   rather than the reference's N/4-complex-FFT trick: RFC 6716 explicitly
   normalizes on the *reference source* for bitstream-affecting choices
   (entropy coding, bit allocation, PVQ indexing) but the IMDCT is a plain
   linear transform where any mathematically-equivalent implementation is
   fine -- 'The inverse MDCT implementation has no special characteristics.'
   Pure cljc, zero dependencies.

   Scope: this repo's CELT decode covers a single, isolated frame (see
   opus.celt), so overlap-add always starts from a zero previous-frame
   tail -- the same 'cold start' condition a real decoder uses for the very
   first frame after a stream (re)start."
  )

(defn inverse-mdct
  "Inverse MDCT: N frequency-domain coefficients `x` (a vector of doubles)
   -> 2N time-domain samples, scaled by 1/2 per RFC 6716 SS4.3.7.
   out[m] = (1/2) * sum_{k=0}^{N-1} x[k] * cos( (pi/(2N)) * (2m+1+N) * (2k+1) ),
   for m = 0 .. 2N-1."
  [x]
  (let [n (count x)
        two-n (* 2 n)
        xv (vec x)]
    (mapv
     (fn [m]
       (* 0.5
          (reduce
           (fn [acc k]
             (+ acc (* (nth xv k)
                       (Math/cos (/ (* Math/PI (+ (* 2 m) 1 n) (+ (* 2 k) 1))
                                    (* 2.0 n))))))
           0.0
           (range n))))
     (range two-n))))

(defn window
  "CELT low-overlap synthesis window (RFC 6716 SS4.3.7): for a block of
   `total` time samples with overlap region `overlap` samples at each end,
   returns the length-`total` window vector. Derived from the basic
   (full-overlap) 2*overlap-sample Vorbis-style window
   W(n) = (sin(pi/2 * sin(pi/2 * (n+0.5)/overlap)))^2, with ones inserted in
   the flat middle section."
  [total overlap]
  (let [rise (fn [n]
               (let [s (Math/sin (/ (* Math/PI 0.5 (+ n 0.5)) overlap))
                     v (Math/sin (* Math/PI 0.5 s))]
                 (* v v)))]
    (mapv (fn [m]
            (cond
              (< m overlap) (rise m)
              (>= m (- total overlap)) (rise (- total 1 m))
              :else 1.0))
          (range total))))

(defn synthesize-frame
  "Windowed IMDCT + overlap-add for a single isolated frame (zero previous
   overlap memory, see namespace docstring): `freq` is the N frequency-domain
   band-domain coefficients (already denormalized by opus.celt), `overlap`
   is the window's transition length (CELT: mode overlap, `shortMdctSize`).
   Returns the N finished PCM samples for this frame."
  [freq overlap]
  (let [n   (count freq)
        raw (inverse-mdct freq)
        w   (window (* 2 n) overlap)]
    (vec (for [m (range n)] (* (nth raw m) (nth w m))))))
