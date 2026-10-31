(ns kami.eizo.compositor.blend
  "Standard compositing blend modes. Each blend fn takes `top` and
  `bottom` pixels ([r g b], channels in [0,1]) and returns the raw
  blended pixel (opacity is NOT applied inside the blend fn — use
  `composite` to mix the blended result over `bottom` by `opacity`,
  matching how every NLE/compositor separates \"blend mode\" from
  \"layer opacity\").")

(defn- clamp01 [x] (max 0.0 (min 1.0 x)))
(defn- per-channel [f a b] (mapv f a b))

(defn multiply [top bottom] (per-channel * top bottom))
(defn screen [top bottom] (per-channel (fn [t b] (- 1.0 (* (- 1.0 t) (- 1.0 b)))) top bottom))
(defn add [top bottom] (per-channel (fn [t b] (clamp01 (+ t b))) top bottom))

(def blend-modes
  {:normal   (fn [top _bottom] top)
   :multiply multiply
   :screen   screen
   :add      add})

(defn composite
  "Composites `top` over `bottom` using `mode` (one of :normal
  :multiply :screen :add) and `opacity` (0-1): result = bottom*(1-opacity)
  + blend(top,bottom)*opacity — the standard blend-mode-then-opacity-mix
  formula used by every layer-based compositor."
  [mode top bottom opacity]
  (let [blend-fn (get blend-modes mode)]
    (when-not blend-fn (throw (ex-info "unknown blend mode" {:mode mode})))
    (let [blended (blend-fn top bottom)]
      (mapv (fn [bl bo] (+ (* bo (- 1.0 opacity)) (* bl opacity))) blended bottom))))
