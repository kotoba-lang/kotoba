(ns kotoba.lang.kami-nv-compat.utsushimi.render-bridge
  "utsushimi — render bridge (synthetic-data ground truth via kami-rt/
  kami-rtx). Portable .cljc port of src/utsushimi/render-bridge.ts. Wave 32.

  Turns DR-randomized scene primitives into (a) real 2D bounding boxes by
  projecting each semantic prim's AABB through the camera, and (b)
  optional RGB frames by tessellating prims into triangles and
  ray-tracing them with kami-rt. This upgrades the upstream Replicator
  placeholder (full-image bbox / no pixels) to genuine annotated images.

  Projection reuses kami-rt's pinhole basis so the projected boxes align
  with a kami-rt render from the same camera parameters.

  ADR-2605261800 SD6 / D10.4 utsushimi."
  (:require [kotoba.lang.kami-nv-compat.kami-rt.bvh :as bvh]
            [kotoba.lang.kami-nv-compat.kami-rt.index :as kami-rt]))

;; ── projection camera (kami-rt pinhole basis) ────────────────────────────
;; ProjCamera {:eye :w :u :v :tan-half :aspect}
;; w = norm(eye-target), u = norm(up x w), v = w x u.

(defn- vsub [a b] [(- (a 0) (b 0)) (- (a 1) (b 1)) (- (a 2) (b 2))])
(defn- vcross [a b]
  [(- (* (a 1) (b 2)) (* (a 2) (b 1)))
   (- (* (a 2) (b 0)) (* (a 0) (b 2)))
   (- (* (a 0) (b 1)) (* (a 1) (b 0)))])
(defn- vdot [a b] (+ (* (a 0) (b 0)) (* (a 1) (b 1)) (* (a 2) (b 2))))
(defn- vnorm
  [a]
  (let [l0 (Math/hypot (double (a 0)) (Math/hypot (double (a 1)) (double (a 2))))
        l (if (zero? l0) 1.0 l0)]
    [(/ (a 0) l) (/ (a 1) l) (/ (a 2) l)]))

(defn make-proj-camera
  [eye target up vfov-deg aspect]
  (let [w (vnorm (vsub eye target))
        u (vnorm (vcross up w))
        v (vcross w u)]
    {:eye eye :w w :u u :v v
     :tan-half (Math/tan (/ (* vfov-deg Math/PI) 180.0 2.0))
     :aspect aspect}))

(defn project-point
  "Project a world point to pixel coords (top-left origin, y down). Returns
  nil when the point is behind the camera."
  [cam p width height]
  (let [d (vsub p (:eye cam))
        depth (- (vdot d (:w cam)))] ; forward = -w
    (when (> depth 1e-4)
      (let [cx (vdot d (:u cam))
            cy (vdot d (:v cam))
            ndc-x (/ cx depth (* (:tan-half cam) (:aspect cam)))
            ndc-y (/ cy depth (:tan-half cam))
            px (* (+ (* ndc-x 0.5) 0.5) width)
            py (* (- 1.0 (+ (* ndc-y 0.5) 0.5)) height)]
        [px py]))))

;; ── prim AABB ─────────────────────────────────────────────────────────────

(defn- as-vec3 [a] (if a [(a 0) (a 1) (a 2)] [0.0 0.0 0.0]))

(defn- prim-aabb
  [prim]
  (let [p (as-vec3 (:position prim))]
    (case (:kind prim)
      :cube {:min [(- (p 0) 0.5) (- (p 1) 0.5) (- (p 2) 0.5)]
             :max [(+ (p 0) 0.5) (+ (p 1) 0.5) (+ (p 2) 0.5)]}
      :sphere (let [r (or (:radius prim) 1)]
                {:min [(- (p 0) r) (- (p 1) r) (- (p 2) r)]
                 :max [(+ (p 0) r) (+ (p 1) r) (+ (p 2) r)]})
      nil))) ; cameras / lights have no annotatable extent

(defn project-aabb
  "Project an AABB to a 2D bbox [x y w h] (clamped to the image), or nil if
  entirely behind the camera."
  [cam mn mx width height]
  (let [corners (for [i (range 8)]
                  [(if (pos? (bit-and i 1)) (mx 0) (mn 0))
                   (if (pos? (bit-and i 2)) (mx 1) (mn 1))
                   (if (pos? (bit-and i 4)) (mx 2) (mn 2))])
        projected (keep #(project-point cam % width height) corners)]
    (when (seq projected)
      (let [min-x (apply min (map first projected))
            min-y (apply min (map second projected))
            max-x (apply max (map first projected))
            max-y (apply max (map second projected))
            x0 (max 0.0 (min (double width) min-x))
            y0 (max 0.0 (min (double height) min-y))
            x1 (max 0.0 (min (double width) max-x))
            y1 (max 0.0 (min (double height) max-y))]
        (when (and (> x1 x0) (> y1 y0))
          [x0 y0 (- x1 x0) (- y1 y0)])))))

(defn annotate-frame
  "Annotate every semantic prim in `prims` with a real 2D bbox. Prims with
  no class semantic or no on-screen extent are returned without :bbox2d."
  [cam prims width height]
  (mapv (fn [prim]
          (if-let [aabb (prim-aabb prim)]
            (if-let [bbox (project-aabb cam (:min aabb) (:max aabb) width height)]
              (assoc prim :bbox2d bbox)
              prim)
            prim))
        prims))

;; ── tessellation + RGB render (optional bonus ground truth) ──────────────

(defn- cube-tris
  [c h]
  (let [v [[(- (c 0) h) (- (c 1) h) (- (c 2) h)] [(+ (c 0) h) (- (c 1) h) (- (c 2) h)]
           [(+ (c 0) h) (+ (c 1) h) (- (c 2) h)] [(- (c 0) h) (+ (c 1) h) (- (c 2) h)]
           [(- (c 0) h) (- (c 1) h) (+ (c 2) h)] [(+ (c 0) h) (- (c 1) h) (+ (c 2) h)]
           [(+ (c 0) h) (+ (c 1) h) (+ (c 2) h)] [(- (c 0) h) (+ (c 1) h) (+ (c 2) h)]]
        q (fn [a b cc d] [[(v a) (v b) (v cc)] [(v a) (v cc) (v d)]])]
    (vec (concat (q 0 1 2 3) (q 5 4 7 6) (q 4 0 3 7)
                 (q 1 5 6 2) (q 4 5 1 0) (q 3 2 6 7)))))

(defn- sphere-tris
  ([c r] (sphere-tris c r 8))
  ([c r seg]
   (let [pt (fn [i j]
              (let [theta (* (/ (double i) seg) Math/PI)
                    phi (* (/ (double j) seg) 2.0 Math/PI)]
                [(+ (c 0) (* r (Math/sin theta) (Math/cos phi)))
                 (+ (c 1) (* r (Math/cos theta)))
                 (+ (c 2) (* r (Math/sin theta) (Math/sin phi)))]))]
     (vec (mapcat (fn [i]
                    (mapcat (fn [j]
                              (let [a (pt i j) b (pt (inc i) j)
                                    cc (pt (inc i) (inc j)) d (pt i (inc j))]
                                [[a b cc] [a cc d]]))
                            (range seg)))
                  (range seg))))))

(defn prims-to-scene
  "Tessellate the renderable prims (cubes + spheres) into a kami-rt scene."
  [prims]
  (let [tris (mapcat (fn [prim]
                        (let [p (as-vec3 (:position prim))]
                          (case (:kind prim)
                            :cube (cube-tris p 0.5)
                            :sphere (sphere-tris p (or (:radius prim) 1))
                            [])))
                      prims)]
    (kami-rt/build-scene (vec tris))))

(defn render-frame-cpu
  "Render an RGB frame (RGBA float framebuffer) of the prims via kami-rt's
  CPU ray tracer, from a camera matching make-proj-camera's parameters."
  [eye target up vfov-deg prims width height]
  (let [scene (prims-to-scene prims)
        cam (bvh/look-at eye target up vfov-deg (/ (double width) height))]
    (:framebuffer (kami-rt/trace-image-cpu scene cam width height))))
