(ns kami.eizo.compositor.chroma-key
  "Chroma-key alpha (matte) computation.

  Standard distance-from-key-color keying with a soft threshold
  falloff (the same shape of formula used by common shader-based
  chroma-key implementations): pixels within `tolerance` of the key
  color in normalized RGB space are fully transparent (alpha 0),
  pixels beyond `tolerance + softness` are fully opaque (alpha 1),
  and the band between smoothsteps.")

(defn- clamp01 [x] (max 0.0 (min 1.0 x)))

(defn- smoothstep [edge0 edge1 x]
  (if (== edge0 edge1)
    (if (< x edge0) 0.0 1.0)
    (let [t (clamp01 (/ (- x edge0) (- edge1 edge0)))]
      (* t t (- 3.0 (* 2.0 t))))))

(defn rgb-distance
  "Euclidean distance between two [r g b] triples (each channel in
  [0,1]), normalized to [0,1] by dividing by sqrt(3) (the max possible
  distance between two points in the unit RGB cube)."
  [[r1 g1 b1] [r2 g2 b2]]
  (/ (Math/sqrt (+ (Math/pow (- r1 r2) 2)
                   (Math/pow (- g1 g2) 2)
                   (Math/pow (- b1 b2) 2)))
     (Math/sqrt 3)))

(defn key-alpha
  "Computes the alpha/matte value for `pixel` ([r g b], each channel
  in [0,1]) given a chroma-key configuration:
    :key-color [r g b]
    :tolerance   distance below which the pixel is fully keyed out (alpha 0)
    :softness    additional distance over which alpha ramps 0 -> 1

  Returns alpha in [0,1] where 0 = fully transparent (keyed out),
  1 = fully opaque (kept)."
  [pixel {:keys [key-color tolerance softness]
          :or {tolerance 0.1 softness 0.1}}]
  (let [d (rgb-distance pixel key-color)]
    (smoothstep tolerance (+ tolerance softness) d)))
