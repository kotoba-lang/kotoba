(ns comfyui.diffusion.tiled-vae-deno
  "Bounded-memory overlapping VAE decode for Deno WebGPU hosts."
  (:require [num.array :as arr]
            [num.tensor :as t]))

(defn- tile-origins [size tile stride]
  (let [last-origin (- size tile)]
    (if (zero? last-origin)
      [0]
      (conj (vec (range 0 last-origin stride)) last-origin))))

(defn- tile-values [values channels height width origin-y origin-x tile]
  (vec
   (for [channel (range channels) y (range tile) x (range tile)]
     (nth values (+ (* channel height width)
                    (* (+ origin-y y) width) origin-x x)))))

(defn- edge-weight [coordinate origin tile size feather]
  (if (zero? feather)
    1.0
    (let [pixels tile
        leading (if (zero? origin) 1.0 (min 1.0 (/ (inc coordinate) feather)))
        trailing (if (= (+ origin pixels) size) 1.0
                     (min 1.0 (/ (- pixels coordinate) feather)))]
      (* leading trailing))))

(defn- blend-tile! [output weights values origin-y origin-x tile-pixels
                    output-height output-width feather]
  (dotimes [y tile-pixels]
    (dotimes [x tile-pixels]
      (let [weight (* (edge-weight y origin-y tile-pixels output-height feather)
                      (edge-weight x origin-x tile-pixels output-width feather))]
        (dotimes [channel 3]
          (let [source (+ (* y tile-pixels 3) (* x 3) channel)
                destination (+ (* (+ origin-y y) output-width 3)
                               (* (+ origin-x x) 3) channel)]
            (aset output destination
                  (+ (aget output destination) (* weight (nth values source))))
            (aset weights destination (+ (aget weights destination) weight))))))))

(defn- normalize! [output weights]
  (dotimes [index (.-length output)]
    (let [weight (aget weights index)]
      (when-not (pos? weight)
        (throw (ex-info "tiled VAE left an uncovered output pixel" {:index index})))
      (aset output index (/ (aget output index) weight)))))

(defn decode-tiled
  "Return Promise<NHWC image NDArray>. `latent` must be batch-one NCHW. Tile
  weights are shared through the compiled decoder cache; only bounded tile
  activations are live at once."
  ([decode latent] (decode-tiled decode latent {}))
  ([decode latent {:keys [tile-size overlap] :or {tile-size 8 overlap 2}}]
   (let [[batch channels height width] (:shape latent)
         _ (when-not (and (= batch 1) (pos-int? tile-size)
                          (<= tile-size height) (<= tile-size width)
                          (<= 0 overlap) (< overlap tile-size))
             (throw (ex-info "invalid tiled VAE input/options"
                             {:shape (:shape latent) :tile-size tile-size
                              :overlap overlap})))
         stride (- tile-size overlap)
         scale (reduce * 1 (map #(long (or (:scale-factor %) 2))
                                (filter #(= :upsample (:op %))
                                        (-> decode meta :comfyui/model-spec :layers))))
         tile-pixels (* tile-size scale)
         output-height (* height scale)
         output-width (* width scale)
         feather (* overlap scale)
         origins (for [y (tile-origins height tile-size stride)
                       x (tile-origins width tile-size stride)] [y x])
         output (js/Float32Array. (* output-height output-width 3))
         weights (js/Float32Array. (* output-height output-width 3))
         backend (:backend latent)
         decoder-dtype (or (-> decode meta :comfyui/dtype) :f32)]
     (-> (arr/->vec latent)
         (.then
          (fn [latent-values]
            (reduce
             (fn [promise [origin-y origin-x]]
               (.then
                promise
                (fn [_]
                  (let [tile-latent
                        (arr/from-vec backend
                                      (tile-values latent-values channels height width
                                                   origin-y origin-x tile-size)
                                      [1 channels tile-size tile-size] decoder-dtype)
                        decoded (decode tile-latent)
                        image (t/nchw-to-rgb-image decoded)]
                    (-> (arr/->vec image)
                        (.then
                         (fn [values]
                           (let [finite? (every? #(js/Number.isFinite %) values)]
                             (when finite?
                               (blend-tile! output weights values
                                            (* origin-y scale) (* origin-x scale)
                                            tile-pixels output-height output-width feather))
                             (arr/release-all! [tile-latent decoded image])
                             (when-not finite?
                               (throw (ex-info "VAE tile contains non-finite values"
                                               {:origin [origin-y origin-x]})))))))))))
             (js/Promise.resolve nil) origins)))
         (.then (fn [_]
                  (normalize! output weights)
                  (arr/from-vec backend (vec (js/Array.from output))
                                [1 output-height output-width 3])))))))
