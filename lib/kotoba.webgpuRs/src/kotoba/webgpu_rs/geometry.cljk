(ns kotoba.webgpu-rs.geometry
  "Pure CPU-side mesh generation — vertex (`pos3 + normal3`, interleaved)
  and index buffers as plain data, no wgpu buffer/pipeline calls. Ported
  from kami-webgpu-rs's `cube()` (the only mesh generator in its own
  `src/lib.rs`) plus `geo_sphere`/`geo_cylinder`, which lived in
  kami-webgpu-rs's `#[cfg(test)]` module as local re-implementations of
  `kami.webgpu.geometry` (the cljc canonical, in the separate
  `kotoba-lang/webgpu` repo — not touched by this port) used there only to
  assert cross-platform parity against fixtures. The generation algorithms
  themselves are pure geometry logic, not test-only by nature, so they're
  ported here as first-class data-producing functions rather than dropped;
  the golden-fixture *comparison* (which required `kami-webgpu`/fixtures
  co-located in the Rust workspace) is out of scope — see the README.

  Every generator returns `[verts indices]`: `verts` is a flat vector of
  `f64`s, 6 per vertex (`x y z nx ny nz`); `indices` is a flat vector of
  non-negative ints, 3 per triangle.

  No network, no I/O.")

;; --- cube (pos+normal), 24 verts / 36 indices — matches the web mesh ------

(def ^:private cube-faces
  "`[normal [4 quad corners]]` per face, same winding as kami-webgpu-rs's
  `cube()`."
  [[[0.0 0.0 1.0] [[-0.5 -0.5 0.5] [0.5 -0.5 0.5] [0.5 0.5 0.5] [-0.5 0.5 0.5]]]
   [[0.0 0.0 -1.0] [[0.5 -0.5 -0.5] [-0.5 -0.5 -0.5] [-0.5 0.5 -0.5] [0.5 0.5 -0.5]]]
   [[1.0 0.0 0.0] [[0.5 -0.5 0.5] [0.5 -0.5 -0.5] [0.5 0.5 -0.5] [0.5 0.5 0.5]]]
   [[-1.0 0.0 0.0] [[-0.5 -0.5 -0.5] [-0.5 -0.5 0.5] [-0.5 0.5 0.5] [-0.5 0.5 -0.5]]]
   [[0.0 1.0 0.0] [[-0.5 0.5 0.5] [0.5 0.5 0.5] [0.5 0.5 -0.5] [-0.5 0.5 -0.5]]]
   [[0.0 -1.0 0.0] [[-0.5 -0.5 -0.5] [0.5 -0.5 -0.5] [0.5 -0.5 0.5] [-0.5 -0.5 0.5]]]])

(defn cube
  "A 1×1×1 cuboid centred at the origin, 24 verts (4 per face, unshared
  across faces so normals are flat-shaded) / 36 indices (6 faces × 2
  tris). `[verts indices]`."
  []
  (loop [faces cube-faces verts [] idx [] base 0]
    (if (empty? faces)
      [verts idx]
      (let [[[nx ny nz] quad] (first faces)
            verts' (into verts (mapcat (fn [[x y z]] [x y z nx ny nz]) quad))
            idx' (into idx [base (+ base 1) (+ base 2)
                             base (+ base 2) (+ base 3)])]
        (recur (rest faces) verts' idx' (+ base 4))))))

;; --- sphere / cylinder — ports of kami-webgpu-rs's test-only geometry ----

(defn- push-v6 [v [px py pz] [nx ny nz]]
  (into v [(double px) (double py) (double pz) (double nx) (double ny) (double nz)]))

(defn sphere
  "UV sphere of radius `r` with `rings` latitude bands and `sectors`
  longitude segments. Direct port of kami-webgpu-rs's test-local
  `geo_sphere`."
  [r rings sectors]
  (let [pi Math/PI
        verts (vec (for [i (range (inc rings))
                          j (range (inc sectors))
                          :let [phi (* pi (/ (double i) rings))
                                th (* 2.0 pi (/ (double j) sectors))
                                nx (* (Math/sin phi) (Math/cos th))
                                ny (Math/cos phi)
                                nz (* (Math/sin phi) (Math/sin th))]]
                      [(* r nx) (* r ny) (* r nz) nx ny nz]))
        flat (vec (mapcat identity verts))
        stride (inc sectors)
        idx (vec (for [i (range rings)
                        j (range sectors)
                        :let [a (+ (* i (inc sectors)) j)]
                        k [a (+ a 1) (+ a stride 1) a (+ a stride 1) (+ a stride)]]
                    k))]
    [flat idx]))

(defn- cyl-ring [r sectors y]
  (let [pi Math/PI]
    (vec (for [j (range (inc sectors))
                :let [th (* 2.0 pi (/ (double j) sectors))]]
           [(* r (Math/cos th)) y (* r (Math/sin th))]))))

(defn cylinder
  "Capped cylinder of radius `r`, height `h`, `sectors` around the
  circumference. Direct port of kami-webgpu-rs's test-local
  `geo_cylinder`."
  [r h sectors]
  (let [hy (/ h 2.0)
        top (cyl-ring r sectors hy)
        bot (cyl-ring r sectors (- hy))
        side-verts (vec (mapcat (fn [[x _ z] tp bp]
                                   (let [m (max (Math/sqrt (+ (* x x) (* z z))) 1e-6)
                                         n [(/ x m) 0.0 (/ z m)]]
                                     (into (push-v6 [] tp n) (push-v6 [] bp n))))
                                 top top bot))
        side-idx (vec (mapcat (fn [j]
                                 (let [a (* 2 j)]
                                   [a (+ a 1) (+ a 3) a (+ a 3) (+ a 2)]))
                               (range sectors)))
        nv (* 2 (count top))
        cap (fn [y ny dir base]
              (let [ring (cyl-ring r sectors y)
                    verts (into (push-v6 [] [0.0 y 0.0] ny)
                                 (mapcat #(push-v6 [] % ny) ring))
                    idx (vec (mapcat (fn [j]
                                        (if (pos? dir)
                                          [base (+ base 1 j) (+ base 2 j)]
                                          [base (+ base 2 j) (+ base 1 j)]))
                                      (range sectors)))]
                [verts idx]))
        [top-cap-v top-cap-i] (cap hy [0.0 1.0 0.0] 1 nv)
        bot-base (+ nv (inc (count top)))
        [bot-cap-v bot-cap-i] (cap (- hy) [0.0 -1.0 0.0] -1 bot-base)]
    [(vec (concat side-verts top-cap-v bot-cap-v))
     (vec (concat side-idx top-cap-i bot-cap-i))]))
