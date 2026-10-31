(ns kami.eizo.grade.scope
  "Waveform/vectorscope *data* computation — not rendering. A frame is
   represented for v0 as a flat sequence of [r g b] pixel triples (no
   image decode/spatial layout; that is out of scope). Luma and the
   YCbCr chroma-plane transform both use Rec. 709 coefficients, matching
   `kami.eizo.grade.cdl`'s luma choice for consistency across the repo.")

(def ^:const rec709-luma [0.2126 0.7152 0.0722])

(defn luma [[r g b]]
  (let [[lr lg lb] rec709-luma]
    (+ (* r lr) (* g lg) (* b lb))))

(defn rgb->ycbcr
  "Rec. 709 full-range YCbCr. Cb/Cr are in [-0.5, 0.5] for [0,1] RGB
   input (standard normalized chroma-plane range for a vectorscope)."
  [[r _g b :as rgb]]
  (let [y (luma rgb)]
    [y (/ (- b y) 1.8556) (/ (- r y) 1.5748)]))

(defn waveform
  "Luma histogram over `n-buckets` equal-width buckets across [0,1].
   Returns a vector of `n-buckets` counts. This is a value-distribution
   simplification of a real waveform monitor (which also preserves
   horizontal pixel position); documented as a v0 simplification."
  [pixels n-buckets]
  (let [counts (atom (vec (repeat n-buckets 0)))]
    (doseq [px pixels]
      (let [y (max 0.0 (min 0.999999 (luma px)))
            bucket (int (* y n-buckets))]
        (swap! counts update bucket inc)))
    @counts))

(defn vectorscope
  "Chroma-vector distribution: returns a seq of [cb cr] pairs, one per
   input pixel, via `rgb->ycbcr`. Downstream rendering would histogram
   or plot these; that is out of scope here."
  [pixels]
  (mapv (fn [px] (let [[_ cb cr] (rgb->ycbcr px)] [cb cr])) pixels))
