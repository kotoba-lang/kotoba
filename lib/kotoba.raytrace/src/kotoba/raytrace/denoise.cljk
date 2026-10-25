(ns kotoba.raytrace.denoise
  "Edge-aware denoising for path-traced images: an a-trous wavelet filter with
  albedo, normal and depth edge stops, in the shape SVGF and Open Image Denoise
  use.

  A path tracer's output is the right answer plus variance, and the variance
  falls as 1/sqrt(samples) — so getting a clean image by sampling costs
  quadratically. A denoiser buys the same cleanliness by averaging neighbouring
  pixels instead, and the entire problem is that neighbouring pixels are only
  comparable where the SURFACE is comparable. Averaging across the silhouette
  of an object mixes two different surfaces and produces a clean image of
  something that is not there.

  Which is why the feature buffers are the subject and the blur is not. The
  filter is a plain 5-tap b-spline kernel applied at increasing strides; what
  makes it a denoiser rather than a blur is the weight

      w = exp(-|c_i - c_j|^2 / sigma_c^2 - |n_i - n_j|^2 / sigma_n^2 - ...)

  which collapses to zero across a discontinuity in albedo, normal or depth.
  Those buffers come from the renderer's first hit and carry no noise, so they
  can be trusted at full strength where the colour cannot.

  How this is checked, and it matters that it is not by eye: a ground-truth
  image is synthesised, noise of known variance is added, and the filter has to
  (1) reduce the RMSE against the truth, (2) beat a Gaussian of the same
  support, and (3) beat it BY MORE at the edges than in the flat regions —
  which is the only measurement that distinguishes an edge-aware filter from a
  well-tuned blur.

  One term is NOT covered by the suite: `:sigma-depth`. Removing the depth
  stop entirely leaves every test green, because no scene here has a
  depth-only discontinuity — the seams are all albedo or normal seams that
  depth happens to agree with. The albedo and normal terms each have a scene
  that isolates them and each fails when removed; depth does not, and saying
  so here is cheaper than letting twenty-two green tests imply otherwise.

  Not here: temporal accumulation and reprojection (the T in SVGF), variance
  estimation from per-pixel sample moments, firefly rejection, and any learned
  prior. This is the spatial half."
  (:require [kotoba.lang.text :as string]))

(defn- clampi [x lo hi] (max lo (min hi x)))
(defn- sq [x] (* x x))
(defn- exp [x] (#?(:clj Math/exp :cljs js/Math.exp) x))
(defn- sqrt [x] (#?(:clj Math/sqrt :cljs js/Math.sqrt) x))
(defn- log10 [x] (/ (#?(:clj Math/log :cljs js/Math.log) x)
                    (#?(:clj Math/log :cljs js/Math.log) 10.0)))

(def ^:private b3 [0.0625 0.25 0.375 0.25 0.0625])

(defn image
  "An image is a flat vector of `channels`-long vectors, row major."
  [width height pixels]
  {:image/width width :image/height height :image/channels (count (first pixels))
   :image/pixels (vec pixels)})

(defn at [{:keys [image/width image/pixels]} x y] (nth pixels (+ (* y width) x)))

(defn rmse
  "Root mean squared error between two images, over all channels."
  [a b]
  (let [pa (:image/pixels a) pb (:image/pixels b)
        n (* (count pa) (count (first pa)))]
    (sqrt (/ (reduce + (map (fn [p q] (reduce + (map #(sq (- %1 %2)) p q))) pa pb))
             (double n)))))

(defn psnr
  "Peak signal to noise ratio in dB, for images in [0, 1]."
  [a b]
  (let [e (rmse a b)]
    (if (zero? e) #?(:clj Double/POSITIVE_INFINITY :cljs js/Infinity)
        (* 20.0 (log10 (/ 1.0 e))))))

(defn- feature-weight
  [{:keys [colour albedo normal depth]} i j
   {:keys [sigma-colour sigma-albedo sigma-normal sigma-depth]}]
  (let [term (fn [buf sigma]
               (if (and buf (pos? sigma))
                 (/ (reduce + (map #(sq (- %1 %2))
                                   (nth (:image/pixels buf) i)
                                   (nth (:image/pixels buf) j)))
                    (sq sigma))
                 0.0))]
    (exp (- (+ (term colour sigma-colour)
               (term albedo sigma-albedo)
               (term normal sigma-normal)
               (term depth sigma-depth))))))

(defn- atrous-pass
  [{:keys [colour] :as buffers} stride sigmas]
  (let [{:keys [image/width image/height]} colour
        px (:image/pixels colour)
        chans (count (first px))]
    (assoc colour :image/pixels
           (vec (for [y (range height) x (range width)]
                  (let [i (+ (* y width) x)
                        [sum wsum]
                        (reduce
                         (fn [[sum wsum] [dy dx]]
                           (let [sy (clampi (+ y (* dy stride)) 0 (dec height))
                                 sx (clampi (+ x (* dx stride)) 0 (dec width))
                                 j (+ (* sy width) sx)
                                 k (* (nth b3 (+ dy 2)) (nth b3 (+ dx 2)))
                                 w (* k (feature-weight buffers i j sigmas))]
                             [(mapv + sum (mapv #(* w %) (nth px j))) (+ wsum w)]))
                         [(vec (repeat chans 0.0)) 0.0]
                         (for [dy (range -2 3) dx (range -2 3)] [dy dx]))]
                    (if (pos? wsum) (mapv #(/ % wsum) sum) (nth px i))))))))

(defn denoise-error
  "Why these buffers cannot be filtered, or nil."
  [{:keys [colour albedo normal depth]} {:keys [passes]}]
  (let [dims (fn [img] [(:image/width img) (:image/height img)])
        named (remove (comp nil? second) [["albedo" albedo] ["normal" normal] ["depth" depth]])]
    (cond
      (nil? colour) "no :colour buffer to denoise"

      (not (pos? passes))
      (str "passes must be positive, got " (pr-str passes)
           " — zero passes returns the noisy image unchanged, which is a"
           " denoiser that reports success and does nothing")

      (not= (* (:image/width colour) (:image/height colour)) (count (:image/pixels colour)))
      (str "the colour buffer says " (:image/width colour) "x" (:image/height colour)
           " but carries " (count (:image/pixels colour)) " pixels")

      (some (fn [[_ img]] (not= (dims img) (dims colour))) named)
      (str "feature buffers must match the colour buffer's size: colour is "
           (pr-str (dims colour)) ", "
           (string/join ", " (map (fn [[n img]] (str n " is " (pr-str (dims img)))) named))
           ". A misaligned feature buffer does not fail — it stops edges in the"
           " wrong places, which looks like a denoiser with the wrong sigmas.")

      (empty? named)
      (str "no feature buffer was supplied. Without albedo, normal or depth this"
           " is a colour-only bilateral filter, which cannot tell a silhouette"
           " from a bright sample; pass :albedo, :normal or :depth, or say"
           " :colour-only? true to mean it."))))

(def default-sigmas
  {:sigma-colour 0.6 :sigma-albedo 0.15 :sigma-normal 0.2 :sigma-depth 0.05})

(defn denoise
  "Filter `:colour` using `:albedo`, `:normal` and `:depth` as edge stops.

  `opts`: `:passes` (a-trous levels, stride doubles each time), the four
  sigmas, and `:colour-only?` to allow running without feature buffers.
  Returns `[:ok image]` or `[:error msg]`."
  ([buffers] (denoise buffers {}))
  ([buffers {:keys [passes colour-only?] :or {passes 4} :as opts}]
   (let [opts (merge default-sigmas opts {:passes passes})
         err (denoise-error buffers opts)
         err (if (and colour-only? err (string/includes? err "no feature buffer")) nil err)]
     (if err
       [:error err]
       [:ok (reduce (fn [c pass]
                      (atrous-pass (assoc buffers :colour c) (bit-shift-left 1 pass) opts))
                    (:colour buffers) (range passes))]))))

(defn gaussian
  "A plain separable-ish Gaussian over the same 5-tap support and the same
  strides, ignoring every feature buffer.

  This exists to be beaten. A denoiser that does not beat it is a blur with
  more arithmetic, and the only way to know which one has been written is to
  run both on the same image and compare — separately in the flat regions and
  at the edges."
  [colour passes]
  (reduce (fn [c pass]
            (let [stride (bit-shift-left 1 pass)
                  {:keys [image/width image/height]} c
                  px (:image/pixels c)
                  chans (count (first px))]
              (assoc c :image/pixels
                     (vec (for [y (range height) x (range width)]
                            (let [[sum wsum]
                                  (reduce (fn [[sum wsum] [dy dx]]
                                            (let [sy (clampi (+ y (* dy stride)) 0 (dec height))
                                                  sx (clampi (+ x (* dx stride)) 0 (dec width))
                                                  k (* (nth b3 (+ dy 2)) (nth b3 (+ dx 2)))]
                                              [(mapv + sum (mapv #(* k %) (nth px (+ (* sy width) sx))))
                                               (+ wsum k)]))
                                          [(vec (repeat chans 0.0)) 0.0]
                                          (for [dy (range -2 3) dx (range -2 3)] [dy dx]))]
                              (mapv #(/ % wsum) sum)))))))
          colour (range passes)))
