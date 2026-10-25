(ns game.brainrot-mesh
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-game Rust
  crate (`kami-game/src/brainrot_mesh.rs`, 1646 lines, `kotoba-lang/kami-engine`,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of the
  clj-wgsl migration (ADR-2607010930, `com-junkawasaki/root`). Restored as part
  of a 7-cluster parallel restoration of `kami-game` — this is Cluster D
  (procedural mesh generation).

  Purpose: Nintendo-Mii-style procedural mesh generators for \"brainrot\"
  characters/objects (toilet, character rig, dumbbell, obelisk, blob, food
  crate, orb, torii gate, gorilla...) plus a multi-stage \"evolution\" mesh
  dispatcher (Pokemon-style stage transforms) built by composing those
  primitives. Every function returns a mesh as a `[vertices indices]` pair
  (mirroring the original Rust `(Vec<f32>, Vec<u32>)` tuple): `vertices` is a
  flat interleaved pos3+norm3+uv2 (stride 8) float vector, `indices` is a flat
  u32-ish index vector for a triangle list. Pure data + pure functions
  throughout; no IO/GPU. `offset-mesh`/`scale-mesh` are pure transforms here
  (the original mutated `&mut (Vec<f32>, Vec<u32>)` in place; CLJC data is
  immutable, so they return a new mesh instead).")

;; ---------------------------------------------------------------------------
;; Portable math helpers (#?(:clj ...) / #?(:cljs ...) so this namespace runs
;; unmodified on the JVM and in ClojureScript).
;; ---------------------------------------------------------------------------

(defn- sin* [x] #?(:clj (Math/sin (double x)) :cljs (js/Math.sin x)))
(defn- cos* [x] #?(:clj (Math/cos (double x)) :cljs (js/Math.cos x)))
(defn- sqrt* [x] #?(:clj (Math/sqrt (double x)) :cljs (js/Math.sqrt x)))
(defn- abs* [x] #?(:clj (Math/abs (double x)) :cljs (js/Math.abs x)))

(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))

;; ---------------------------------------------------------------------------
;; Mesh primitives
;; ---------------------------------------------------------------------------

(defn merge-meshes
  "Merge multiple `[vertices indices]` meshes into one, offsetting indices.
  Mirrors `merge_meshes`."
  [meshes]
  (reduce (fn [[acc-v acc-i] [verts idxs]]
            (let [base (quot (count acc-v) 8)]
              [(into acc-v verts)
               (into acc-i (map #(+ % base) idxs))]))
          [[] []]
          meshes))

(defn sphere-mesh
  "UV sphere with given stacks/slices, radius, and center offset.
  Mirrors `sphere_mesh`."
  [stacks slices radius cx cy cz]
  (let [vertices (vec (apply concat
                        (for [i (range (inc stacks))
                              :let [phi (* PI (/ (double i) stacks))
                                    y (cos* phi)
                                    r (sin* phi)]
                              j (range (inc slices))
                              :let [theta (* 2.0 PI (/ (double j) slices))
                                    nx (* r (cos* theta))
                                    nz (* r (sin* theta))
                                    ny y]]
                          [(+ cx (* nx radius)) (+ cy (* ny radius)) (+ cz (* nz radius))
                           nx ny nz
                           (/ (double j) slices) (/ (double i) stacks)])))
        ring (inc slices)
        indices (vec (apply concat
                       (for [i (range stacks) j (range slices)
                             :let [a (+ (* i ring) j) b (+ a ring)]]
                         [a b (inc a) (inc a) b (inc b)])))]
    [vertices indices]))

(defn cylinder-mesh
  "Cylinder along Y axis with given segments, radius, half-height, and center
  offset. Mirrors `cylinder_mesh`."
  [segments radius half-height cx cy cz]
  (let [side-verts (vec (apply concat
                          (for [ring (range 2)
                                :let [y (if (zero? ring) (- half-height) half-height)
                                      v (double ring)]
                                j (range (inc segments))
                                :let [theta (* 2.0 PI (/ (double j) segments))
                                      nx (cos* theta) nz (sin* theta)]]
                            [(+ cx (* nx radius)) (+ cy y) (+ cz (* nz radius))
                             nx 0.0 nz
                             (/ (double j) segments) v])))
        ring-size (inc segments)
        side-idxs (vec (apply concat
                         (for [j (range segments)
                               :let [a j b (+ a ring-size)]]
                           [a b (inc a) (inc a) b (inc b)])))
        top-center (quot (count side-verts) 8)
        top-cap-center [cx (+ cy half-height) cz 0.0 1.0 0.0 0.5 0.5]
        top-ring (vec (apply concat
                        (for [j (range (inc segments))
                              :let [theta (* 2.0 PI (/ (double j) segments))
                                    nx (cos* theta) nz (sin* theta)]]
                          [(+ cx (* nx radius)) (+ cy half-height) (+ cz (* nz radius))
                           0.0 1.0 0.0
                           (+ 0.5 (* nx 0.5)) (+ 0.5 (* nz 0.5))])))
        top-idxs (vec (apply concat
                        (for [j (range segments)]
                          [top-center (+ top-center 1 j) (+ top-center 2 j)])))
        verts-after-top (into (into side-verts top-cap-center) top-ring)
        idxs-after-top (into side-idxs top-idxs)
        bot-center (quot (count verts-after-top) 8)
        bot-cap-center [cx (- cy half-height) cz 0.0 -1.0 0.0 0.5 0.5]
        bot-ring (vec (apply concat
                        (for [j (range (inc segments))
                              :let [theta (* 2.0 PI (/ (double j) segments))
                                    nx (cos* theta) nz (sin* theta)]]
                          [(+ cx (* nx radius)) (- cy half-height) (+ cz (* nz radius))
                           0.0 -1.0 0.0
                           (+ 0.5 (* nx 0.5)) (+ 0.5 (* nz 0.5))])))
        bot-idxs (vec (apply concat
                        (for [j (range segments)]
                          [bot-center (+ bot-center 2 j) (+ bot-center 1 j)])))
        final-verts (into (into verts-after-top bot-cap-center) bot-ring)
        final-idxs (into idxs-after-top bot-idxs)]
    [final-verts final-idxs]))

(defn capsule
  "Cylinder with sphere caps. Mirrors `capsule`."
  [radius half-height segments]
  (let [cyl (cylinder-mesh segments radius half-height 0.0 0.0 0.0)
        top-cap (sphere-mesh (quot segments 2) segments radius 0.0 half-height 0.0)
        bot-cap (sphere-mesh (quot segments 2) segments radius 0.0 (- half-height) 0.0)]
    (merge-meshes [cyl top-cap bot-cap])))

(defn- add-quad
  "Append a quad (4 verts + 6 indices, UVs (0,0)(1,0)(1,1)(0,1)) to `[vertices
  indices]`. Local equivalent of the Rust closures named `add_quad`."
  [[vertices indices] p0 p1 p2 p3 n]
  (let [base (quot (count vertices) 8)
        vs (-> vertices
               (into p0) (into n) (into [0.0 0.0])
               (into p1) (into n) (into [1.0 0.0])
               (into p2) (into n) (into [1.0 1.0])
               (into p3) (into n) (into [0.0 1.0]))
        is (into indices [base (inc base) (+ base 2) base (+ base 2) (+ base 3)])]
    [vs is]))

(defn rounded-box
  "Rounded box with beveled edges, approximated as a box with slightly inset
  faces plus bevel quads. Mirrors `rounded_box`."
  [w h d bevel]
  (let [hw (* w 0.5) hh (* h 0.5) hd (* d 0.5)
        b (min bevel hw hh hd)
        iw (- hw b) ih (- hh b) id (- hd b)
        diag (/ 1.0 (sqrt* 2.0))
        steps [[[(- iw) (- ih) hd] [iw (- ih) hd] [iw ih hd] [(- iw) ih hd] [0.0 0.0 1.0]]
               [[iw (- ih) (- hd)] [(- iw) (- ih) (- hd)] [(- iw) ih (- hd)] [iw ih (- hd)] [0.0 0.0 -1.0]]
               [[(- iw) hh (- id)] [iw hh (- id)] [iw hh id] [(- iw) hh id] [0.0 1.0 0.0]]
               [[(- iw) (- hh) id] [iw (- hh) id] [iw (- hh) (- id)] [(- iw) (- hh) (- id)] [0.0 -1.0 0.0]]
               [[hw (- ih) (- id)] [hw (- ih) id] [hw ih id] [hw ih (- id)] [1.0 0.0 0.0]]
               [[(- hw) (- ih) id] [(- hw) (- ih) (- id)] [(- hw) ih (- id)] [(- hw) ih id] [-1.0 0.0 0.0]]
               [[(- iw) ih hd] [iw ih hd] [iw hh id] [(- iw) hh id] [0.0 diag diag]]
               [[iw ih (- hd)] [(- iw) ih (- hd)] [(- iw) hh (- id)] [iw hh (- id)] [0.0 diag (- diag)]]
               [[(- iw) (- hh) id] [iw (- hh) id] [iw (- ih) hd] [(- iw) (- ih) hd] [0.0 (- diag) diag]]
               [[iw (- hh) (- id)] [(- iw) (- hh) (- id)] [(- iw) (- ih) (- hd)] [iw (- ih) (- hd)] [0.0 (- diag) (- diag)]]
               [[iw (- ih) hd] [hw (- ih) id] [hw ih id] [iw ih hd] [diag 0.0 diag]]
               [[hw (- ih) (- id)] [iw (- ih) (- hd)] [iw ih (- hd)] [hw ih (- id)] [diag 0.0 (- diag)]]
               [[(- hw) (- ih) id] [(- iw) (- ih) hd] [(- iw) ih hd] [(- hw) ih id] [(- diag) 0.0 diag]]
               [[(- iw) (- ih) (- hd)] [(- hw) (- ih) (- id)] [(- hw) ih (- id)] [(- iw) ih (- hd)] [(- diag) 0.0 (- diag)]]]]
    (reduce (fn [mesh [p0 p1 p2 p3 n]] (add-quad mesh p0 p1 p2 p3 n)) [[] []] steps)))

(defn offset-mesh
  "Return a new mesh with `[dx dy dz]` added to every vertex position (pure;
  original mutated `&mut (Vec<f32>, Vec<u32>)` in place). Mirrors `offset_mesh`."
  [[vertices indices] dx dy dz]
  (let [n (quot (count vertices) 8)
        vertices' (reduce (fn [v i]
                             (let [base (* i 8)]
                               (-> v
                                   (update base + dx)
                                   (update (+ base 1) + dy)
                                   (update (+ base 2) + dz))))
                           vertices (range n))]
    [vertices' indices]))

(defn scale-mesh
  "Return a new mesh with every vertex position scaled by `[sx sy sz]`
  (normals untouched, matching the original). Mirrors `scale_mesh`."
  [[vertices indices] sx sy sz]
  (let [n (quot (count vertices) 8)
        vertices' (reduce (fn [v i]
                             (let [base (* i 8)]
                               (-> v
                                   (update base * sx)
                                   (update (+ base 1) * sy)
                                   (update (+ base 2) * sz))))
                           vertices (range n))]
    [vertices' indices]))

(defn- swap-xy-mesh
  "Swap X/Y of position and normal for every vertex — used to rotate a
  Y-axis cylinder to lie along X. Local equivalent of the anonymous block in
  `dumbbell_mesh` that swaps `v[i*8]`/`v[i*8+1]` and `v[i*8+3]`/`v[i*8+4]`."
  [[vertices indices]]
  (let [n (quot (count vertices) 8)
        vertices' (reduce (fn [v i]
                             (let [base (* i 8)
                                   px (nth v base) py (nth v (inc base))
                                   nx (nth v (+ base 3)) ny (nth v (+ base 4))]
                               (-> v
                                   (assoc base py) (assoc (inc base) px)
                                   (assoc (+ base 3) ny) (assoc (+ base 4) nx))))
                           vertices (range n))]
    [vertices' indices]))

;; ---------------------------------------------------------------------------
;; Public mesh generators
;; ---------------------------------------------------------------------------

(defn toilet-mesh
  "Giant Skibidi Toilet: bowl (squashed sphere) + tank (rounded box) + seat
  ring (torus quads) + lid (disc). Mirrors `toilet_mesh`."
  []
  (let [segs 16
        bowl (scale-mesh (sphere-mesh segs segs 1.2 0.0 0.0 0.0) 1.0 0.6 1.0)
        tank (offset-mesh (rounded-box 1.0 1.8 0.8 0.1) 0.0 0.5 -1.1)
        ring-segs 24 ring-r-major 1.0 ring-r-minor 0.12
        ring-verts (vec (apply concat
                          (for [i (range (inc ring-segs))
                                :let [theta (* 2.0 PI (/ (double i) ring-segs))
                                      ct (cos* theta) st (sin* theta)]
                                j (range 9)
                                :let [phi (* 2.0 PI (/ (double j) 8.0))
                                      cp (cos* phi) sp (sin* phi)
                                      x (* (+ ring-r-major (* ring-r-minor cp)) ct)
                                      z (* (+ ring-r-major (* ring-r-minor cp)) st)
                                      y (* ring-r-minor sp)
                                      nx (* cp ct) nz (* cp st) ny sp]]
                            [x (+ y 0.65) z nx ny nz (/ (double i) ring-segs) (/ (double j) 8.0)])))
        tube-ring 9
        ring-idxs (vec (apply concat
                         (for [i (range ring-segs) j (range 8)
                               :let [a (+ (* i tube-ring) j) b (+ a tube-ring)]]
                           [a b (inc a) (inc a) b (inc b)])))
        seat [ring-verts ring-idxs]
        lid-segs 16
        lid-center 0
        lid-verts0 [0.0 0.85 0.0 0.0 1.0 0.0 0.5 0.5]
        lid-ring (vec (apply concat
                        (for [j (range (inc lid-segs))
                              :let [theta (* 2.0 PI (/ (double j) lid-segs))
                                    x (* (cos* theta) 0.95) z (* (sin* theta) 0.95)]]
                          [x 0.85 z 0.0 1.0 0.0 (+ 0.5 (* 0.5 (cos* theta))) (+ 0.5 (* 0.5 (sin* theta)))])))
        lid-verts (into lid-verts0 lid-ring)
        lid-idxs (vec (apply concat (for [j (range lid-segs)] [lid-center (+ lid-center 1 j) (+ lid-center 2 j)])))
        lid [lid-verts lid-idxs]]
    (merge-meshes [bowl tank seat lid])))

(defn character-mesh
  "Nintendo Mii-style character body from primitives. `body-build` is one of
  \"slim\"/\"average\"/\"stocky\"/\"athletic\"/\"tall\". `height` is an overall
  scale factor. Mirrors `character_mesh`."
  [body-build height]
  (let [segs 12
        [body-w body-h] (case body-build
                           "slim" [0.25 0.5]
                           "stocky" [0.45 0.45]
                           "athletic" [0.35 0.55]
                           "tall" [0.3 0.65]
                           [0.35 0.5])
        head-r 0.3
        head (sphere-mesh segs segs head-r 0.0 (+ body-h head-r 0.05) 0.0)
        body (capsule body-w (* body-h 0.5) segs)
        arm-r 0.08 arm-h 0.35
        left-arm (offset-mesh (cylinder-mesh segs arm-r (* arm-h 0.5) 0.0 0.0 0.0)
                               (- (+ body-w arm-r 0.05)) (* body-h 0.2) 0.0)
        right-arm (offset-mesh (cylinder-mesh segs arm-r (* arm-h 0.5) 0.0 0.0 0.0)
                                (+ body-w arm-r 0.05) (* body-h 0.2) 0.0)
        leg-r 0.1 leg-h 0.4
        left-leg (offset-mesh (cylinder-mesh segs leg-r (* leg-h 0.5) 0.0 0.0 0.0)
                               (* body-w -0.5) (- (+ (* body-h 0.5) (* leg-h 0.5) 0.05)) 0.0)
        right-leg (offset-mesh (cylinder-mesh segs leg-r (* leg-h 0.5) 0.0 0.0 0.0)
                                (* body-w 0.5) (- (+ (* body-h 0.5) (* leg-h 0.5) 0.05)) 0.0)]
    (scale-mesh (merge-meshes [head body left-arm right-arm left-leg right-leg]) height height height)))

(defn dumbbell-mesh
  "Sigma Gym dumbbell: two spheres connected by a thin bar. Mirrors `dumbbell_mesh`."
  []
  (let [segs 12 weight-r 0.4 bar-r 0.08 bar-half 0.7
        left-weight (sphere-mesh segs segs weight-r (- bar-half) 0.0 0.0)
        right-weight (sphere-mesh segs segs weight-r bar-half 0.0 0.0)
        bar (swap-xy-mesh (cylinder-mesh segs bar-r bar-half 0.0 0.0 0.0))]
    (merge-meshes [left-weight right-weight bar])))

(defn obelisk-mesh
  "Ohio Obelisk: tall tapered box + glowing sphere on top. Mirrors `obelisk_mesh`."
  []
  (let [base-w 1.0 top-w 0.4 h 4.0 depth 0.8 top-d 0.35
        bw (* base-w 0.5) tw (* top-w 0.5) bd (* depth 0.5) td (* top-d 0.5)
        steps [[[(- bw) 0.0 bd] [bw 0.0 bd] [tw h td] [(- tw) h td] [0.0 0.0 1.0]]
               [[bw 0.0 (- bd)] [(- bw) 0.0 (- bd)] [(- tw) h (- td)] [tw h (- td)] [0.0 0.0 -1.0]]
               [[bw 0.0 bd] [bw 0.0 (- bd)] [tw h (- td)] [tw h td] [1.0 0.0 0.0]]
               [[(- bw) 0.0 (- bd)] [(- bw) 0.0 bd] [(- tw) h td] [(- tw) h (- td)] [-1.0 0.0 0.0]]
               [[(- tw) h td] [tw h td] [tw h (- td)] [(- tw) h (- td)] [0.0 1.0 0.0]]]
        obelisk (reduce (fn [mesh [p0 p1 p2 p3 n]] (add-quad mesh p0 p1 p2 p3 n)) [[] []] steps)
        orb (sphere-mesh 10 10 0.3 0.0 (+ h 0.5) 0.0)]
    (merge-meshes [obelisk orb])))

(defn blob-mesh
  "Grimace Blob: distorted sphere using sine-wave displacement. `wobble-phase`
  (0.0-1.0) creates different wobble shapes. Mirrors `blob_mesh`."
  [wobble-phase]
  (let [stacks 20 slices 20 base-radius 1.0 wobble-amp 0.15
        phase (* wobble-phase 2.0 PI)
        vertices (vec (apply concat
                        (for [i (range (inc stacks))
                              :let [phi (* PI (/ (double i) stacks))
                                    y (cos* phi) r (sin* phi)]
                              j (range (inc slices))
                              :let [theta (* 2.0 PI (/ (double j) slices))
                                    nx (* r (cos* theta)) nz (* r (sin* theta)) ny y
                                    displacement (* wobble-amp
                                                     (+ (* (sin* (+ (* 3.0 phi) phase)) 0.5)
                                                        (* (sin* (+ (* 2.0 theta) (* phase 1.3))) 0.3)
                                                        (* (sin* (+ (* 4.0 phi) (* 3.0 theta) (* phase 0.7))) 0.2)))
                                    radius (+ base-radius displacement)]]
                          [(* nx radius) (* ny radius) (* nz radius)
                           nx ny nz
                           (/ (double j) slices) (/ (double i) stacks)])))
        ring (inc slices)
        indices (vec (apply concat
                       (for [i (range stacks) j (range slices)
                             :let [a (+ (* i ring) j) b (+ a ring)]]
                         [a b (inc a) (inc a) b (inc b)])))]
    [vertices indices]))

(defn food-crate-mesh
  "Fanum Food Crate: rounded box with slightly bulging sides. Mirrors `food_crate_mesh`."
  []
  (let [[vertices indices] (rounded-box 1.2 0.8 1.0 0.08)
        n (quot (count vertices) 8)
        vertices' (reduce
                    (fn [v i]
                      (let [base (* i 8)
                            px (nth v base) py (nth v (inc base)) pz (nth v (+ base 2))
                            center-factor-y (- 1.0 (min 1.0 (/ (abs* py) 0.4)))
                            bulge (* 0.03 center-factor-y)
                            len-xz (sqrt* (+ (* px px) (* pz pz)))]
                        (if (> len-xz 0.01)
                          (-> v
                              (update base + (* (/ px len-xz) bulge))
                              (update (+ base 2) + (* (/ pz len-xz) bulge)))
                          v)))
                    vertices (range n))]
    [vertices' indices]))

(defn orb-mesh
  "Gyatt/Item Orb: sphere with sparkle/pulse displacement. `pulse-phase`
  (0.0-1.0) scales radius between 0.9-1.1. Mirrors `orb_mesh`."
  [pulse-phase]
  (let [stacks 16 slices 16 base-radius 0.5
        phase (* pulse-phase 2.0 PI)
        pulse-scale (+ 1.0 (* 0.1 (sin* phase)))
        vertices (vec (apply concat
                        (for [i (range (inc stacks))
                              :let [phi (* PI (/ (double i) stacks)) y (cos* phi) r (sin* phi)]
                              j (range (inc slices))
                              :let [theta (* 2.0 PI (/ (double j) slices))
                                    nx (* r (cos* theta)) nz (* r (sin* theta)) ny y
                                    sparkle (* 0.02 (+ (* (sin* (+ (* 5.0 theta) (* 3.0 phi))) 0.7)
                                                        (* (sin* (- (+ (* 7.0 theta) phase) (* 2.0 phi))) 0.3)))
                                    radius (+ (* base-radius pulse-scale) sparkle)]]
                          [(* nx radius) (* ny radius) (* nz radius) nx ny nz
                           (/ (double j) slices) (/ (double i) stacks)])))
        ring (inc slices)
        indices (vec (apply concat (for [i (range stacks) j (range slices)
                                          :let [a (+ (* i ring) j) b (+ a ring)]]
                                      [a b (inc a) (inc a) b (inc b)])))]
    [vertices indices]))

(defn torii-gate-mesh
  "Torii Gate: two vertical pillars + two horizontal beams. Mirrors `torii_gate_mesh`."
  []
  (let [segs 12 pillar-r 0.15 pillar-h 3.0 gate-w 3.0 beam-h 0.2 beam-d 0.25
        left-pillar (cylinder-mesh segs pillar-r (* pillar-h 0.5) (* -0.5 gate-w) (* pillar-h 0.5) 0.0)
        right-pillar (cylinder-mesh segs pillar-r (* pillar-h 0.5) (* 0.5 gate-w) (* pillar-h 0.5) 0.0)
        top-beam (offset-mesh (rounded-box (+ gate-w 0.6) beam-h beam-d 0.04) 0.0 (+ pillar-h (* beam-h 0.5)) 0.0)
        lower-beam (offset-mesh (rounded-box (* gate-w 0.9) (* beam-h 0.7) (* beam-d 0.8) 0.03) 0.0 (* pillar-h 0.75) 0.0)]
    (merge-meshes [left-pillar right-pillar top-beam lower-beam])))

;; ---------------------------------------------------------------------------
;; Brainrot Evolution — Pokemon-style multi-stage model transforms
;; ---------------------------------------------------------------------------

(def brainrot-characters
  "Brainrot character identifiers for evolution mesh dispatch. Mirrors enum
  `BrainrotCharacter`."
  #{:skibidi :sigma :ohio :grimace :rizz :fanum})

(defn max-stage
  "Mirrors `BrainrotCharacter::max_stage`."
  [character]
  (case character
    :skibidi 3
    :sigma 4
    :ohio 2
    :grimace 3
    :rizz 2
    :fanum 3))

(def ^:private stage-names
  {[:skibidi 0] "Mini Toilet" [:skibidi 1] "Skibidi Soldier" [:skibidi 2] "Skibidi Tank" [:skibidi 3] "Skibidi Titan"
   [:sigma 0] "Scrawny Kid" [:sigma 1] "Gym Bro" [:sigma 2] "Sigma Male" [:sigma 3] "Gigachad" [:sigma 4] "Sigma Ascended"
   [:ohio 0] "Ohio Anomaly" [:ohio 1] "Ohio Nightmare" [:ohio 2] "Ohio Eldritch"
   [:grimace 0] "Purple Puddle" [:grimace 1] "Grimace Blob" [:grimace 2] "Grimace Tide" [:grimace 3] "Grimace Singularity"
   [:rizz 0] "Awkward Kid" [:rizz 1] "Rizz Master" [:rizz 2] "Rizz Sensei"
   [:fanum 0] "Street Kid" [:fanum 1] "Tax Collector" [:fanum 2] "Tax Baron" [:fanum 3] "Fanum Mogul"})

(defn stage-name
  "Mirrors `BrainrotCharacter::stage_name`."
  [character stage]
  (get stage-names [character stage] "Unknown"))

(def ^:private stage-scales
  {[:skibidi 0] 0.6 [:skibidi 1] 1.0 [:skibidi 2] 1.8 [:skibidi 3] 3.0
   [:sigma 0] 0.7 [:sigma 1] 1.0 [:sigma 2] 1.1 [:sigma 3] 1.3 [:sigma 4] 1.5
   [:ohio 0] 1.0 [:ohio 1] 2.0 [:ohio 2] 4.0
   [:grimace 0] 0.5 [:grimace 1] 1.0 [:grimace 2] 1.8 [:grimace 3] 2.5
   [:rizz 0] 0.8 [:rizz 1] 1.0 [:rizz 2] 1.1
   [:fanum 0] 0.8 [:fanum 1] 1.0 [:fanum 2] 1.1 [:fanum 3] 1.4})

(defn stage-scale
  "Mirrors `BrainrotCharacter::stage_scale`."
  [character stage]
  (get stage-scales [character stage] 1.0))

(defn- skibidi-evolution-mesh
  "Skibidi: Mini Toilet(0) -> Soldier(1) -> Tank(2) -> Titan(3)."
  [stage]
  (case stage
    0 (let [t (scale-mesh (toilet-mesh) 0.6 0.6 0.6)
            leg-l (cylinder-mesh 8 0.08 0.15 -0.15 -0.4 0.0)
            leg-r (cylinder-mesh 8 0.08 0.15 0.15 -0.4 0.0)]
        (merge-meshes [t leg-l leg-r]))
    1 (let [t (toilet-mesh)
            torso (offset-mesh (character-mesh "stocky" 0.7) 0.0 0.8 0.0)]
        (merge-meshes [t torso]))
    2 (let [base (scale-mesh (toilet-mesh) 2.0 2.0 2.0)
            cams (for [i (range 4) :let [angle (* i (/ PI 2))]]
                   (sphere-mesh 8 12 0.25 (* (cos* angle) 1.2) 1.8 (* (sin* angle) 1.2)))
            tread-l (offset-mesh (rounded-box 2.0 0.3 0.4 0.05) -1.5 -0.8 0.0)
            tread-r (offset-mesh (rounded-box 2.0 0.3 0.4 0.05) 1.5 -0.8 0.0)]
        (merge-meshes (concat [base tread-l tread-r] cams)))
    (let [base (scale-mesh (toilet-mesh) 3.0 3.0 3.0)
          towers (for [i (range 4) :let [angle (* i (/ PI 2))]]
                   (offset-mesh (scale-mesh (obelisk-mesh) 0.5 0.6 0.5)
                                (* (cos* angle) 2.5) 0.0 (* (sin* angle) 2.5)))
          heads (for [i (range 8) :let [angle (* i (/ PI 4.0))]]
                  (sphere-mesh 8 12 0.3 (* (cos* angle) 3.5) 4.0 (* (sin* angle) 3.5)))]
      (merge-meshes (concat [base] towers heads)))))

(defn- sigma-evolution-mesh
  "Sigma: Scrawny Kid(0) -> Gym Bro(1) -> Sigma Male(2) -> Gigachad(3) -> Ascended(4)."
  [stage]
  (case stage
    0 (character-mesh "slim" 0.85)
    1 (let [body (character-mesh "athletic" 1.0)
            db (offset-mesh (scale-mesh (dumbbell-mesh) 0.6 0.6 0.6) 0.5 0.2 0.0)]
        (merge-meshes [body db]))
    2 (let [body (character-mesh "athletic" 1.1)
            bar (cylinder-mesh 12 0.04 0.8 0.0 0.8 0.0)
            w-l (sphere-mesh 10 10 0.25 -0.8 0.8 0.0)
            w-r (sphere-mesh 10 10 0.25 0.8 0.8 0.0)]
        (merge-meshes [body bar w-l w-r]))
    3 (let [body (character-mesh "stocky" 1.3)
            jaw (offset-mesh (rounded-box 0.5 0.15 0.3 0.03) 0.0 0.85 0.15)
            throne (offset-mesh (rounded-box 1.5 2.0 1.0 0.1) 0.0 0.0 -0.8)]
        (merge-meshes [body jaw throne]))
    (let [body (character-mesh "tall" 1.5)
          orbs (for [i (range 6) :let [angle (* i (/ PI 3.0))]]
                 (offset-mesh (orb-mesh (/ (double i) 6.0)) (* (cos* angle) 1.0) (+ 1.0 (* i 0.15)) (* (sin* angle) 1.0)))
          plates (for [i (range 4) :let [angle (* i (/ PI 2))]]
                   (offset-mesh (rounded-box 0.4 0.8 0.05 0.02) (* (cos* angle) 0.6) 0.3 (* (sin* angle) 0.6)))]
      (merge-meshes (concat [body] orbs plates)))))

(defn- ohio-evolution-mesh
  "Ohio: Anomaly(0) -> Nightmare(1) -> Eldritch(2)."
  [stage phase]
  (case stage
    0 (let [ob (obelisk-mesh)
            cubes (for [i (range 6) :let [angle (* i (/ PI 3.0))]]
                    (offset-mesh (rounded-box 0.6 0.6 0.6 0.05) (* (cos* angle) 2.5) (+ 1.5 (* i 0.4)) (* (sin* angle) 2.5)))]
        (merge-meshes (concat [ob] cubes)))
    1 (let [ob1 (obelisk-mesh)
            ob2 (offset-mesh (scale-mesh (obelisk-mesh) 0.8 0.8 0.8) 1.0 0.0 0.5)
            ob3 (offset-mesh (scale-mesh (obelisk-mesh) 0.7 0.7 0.7) -0.8 0.0 -0.6)
            eye (sphere-mesh 12 12 0.5 0.0 5.0 0.0)
            tentacles (for [i (range 4) :let [angle (* i (/ PI 2))]]
                        (offset-mesh (capsule 0.12 1.5 10) (* (cos* angle) 1.5) 2.0 (* (sin* angle) 1.5)))]
        (scale-mesh (merge-meshes (concat [ob1 ob2 ob3 eye] tentacles)) 2.0 2.0 2.0))
    (let [core (scale-mesh (obelisk-mesh) 1.5 1.5 1.5)
          sub-obs (for [i (range 6) :let [angle (* i (/ PI 3.0))]]
                    (offset-mesh (scale-mesh (obelisk-mesh) 0.4 0.5 0.4) (* (cos* angle) 3.0) 0.0 (* (sin* angle) 3.0)))
          gate (offset-mesh (scale-mesh (torii-gate-mesh) 1.5 1.2 1.5) 0.0 2.0 0.0)
          orbs-pos (for [i (range 12) :let [angle (* i (/ PI 6.0))]]
                     (offset-mesh (orb-mesh (+ phase (/ (double i) 12.0))) (* (cos* angle) 4.0) (+ 3.0 (* i 0.2)) (* (sin* angle) 4.0)))]
      (scale-mesh (merge-meshes (concat [core gate] sub-obs orbs-pos)) 2.0 2.0 2.0))))

(defn- grimace-evolution-mesh
  "Grimace: Purple Puddle(0) -> Blob(1) -> Tide(2) -> Singularity(3)."
  [stage phase]
  (case stage
    0 (scale-mesh (blob-mesh 0.0) 1.0 0.3 1.0)
    1 (let [b (blob-mesh phase)
            eye-l (sphere-mesh 8 8 0.15 -0.3 0.7 0.5)
            eye-r (sphere-mesh 8 8 0.15 0.3 0.7 0.5)]
        (merge-meshes [b eye-l eye-r]))
    2 (let [main (scale-mesh (blob-mesh phase) 1.8 1.8 1.8)
            sats (for [i (range 4) :let [angle (* i (/ PI 2))]]
                   (offset-mesh (scale-mesh (blob-mesh (+ phase (* i 0.25))) 0.4 0.4 0.4)
                                (* (cos* angle) 2.5) 0.5 (* (sin* angle) 2.5)))]
        (merge-meshes (concat [main] sats)))
    (let [shell-scaled (scale-mesh (blob-mesh phase) 2.5 2.5 2.5)
          core-pos (scale-mesh (orb-mesh phase) 0.8 0.8 0.8)
          arms (for [i (range 8) :let [angle (* i (/ PI 4.0))]]
                 (offset-mesh (capsule 0.1 1.2 8) (* (cos* angle) 2.0) 0.0 (* (sin* angle) 2.0)))
          particles (for [i (range 20)
                          :let [angle (+ (* i (/ PI 10.0)) (* phase PI))
                                r (+ 1.5 (* i 0.1))
                                y (* (sin* (* i 0.3)) 1.5)]]
                      (sphere-mesh 4 4 0.06 (* (cos* angle) r) y (* (sin* angle) r)))]
      (merge-meshes (concat [shell-scaled core-pos] arms particles)))))

(defn- rizz-evolution-mesh
  "Rizz: Awkward Kid(0) -> Rizz Master(1) -> Rizz Sensei(2)."
  [stage]
  (case stage
    0 (character-mesh "slim" 0.8)
    1 (let [body (character-mesh "slim" 1.05)
            earring (sphere-mesh 6 6 0.04 0.35 0.85 0.0)
            sparkles (for [i (range 4) :let [angle (* i (/ PI 2))]]
                       (offset-mesh (scale-mesh (orb-mesh (/ (double i) 4.0)) 0.2 0.2 0.2)
                                    (* (cos* angle) 0.6) 1.2 (* (sin* angle) 0.6)))]
        (merge-meshes (concat [body earring] sparkles)))
    (let [body (character-mesh "slim" 1.1)
          robe-panels (for [i (range 4) :let [angle (* i (/ PI 2))]]
                        (offset-mesh (rounded-box 0.4 0.8 0.05 0.02) (* (cos* angle) 0.4) -0.1 (* (sin* angle) 0.4)))
          crown (offset-mesh (scale-mesh (torii-gate-mesh) 0.15 0.1 0.15) 0.0 1.3 0.0)
          scroll-l (offset-mesh (rounded-box 0.15 0.3 0.08 0.02) -0.6 0.5 0.0)
          scroll-r (offset-mesh (rounded-box 0.15 0.3 0.08 0.02) 0.6 0.5 0.0)]
      (merge-meshes (concat [body crown scroll-l scroll-r] robe-panels)))))

(defn- fanum-evolution-mesh
  "Fanum: Street Kid(0) -> Tax Collector(1) -> Tax Baron(2) -> Fanum Mogul(3)."
  [stage]
  (case stage
    0 (let [body (character-mesh "average" 0.85)
            crate1 (offset-mesh (scale-mesh (food-crate-mesh) 0.4 0.4 0.4) 0.4 0.2 0.0)]
        (merge-meshes [body crate1]))
    1 (let [body (character-mesh "average" 1.0)
            crates (for [i (range 3)]
                     (offset-mesh (scale-mesh (food-crate-mesh) 0.35 0.35 0.35) 0.0 (+ 0.1 (* i 0.3)) -0.35))]
        (merge-meshes (concat [body] crates)))
    2 (let [body (character-mesh "stocky" 1.1)
            cart (offset-mesh (rounded-box 1.5 0.4 0.8 0.05) 0.0 0.3 -0.8)
            crates (for [i (range 8)
                         :let [col (double (mod i 4)) row (double (quot i 4))]]
                     (offset-mesh (scale-mesh (food-crate-mesh) 0.25 0.25 0.25)
                                  (+ -0.5 (* col 0.35)) (+ 0.55 (* row 0.22)) -0.8))
            wheel-l (cylinder-mesh 12 0.15 0.05 -0.7 0.15 -0.8)
            wheel-r (cylinder-mesh 12 0.15 0.05 0.7 0.15 -0.8)]
        (merge-meshes (concat [body cart wheel-l wheel-r] crates)))
    (let [body (character-mesh "stocky" 1.4)
          throne (offset-mesh (rounded-box 1.8 2.2 1.2 0.1) 0.0 0.0 -0.5)
          crates (for [i (range 12) :let [angle (* i (/ PI 6.0))]]
                   (offset-mesh (scale-mesh (food-crate-mesh) 0.3 0.3 0.3)
                                (* (cos* angle) 2.2) (+ 0.8 (* (sin* (* i 0.1)) 0.3)) (* (sin* angle) 2.2)))
          gate (offset-mesh (scale-mesh (torii-gate-mesh) 0.8 0.7 0.8) 0.0 0.0 2.0)]
      (merge-meshes (concat [body throne gate] crates)))))

(defn brainrot-evolution-mesh
  "Stage-aware mesh generator for all brainrot characters. `phase` is an
  animation phase (0.0-1.0) for wobble/pulse/orbit effects. Mirrors
  `brainrot_evolution_mesh` (stage clamped to `max-stage`)."
  [character stage phase]
  (let [stage (min stage (max-stage character))]
    (case character
      :skibidi (skibidi-evolution-mesh stage)
      :sigma (sigma-evolution-mesh stage)
      :ohio (ohio-evolution-mesh stage phase)
      :grimace (grimace-evolution-mesh stage phase)
      :rizz (rizz-evolution-mesh stage)
      :fanum (fanum-evolution-mesh stage))))

;; ---------------------------------------------------------------------------
;; Goriketsu Dash!! creature meshes
;; ---------------------------------------------------------------------------

(defn gorilla-mesh
  "Gorilla mesh — organic body for Goriketsu Dash!!, massive silverback with
  an oversized red butt. `anger-phase` (0.0-1.0) controls chest expansion +
  butt pulsation. Mirrors `gorilla_mesh`."
  [anger-phase]
  (let [chest-expand (+ 1.0 (* anger-phase 0.15))
        butt-pulse (+ 1.0 (* (abs* (sin* (* anger-phase PI 2.0))) 0.2))
        torso (sphere-mesh 12 16 (* 1.8 chest-expand) 0.0 2.0 0.0)
        belly (sphere-mesh 10 14 (* 1.2 chest-expand) 0.0 1.5 0.5)
        head (sphere-mesh 12 16 0.9 0.0 3.8 0.3)
        crest (offset-mesh (rounded-box 0.3 0.6 0.8 0.08) 0.0 4.3 0.2)
        brow (offset-mesh (rounded-box 0.7 0.15 0.3 0.04) 0.0 3.95 0.9)
        arm-l-upper (offset-mesh (capsule 0.45 1.2 12) -1.8 2.5 0.0)
        arm-l-fore (offset-mesh (capsule 0.35 1.0 10) -2.3 1.2 0.0)
        fist-l (sphere-mesh 8 10 0.4 -2.4 0.35 0.2)
        arm-r-upper (offset-mesh (capsule 0.45 1.2 12) 1.8 2.5 0.0)
        arm-r-fore (offset-mesh (capsule 0.35 1.0 10) 2.3 1.2 0.0)
        fist-r (sphere-mesh 8 10 0.4 2.4 0.35 0.2)
        leg-l (offset-mesh (capsule 0.4 0.7 10) -0.7 0.7 0.0)
        leg-r (offset-mesh (capsule 0.4 0.7 10) 0.7 0.7 0.0)
        foot-l (offset-mesh (rounded-box 0.35 0.15 0.5 0.05) -0.7 0.15 0.3)
        foot-r (offset-mesh (rounded-box 0.35 0.15 0.5 0.05) 0.7 0.15 0.3)
        butt-r (* 1.1 butt-pulse)
        butt-l-cheek (sphere-mesh 12 16 butt-r -0.4 1.0 -1.0)
        butt-r-cheek (sphere-mesh 12 16 butt-r 0.4 1.0 -1.0)]
    (merge-meshes [torso belly head crest brow arm-l-upper arm-l-fore fist-l
                   arm-r-upper arm-r-fore fist-r leg-l leg-r foot-l foot-r
                   butt-l-cheek butt-r-cheek])))

(defn baby-gorilla-mesh
  "Baby gorilla mesh — cute small version with big eyes. Mirrors `baby_gorilla_mesh`."
  []
  (let [body (sphere-mesh 10 12 0.5 0.0 0.7 0.0)
        head (sphere-mesh 10 12 0.4 0.0 1.3 0.1)
        eye-l (sphere-mesh 6 8 0.12 -0.15 1.4 0.4)
        eye-r (sphere-mesh 6 8 0.12 0.15 1.4 0.4)
        arm-l (offset-mesh (capsule 0.12 0.3 8) -0.5 0.8 0.0)
        arm-r (offset-mesh (capsule 0.12 0.3 8) 0.5 0.8 0.0)
        leg-l (offset-mesh (capsule 0.1 0.2 8) -0.2 0.25 0.0)
        leg-r (offset-mesh (capsule 0.1 0.2 8) 0.2 0.25 0.0)]
    (merge-meshes [body head eye-l eye-r arm-l arm-r leg-l leg-r])))

(defn banana-mesh
  "Banana mesh — curved yellow fruit. Mirrors `banana_mesh`."
  []
  (let [body (capsule 0.12 0.6 10)
        tip (sphere-mesh 6 6 0.06 0.15 0.62 0.0)
        stem (cylinder-mesh 6 0.03 0.08 -0.12 0.02 0.0)]
    (merge-meshes [body tip stem])))
