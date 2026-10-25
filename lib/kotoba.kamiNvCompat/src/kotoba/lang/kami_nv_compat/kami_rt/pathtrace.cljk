(ns kotoba.lang.kami-nv-compat.kami-rt.pathtrace
  "Clean-room Monte-Carlo path tracer (CPU reference) — portable .cljc port
  of src/kami-rt/pathtrace.ts. Wave 23.

  Textbook unidirectional path tracing (cosine-weighted importance sampling,
  next-event-free, Russian-roulette-free for determinism) on top of the
  kami-rt.bvh BVH/intersection core. The RNG and hemisphere sampling are
  written to be reproducible bit-for-bit against the WGSL stream: a
  per-(pixel, sample) xorshift32 stream, advanced in the exact same order."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.bvh :as bvh]))

;; ── materials ────────────────────────────────────────────────────────────

(defn material
  "Lambertian albedo + emitted radiance. Nonzero emission ⇒ the surface is a light."
  ([albedo] (material albedo [0.0 0.0 0.0]))
  ([albedo emission] {:albedo albedo :emission emission}))

(defn material-soup
  "Per-triangle materials, parallel to a triangle-soup. Flat double-arrays
  (3 floats/triangle each)."
  [materials]
  (let [n (count materials)
        albedo (double-array (* n 3))
        emission (double-array (* n 3))]
    (doseq [[i m] (map-indexed vector materials)
            :let [a (:albedo m)
                  e (:emission m)]]
      (aset albedo (* i 3) (double (a 0)))
      (aset albedo (+ (* i 3) 1) (double (a 1)))
      (aset albedo (+ (* i 3) 2) (double (a 2)))
      (aset emission (* i 3) (double (e 0)))
      (aset emission (+ (* i 3) 1) (double (e 1)))
      (aset emission (+ (* i 3) 2) (double (e 2))))
    {:albedo albedo :emission emission}))

(defn build-path-scene
  "A path-traceable scene: geometry + acceleration structure + materials.
  `triangles` and `materials` must be 1:1."
  [triangles materials]
  (assert (= (count triangles) (count materials))
          (str "build-path-scene: " (count triangles) " triangles vs "
               (count materials) " materials — must be 1:1"))
  (let [soup (bvh/triangle-soup triangles)]
    {:soup soup :bvh (bvh/build-bvh soup) :mats (material-soup materials)}))

;; ── deterministic RNG (xorshift32; identical to the WGSL stream) ───────────

(defn seed-hash
  "Mix three integers into a 32-bit seed (a small, well-dispersing hash)."
  [px py sample]
  (let [h0 (bit-and (+ (* px 1973) (* py 9277) (* sample 26699) 1) 0xffffffff)
        h1 (bit-and (* (bit-xor h0 (unsigned-bit-shift-right h0 15)) 0x2c1b3c6d) 0xffffffff)
        h2 (bit-and (* (bit-xor h1 (unsigned-bit-shift-right h1 12)) 0x297a2d39) 0xffffffff)
        h3 (bit-and (bit-xor h2 (unsigned-bit-shift-right h2 15)) 0xffffffff)]
    (if (zero? h3) 1 h3)))

(defn next-float!
  "Advance the mutable single-stream xorshift32 held in `rng`, an atom of a
  32-bit int. Returns the next float, half-open on the low end and open on
  the high end."
  [rng]
  (let [x0 @rng
        x1 (bit-xor x0 (bit-and (bit-shift-left x0 13) 0xffffffff))
        x2 (bit-xor x1 (unsigned-bit-shift-right x1 17))
        x3 (bit-xor x2 (bit-and (bit-shift-left x2 5) 0xffffffff))]
    (reset! rng x3)
    (/ x3 4294967296.0)))

;; ── small vector helpers ────────────────────────────────────────────────

(defn- vadd [a b] [(+ (a 0) (b 0)) (+ (a 1) (b 1)) (+ (a 2) (b 2))])
(defn- vmul [a b] [(* (a 0) (b 0)) (* (a 1) (b 1)) (* (a 2) (b 2))])
(defn- vscale [a s] [(* (a 0) s) (* (a 1) s) (* (a 2) s)])

(defn- vnorm [a]
  (let [l0 (Math/hypot (double (a 0)) (Math/hypot (double (a 1)) (double (a 2))))
        l (if (zero? l0) 1.0 l0)]
    [(/ (a 0) l) (/ (a 1) l) (/ (a 2) l)]))

(defn onb
  "Branchless orthonormal basis from a unit normal (Duff et al. 2017).
  Returns `[tangent bitangent]`; identical formula to the WGSL kernel."
  [n]
  (let [sign (if (>= (n 2) 0) 1.0 -1.0)
        a (/ -1.0 (+ sign (n 2)))
        b (* (n 0) (n 1) a)
        t [(+ 1.0 (* sign (n 0) (n 0) a)) (* sign b) (* (- sign) (n 0))]
        bt [b (+ sign (* (n 1) (n 1) a)) (- (n 1))]]
    [t bt]))

(defn- cosine-sample
  "Cosine-weighted hemisphere sample around `n`, drawing 2 floats from `rng`."
  [n rng]
  (let [r1 (next-float! rng)
        r2 (next-float! rng)
        phi (* 2.0 Math/PI r1)
        sin-t (Math/sqrt r2)
        cos-t (Math/sqrt (- 1.0 r2))
        basis (onb n)
        t (basis 0)
        bt (basis 1)
        x (* (Math/cos phi) sin-t)
        y (* (Math/sin phi) sin-t)]
    (vnorm (vadd (vadd (vscale t x) (vscale bt y)) (vscale n cos-t)))))

;; ── path-trace settings ──────────────────────────────────────────────────

(def default-path-settings
  {:samples-per-pixel 16
   :max-bounces 6
   :background [0.0 0.0 0.0]})

(defn- tri-emission [mats tri]
  (let [e (:emission mats)
        b (* tri 3)]
    [(aget e b) (aget e (+ b 1)) (aget e (+ b 2))]))

(defn- tri-albedo [mats tri]
  (let [a (:albedo mats)
        b (* tri 3)]
    [(aget a b) (aget a (+ b 1)) (aget a (+ b 2))]))

(defn- radiance
  "Trace one camera path and return the radiance it carries."
  [scene ro rd settings rng]
  (loop [bounce 0 throughput [1.0 1.0 1.0] acc [0.0 0.0 0.0] o ro d rd]
    (let [hit (bvh/trace-closest (:soup scene) (:bvh scene) o d)]
      (if (nil? hit)
        (vadd acc (vmul throughput (:background settings)))
        (let [acc2 (vadd acc (vmul throughput (tri-emission (:mats scene) (:tri hit))))]
          (if (= bounce (:max-bounces settings))
            acc2
            (let [nrm0 (bvh/tri-normal (:soup scene) (:tri hit))
                  facing (+ (* (nrm0 0) (d 0)) (* (nrm0 1) (d 1)) (* (nrm0 2) (d 2)))
                  nrm (if (pos? facing) (vscale nrm0 -1.0) nrm0)
                  throughput2 (vmul throughput (tri-albedo (:mats scene) (:tri hit)))
                  ht (:t hit)
                  hit-p [(+ (o 0) (* (d 0) ht)) (+ (o 1) (* (d 1) ht)) (+ (o 2) (* (d 2) ht))]
                  d2 (cosine-sample nrm rng)
                  o2 [(+ (hit-p 0) (* (nrm 0) 1e-4)) (+ (hit-p 1) (* (nrm 1) 1e-4)) (+ (hit-p 2) (* (nrm 2) 1e-4))]]
              (recur (inc bounce) throughput2 acc2 o2 d2))))))))

(defn path-trace-sync
  "Progressive CPU path trace into a `width × height` RGBA-float framebuffer.
  Reproducible: same scene + camera + settings ⇒ identical pixels. Identical
  math to the WGSL kernel within f32 rounding."
  ([scene cam width height]
   (path-trace-sync scene cam width height default-path-settings))
  ([scene cam width height settings]
   (let [fb (double-array (* width height 4))
         spp (max 1 (:samples-per-pixel settings))
         origin (:origin cam)
         lower-left (:lower-left cam)
         horizontal (:horizontal cam)
         vertical (:vertical cam)]
     (doseq [py (range height)
             px (range width)
             :let [col (loop [s-idx 0 col [0.0 0.0 0.0]]
                         (if (>= s-idx spp)
                           col
                           (let [rng (atom (seed-hash px py s-idx))
                                 u (/ (+ px (next-float! rng)) width)
                                 v (/ (+ py (next-float! rng)) height)
                                 dir (vnorm [(- (+ (lower-left 0) (* u (horizontal 0)) (* v (vertical 0))) (origin 0))
                                             (- (+ (lower-left 1) (* u (horizontal 1)) (* v (vertical 1))) (origin 1))
                                             (- (+ (lower-left 2) (* u (horizontal 2)) (* v (vertical 2))) (origin 2))])]
                             (recur (inc s-idx) (vadd col (radiance scene origin dir settings rng))))))
                   inv (/ 1.0 spp)
                   off (* (+ (* py width) px) 4)]]
       (aset fb off (* (col 0) inv))
       (aset fb (+ off 1) (* (col 1) inv))
       (aset fb (+ off 2) (* (col 2) inv))
       (aset fb (+ off 3) 1.0))
     fb)))
