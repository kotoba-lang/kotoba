(ns kotoba.raytrace.path
  "A unidirectional path tracer, written so that most of what it claims can be
  checked against a number rather than looked at.

  Path tracing is an estimator of the rendering equation, and estimators are
  easy to get subtly wrong: a missing 1/pi in the BRDF, a cosine applied twice,
  a PDF that does not match the sampling — each produces an image that looks
  like a render and is not the answer. So the design here is arranged around
  cases with known values:

  - **The white furnace.** Put a convex diffuse object of albedo 1 inside a
    uniform environment of radiance L. Every path that leaves the surface
    escapes and collects L, and the throughput after a Lambertian bounce with
    cosine-weighted sampling is exactly the albedo — the 1/pi in the BRDF, the
    cosine, and the pdf cancel. So the answer is L with ZERO variance, and any
    of those three factors being wrong shows up as a bias, not as noise. With
    albedo rho the answer is rho L, equally exactly.
  - **Two estimators, one answer.** Next-event estimation and brute-force
    hemisphere sampling compute the same integral by different routes, so they
    have to agree within their own error bars.
  - **The rate.** Monte Carlo error falls as 1/sqrt(N); quadrupling the samples
    has to halve it.

  The generator is an explicit int32 xorshift, so the same seed gives the same
  image on the JVM and in a browser — a frame that cannot be re-rendered
  identically cannot be compared with anything.

  Not here: specular and glossy BSDFs, refraction, participating media,
  textures, motion blur, spectral rendering, bidirectional or Metropolis
  transport, and multiple importance sampling — with only diffuse surfaces and
  uniform lights the two estimators here do not need a weighting scheme, and
  writing one that is never exercised would be decoration."
  (:require [kotoba.lang.text :as string]))

(defn- v+ [a b] (mapv + a b))
(defn- v- [a b] (mapv - a b))
(defn- vs [a s] (mapv #(* s %) a))
(defn- v* [a b] (mapv * a b))
(defn- dot [a b] (reduce + (map * a b)))
(defn- sqrt [x] (#?(:clj Math/sqrt :cljs js/Math.sqrt) x))
(defn- norm [a] (sqrt (dot a a)))
(defn- unit [a] (let [n (norm a)] (if (pos? n) (vs a (/ 1.0 n)) a)))
(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))

;; ---------------------------------------------------------------------------
;; Deterministic randomness, int32, identical on both hosts.
;; ---------------------------------------------------------------------------

(defn- i32 [x] #?(:clj (unchecked-int x) :cljs (bit-or 0 x)))
(defn- shl [x n] (i32 (bit-shift-left (i32 x) n)))
(defn- ushr [x n]
  #?(:clj (i32 (unsigned-bit-shift-right (bit-and (long (i32 x)) 0xffffffff) n))
     :cljs (unsigned-bit-shift-right x n)))

(defn- next-state [x]
  (let [x (i32 (if (zero? x) 2463534242 x))
        x (bit-xor x (shl x 13))
        x (bit-xor x (ushr x 17))
        x (bit-xor x (shl x 5))]
    (i32 x)))

(defn- unit01 [x]
  (let [u #?(:clj (bit-and (long (i32 x)) 0xffffffff)
             :cljs (unsigned-bit-shift-right x 0))]
    (/ u 4294967296.0)))

;; ---------------------------------------------------------------------------
;; Geometry: analytic spheres. A convex primitive is what makes the furnace
;; test exact — every bounce leaves the object.
;; ---------------------------------------------------------------------------

(defn sphere
  [{:keys [centre radius albedo emission]
    :or {centre [0.0 0.0 0.0] radius 1.0 albedo [0.5 0.5 0.5] emission [0.0 0.0 0.0]}}]
  {:shape/kind :sphere :shape/centre (mapv double centre) :shape/radius (double radius)
   :shape/albedo (mapv double albedo) :shape/emission (mapv double emission)})

(defn- hit-sphere [{:shape/keys [centre radius]} origin dir]
  (let [oc (v- origin centre)
        b (dot oc dir)
        c (- (dot oc oc) (* radius radius))
        disc (- (* b b) c)]
    (when (pos? disc)
      (let [s (sqrt disc)
            t0 (- (- b) s)
            t1 (+ (- b) s)]
        (cond (> t0 1.0e-6) t0
              (> t1 1.0e-6) t1
              :else nil)))))

(defn- intersect [shapes origin dir]
  (reduce (fn [best sh]
            (if-let [t (hit-sphere sh origin dir)]
              (if (or (nil? best) (< t (:t best)))
                {:t t :shape sh}
                best)
              best))
          nil shapes))

(defn- basis
  "An orthonormal frame with `n` as its third axis."
  [n]
  (let [a (if (< (#?(:clj Math/abs :cljs js/Math.abs) (nth n 0)) 0.9) [1.0 0.0 0.0] [0.0 1.0 0.0])
        u (unit (let [[ax ay az] a [nx ny nz] n]
                  [(- (* ay nz) (* az ny)) (- (* az nx) (* ax nz)) (- (* ax ny) (* ay nx))]))
        v (let [[ux uy uz] u [nx ny nz] n]
            [(- (* ny uz) (* nz uy)) (- (* nz ux) (* nx uz)) (- (* nx uy) (* ny ux))])]
    [u v n]))

(defn cosine-sample
  "A direction about `n`, distributed as cos(theta)/pi.

  Returned with no weight, because for a Lambertian BRDF there isn't one: the
  estimator's factor is `albedo * cos / (pi * pdf)` and with `pdf = cos/pi`
  that is exactly `albedo`. Every term cancels, which is why the furnace test
  has zero variance and why a mistake in any of the three shows up as a bias."
  [n u1 u2]
  (let [r (sqrt u1)
        phi (* 2.0 pi u2)
        x (* r (#?(:clj Math/cos :cljs js/Math.cos) phi))
        y (* r (#?(:clj Math/sin :cljs js/Math.sin) phi))
        z (sqrt (max 0.0 (- 1.0 u1)))
        [bu bv bn] (basis n)]
    (unit (v+ (vs bu x) (v+ (vs bv y) (vs bn z))))))

;; ---------------------------------------------------------------------------
;; The estimator
;; ---------------------------------------------------------------------------

(defn scene-error
  "Why this scene cannot be rendered, or nil."
  [{:keys [shapes environment]} {:keys [max-depth samples]}]
  (cond
    (not (and (integer? max-depth) (pos? max-depth)))
    (str "max-depth must be a positive integer, got " (pr-str max-depth)
         " — zero bounces renders emission only, which is a light meter, not a"
         " renderer, and reporting it as a render hides that no transport ran")

    (not (and (integer? samples) (pos? samples)))
    (str "samples must be a positive integer, got " (pr-str samples))

    (empty? shapes)
    "no shapes to render"

    (some (fn [s] (some #(> % 1.0) (:shape/albedo s))) shapes)
    (str "an albedo above 1 reflects more light than it receives: "
         (pr-str (mapv :shape/albedo (filter (fn [s] (some #(> % 1.0) (:shape/albedo s))) shapes)))
         ". Every energy check in this namespace would then pass while the"
         " image gets brighter with every bounce.")

    (and (every? (fn [s] (every? zero? (:shape/emission s))) shapes)
         (every? zero? (or environment [0.0 0.0 0.0])))
    (str "nothing emits: every shape's emission is zero and the environment is"
         " black, so the answer is a black image. That is a scene with no"
         " lights, not a render, and returning it as one is how a lighting"
         " mistake becomes 'the renderer is broken'.")))

(defn radiance
  "Estimate the radiance along one ray. Returns an RGB triple.

  With `:next-event? true` the direct contribution from emissive shapes is
  sampled explicitly and emission is not collected again on the following
  bounce; with it false the same integral is estimated by hitting lights
  through the hemisphere sampling alone. Both are here because agreeing with
  each other is the check."
  [{:keys [shapes environment] :as scene} origin dir
   {:keys [max-depth next-event?] :or {max-depth 8} :as opts} state]
  (let [env (or environment [0.0 0.0 0.0])
        lights (filterv (fn [s] (some pos? (:shape/emission s))) shapes)]
    (loop [origin origin dir dir depth 0 throughput [1.0 1.0 1.0] acc [0.0 0.0 0.0] st state
           specular? true]
      (if (= depth max-depth)
        [acc st]
        (if-let [{:keys [t shape]} (intersect shapes origin dir)]
          (let [p (v+ origin (vs dir t))
                n (unit (v- p (:shape/centre shape)))
                n (if (pos? (dot n dir)) (vs n -1.0) n)
                emit (:shape/emission shape)
                acc (if (or (not next-event?) specular?)
                      (v+ acc (v* throughput emit))
                      acc)
                ;; Direct lighting, sampled on the LIGHT rather than on the
                ;; hemisphere: pick a direction inside the cone the sphere
                ;; subtends, whose pdf is 1/(2 pi (1 - cos theta_max)). That is
                ;; a genuinely different estimator from the bounce sampling
                ;; below — different pdf, different variance — which is what
                ;; makes "the two agree" evidence rather than a tautology.
                [acc st]
                (if (and next-event? (seq lights))
                  (reduce
                   (fn [[a s] light]
                     (if (identical? light shape)
                       [a s]
                       (let [to (v- (:shape/centre light) p)
                             d2 (dot to to)
                             lr (:shape/radius light)
                             sin2 (min 1.0 (/ (* lr lr) d2))
                             cos-max (sqrt (max 0.0 (- 1.0 sin2)))
                             s1 (next-state s) s2 (next-state s1)
                             ct (+ cos-max (* (- 1.0 cos-max) (unit01 s1)))
                             st* (sqrt (max 0.0 (- 1.0 (* ct ct))))
                             phi (* 2.0 pi (unit01 s2))
                             [bu bv bn] (basis (unit to))
                             ld (unit (v+ (vs bu (* st* (#?(:clj Math/cos :cljs js/Math.cos) phi)))
                                          (v+ (vs bv (* st* (#?(:clj Math/sin :cljs js/Math.sin) phi)))
                                              (vs bn ct))))
                             cos-s (dot n ld)
                             pdf (/ 1.0 (* 2.0 pi (- 1.0 cos-max)))
                             hit (intersect shapes (v+ p (vs n 1.0e-6)) ld)]
                         [(if (and (pos? cos-s) (pos? pdf) hit (identical? light (:shape hit)))
                            (v+ a (v* throughput
                                      (vs (v* (:shape/albedo shape) (:shape/emission light))
                                          (/ cos-s (* pi pdf)))))
                            a)
                          s2])))
                   [acc st] lights)
                  [acc st])
                s1 (next-state st) s2 (next-state s1)
                new-dir (cosine-sample n (unit01 s1) (unit01 s2))
                ;; albedo * cos / (pi * pdf) = albedo, exactly
                throughput (v* throughput (:shape/albedo shape))]
            (if (every? #(< % 1.0e-12) throughput)
              [acc s2]
              (recur (v+ p (vs n 1.0e-6)) new-dir (inc depth) throughput acc s2 false)))
          [(v+ acc (v* throughput env)) st])))))

(defn film
  "Average `samples` estimates per pixel over a `width` x `height` grid,
  through a pinhole at `:eye` looking down -Z with the given half-extent.

  Returns `[:ok image]` in the shape `kotoba.raytrace.denoise` consumes, so a
  render can be handed straight to the denoiser."
  [scene {:keys [width height samples seed] :or {width 16 height 16 samples 16 seed 1} :as opts}]
  (if-let [e (scene-error scene opts)]
    [:error e]
    (let [half 1.0
          eye (:eye opts [0.0 0.0 5.0])]
      [:ok {:image/width width :image/height height :image/channels 3
            :image/pixels
            (vec (for [y (range height) x (range width)]
                   (let [px (* half (- (/ (* 2.0 (+ 0.5 x)) width) 1.0))
                         py (* half (- 1.0 (/ (* 2.0 (+ 0.5 y)) height)))
                         dir (unit [px py -1.0])]
                     (loop [i 0 sum [0.0 0.0 0.0]
                            st (next-state (+ seed (* 9781 (+ (* y width) x))))]
                       (if (= i samples)
                         (vs sum (/ 1.0 samples))
                         (let [[l st'] (radiance scene eye dir opts st)]
                           (recur (inc i) (v+ sum l) (next-state st'))))))))}])))

(defn mean
  "Channel-wise mean of an image — what a furnace test compares."
  [{:keys [image/pixels]}]
  (vs (reduce v+ [0.0 0.0 0.0] pixels) (/ 1.0 (count pixels))))
