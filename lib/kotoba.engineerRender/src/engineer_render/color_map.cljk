(ns engineer-render.color-map
  "FEA post-processing color maps: normalized value [0,1] -> RGBA. Restored
  from kami-eng-render's `ColorMap` enum + `sample`/`hsv_to_rgb` (kami-engine/
  kami-eng-render/src/lib.rs, deleted PR #82).")

(def kinds #{:rainbow :jet :viridis :coolwarm :grayscale})

(defn- clamp01 [x] (max 0.0 (min 1.0 x)))

(defn- hsv->rgb [h s v]
  (let [c (* v s)
        x (* c (- 1.0 (Math/abs (- (mod (/ h 60.0) 2.0) 1.0))))
        m (- v c)
        [r g b] (cond
                   (< h 60.0)  [c x 0.0]
                   (< h 120.0) [x c 0.0]
                   (< h 180.0) [0.0 c x]
                   (< h 240.0) [0.0 x c]
                   (< h 300.0) [x 0.0 c]
                   :else       [c 0.0 x])]
    [(+ r m) (+ g m) (+ b m)]))

(defn sample
  "Map normalized value `t` (clamped to [0,1]) through `kind` (one of
  `kinds`) to an `[r g b a]` color."
  [kind t]
  (let [t (clamp01 t)]
    (case kind
      :jet (let [r (clamp01 (- 1.5 (Math/abs (- (* t 4.0) 3.0))))
                 g (clamp01 (- 1.5 (Math/abs (- (* t 4.0) 2.0))))
                 b (clamp01 (- 1.5 (Math/abs (- (* t 4.0) 1.0))))]
             [r g b 1.0])
      :coolwarm (let [r (clamp01 (+ 0.5 (* t 0.5)))
                      b (clamp01 (- 1.0 (* t 0.5)))
                      g (- 1.0 (Math/abs (- (* 2.0 t) 1.0)))]
                  [r g b 1.0])
      :viridis (let [r (min 1.0 (+ 0.267 (* t 0.726)))
                     g (min 1.0 (+ 0.004 (* t 0.870)))
                     b (min 1.0 (+ 0.329 (* (- 1.0 t) 0.341)))]
                 [r g b 1.0])
      :grayscale [t t t 1.0]
      :rainbow (let [h (* (- 1.0 t) 270.0)
                     [r g b] (hsv->rgb h 1.0 1.0)]
                 [r g b 1.0]))))
