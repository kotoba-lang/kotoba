(ns scad.csg
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-scad Rust crate
  (`kami-scad/src/csg.rs`, deleted in kotoba-lang/kami-engine PR #82 \"Remove Rust
  workspace from kami-engine\") as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  CSG mesh generation: `cylinder-mesh` builds a Y-axis-aligned truncated-cone
  (cylinder/cone) mesh centered at the origin, returning positions/normals/uvs/
  indices as flat vectors (mirrors the original `(Vec<f32>, Vec<f32>, Vec<f32>,
  Vec<u32>)` tuple return).

  NOTE: the original `cylinder_loaded` helper (which wraps `cylinder_mesh` into a
  `kami_render::mesh::LoadedMesh`) is intentionally NOT ported here — it depends on
  the unported sibling `kami-render` crate and is out of scope for this zero-dep
  restoration. Only the pure geometry function is ported."
  )

(def ^:private pi #?(:clj Math/PI :cljs js/Math.PI))

(defn- cos [x] #?(:clj (Math/cos x) :cljs (js/Math.cos x)))
(defn- sin [x] #?(:clj (Math/sin x) :cljs (js/Math.sin x)))
(defn- sqrt [x] #?(:clj (Math/sqrt x) :cljs (js/Math.sqrt x)))

(defn cylinder-mesh
  "Generate a cylinder (truncated cone) mesh: Y-axis aligned, centered at
  origin, base radius `r1`, top radius `r2`, height `h`, `slices` radial
  segments. Returns `{:positions [...] :normals [...] :uvs [...] :indices [...]}`
  as flat vectors of floats/ints, mirroring the original tuple return."
  [h r1 r2 slices]
  (let [half-h (/ h 2.0)
        n (long slices)]
    (loop [i 0
           positions []
           normals []
           uvs []]
      (if (<= i n)
        (let [theta (* 2.0 pi (/ (double i) (double n)))
              cos-t (cos theta)
              sin-t (sin theta)
              u (/ (double i) (double n))
              x0 (* r1 cos-t) z0 (* r1 sin-t)
              x1 (* r2 cos-t) z1 (* r2 sin-t)
              slope (/ (- r1 r2) h)
              nx cos-t ny slope nz sin-t
              len (sqrt (+ (* nx nx) (* ny ny) (* nz nz)))
              nx' (/ nx len) ny' (/ ny len) nz' (/ nz len)]
          (recur (inc i)
                 (into positions [x0 (- half-h) z0 x1 half-h z1])
                 (into normals [nx' ny' nz' nx' ny' nz'])
                 (into uvs [u 0.0 u 1.0])))
        ;; side indices
        (let [side-indices (vec (mapcat (fn [i]
                                           (let [b (* i 2)]
                                             [b (+ b 2) (+ b 1) (+ b 1) (+ b 2) (+ b 3)]))
                                         (range n)))
              ;; bottom cap
              center-bottom (quot (count positions) 3)
              positions (into positions [0.0 (- half-h) 0.0])
              normals (into normals [0.0 -1.0 0.0])
              uvs (into uvs [0.5 0.5])
              positions (into positions
                               (mapcat (fn [i]
                                         (let [theta (* 2.0 pi (/ (double i) (double n)))]
                                           [(* r1 (cos theta)) (- half-h) (* r1 (sin theta))]))
                                       (range n)))
              normals (into normals (mapcat (fn [_] [0.0 -1.0 0.0]) (range n)))
              uvs (into uvs (mapcat (fn [i]
                                       (let [theta (* 2.0 pi (/ (double i) (double n)))]
                                         [(+ 0.5 (* 0.5 (cos theta))) (+ 0.5 (* 0.5 (sin theta)))]))
                                     (range n)))
              bottom-cap-indices (vec (mapcat (fn [i]
                                                 (let [next (if (< (inc i) n) (inc i) 0)]
                                                   [center-bottom
                                                    (+ center-bottom 1 next)
                                                    (+ center-bottom 1 i)]))
                                               (range n)))
              ;; top cap
              center-top (quot (count positions) 3)
              positions (into positions [0.0 half-h 0.0])
              normals (into normals [0.0 1.0 0.0])
              uvs (into uvs [0.5 0.5])
              positions (into positions
                               (mapcat (fn [i]
                                         (let [theta (* 2.0 pi (/ (double i) (double n)))]
                                           [(* r2 (cos theta)) half-h (* r2 (sin theta))]))
                                       (range n)))
              normals (into normals (mapcat (fn [_] [0.0 1.0 0.0]) (range n)))
              uvs (into uvs (mapcat (fn [i]
                                       (let [theta (* 2.0 pi (/ (double i) (double n)))]
                                         [(+ 0.5 (* 0.5 (cos theta))) (+ 0.5 (* 0.5 (sin theta)))]))
                                     (range n)))
              top-cap-indices (vec (mapcat (fn [i]
                                              (let [next (if (< (inc i) n) (inc i) 0)]
                                                [center-top (+ center-top 1 i) (+ center-top 1 next)]))
                                            (range n)))
              indices (vec (concat side-indices bottom-cap-indices top-cap-indices))]
          {:positions positions :normals normals :uvs uvs :indices indices})))))
