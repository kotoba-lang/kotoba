(ns character.base-mesh
  "Base head mesh generation — FLAME-compatible topology with facial
  features. Restored from the legacy kami-engine/kami-character Rust
  crate's `base_mesh.rs` (deleted in kotoba-lang/kami-engine PR #82)
  as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root)."
  (:require [character.math :as m]))

(defn generate-head
  "Generate base head mesh with facial feature deformations. Returns
  `{:vertices [Vec3 ...] :indices [int ...]}` (normals/UVs computed
  separately)."
  [n-lat n-lon]
  (let [nl (double n-lat)
        nln (double n-lon)
        verts
        (vec
         (for [i (range (inc n-lat))
               :let [phi (* m/pi (/ i nl))
                     y (m/cos phi)
                     sin-phi (m/sin phi)]
               j (range (inc n-lon))]
           (let [theta (* 2.0 m/pi (/ j nln))
                 cos-t (m/cos theta)
                 sin-t (m/sin theta)
                 rx0 0.09
                 ry 0.12
                 rz0 0.08
                 y-pos (* ry y)
                 chin (if (< y -0.3) (/ (+ y 0.3) -0.7) 0.0)
                 rx1 (* rx0 (- 1.0 (* 0.35 chin)))
                 rz1 (* rz0 (- 1.0 (* 0.25 chin)))
                 cheek (* (max 0.0 (- 1.0 (Math/pow (/ (- y 0.0) 0.25) 2))) (max cos-t 0.0))
                 rx (+ rx1 (* 0.008 cheek))
                 x0 (* rx sin-phi cos-t)
                 z0 (* rz1 sin-phi sin-t)
                 front (max sin-t 0.0)
                 nose-y (max 0.0 (- 1.0 (Math/pow (/ (- y-pos 0.02) 0.03) 2)))
                 nose-x (max 0.0 (- 1.0 (Math/pow (/ x0 0.015) 2)))
                 z1 (+ z0 (* nose-y nose-x front 0.025))
                 nose-tip-y (max 0.0 (- 1.0 (Math/pow (/ (+ y-pos 0.005) 0.012) 2)))
                 nose-tip-x (max 0.0 (- 1.0 (Math/pow (/ x0 0.012) 2)))
                 z2 (+ z1 (* nose-tip-y nose-tip-x front 0.018))
                 z3 (reduce
                     (fn [z nx-off]
                       (let [nd (m/sqrt (+ (Math/pow (- x0 nx-off) 2) (Math/pow (+ y-pos 0.012) 2)))]
                         (if (< nd 0.006)
                           (- z (* (- 1.0 (Math/pow (/ nd 0.006) 2)) 0.003 front))
                           z)))
                     z2 [-0.008 0.008])
                 z4 (reduce
                     (fn [z ex]
                       (let [ed (m/sqrt (+ (Math/pow (- x0 ex) 2) (Math/pow (- y-pos 0.045) 2)))]
                         (if (< ed 0.02)
                           (- z (* (- 1.0 (Math/pow (/ ed 0.02) 2)) 0.01 front))
                           z)))
                     z3 [-0.032 0.032])
                 brow (max 0.0 (- 1.0 (Math/pow (/ (- y-pos 0.07) 0.012) 2)))
                 z5 (+ z4 (* brow front 0.007))
                 lip-y (max 0.0 (- 1.0 (Math/pow (/ (+ y-pos 0.035) 0.012) 2)))
                 lip-x (max 0.0 (- 1.0 (Math/pow (/ x0 0.025) 2)))
                 z6 (+ z5 (* lip-y lip-x front 0.01))
                 ph-y (max 0.0 (- 1.0 (Math/pow (/ (+ y-pos 0.015) 0.008) 2)))
                 ph-x (max 0.0 (- 1.0 (Math/pow (/ x0 0.008) 2)))
                 z7 (- z6 (* ph-y ph-x front 0.005))
                 ll (max 0.0 (- 1.0 (Math/pow (/ (+ y-pos 0.05) 0.008) 2)))
                 z8 (- z7 (* ll (max 0.0 (- 1.0 (Math/pow (/ x0 0.02) 2))) front 0.004))
                 ct (max 0.0 (- 1.0 (Math/pow (/ (+ y-pos 0.10) 0.02) 2)))
                 z9 (+ z8 (* ct (max 0.0 (- 1.0 (Math/pow (/ x0 0.02) 2))) front 0.008))
                 z10 (if (> y-pos 0.06) (+ z9 (* (/ (- y-pos 0.06) 0.06) front 0.006)) z9)
                 [x11 z11]
                 (reduce
                  (fn [[x z] ear-side]
                    (let [ear-theta (if (pos? ear-side) (/ m/pi 2.0) (* 3.0 (/ m/pi 2.0)))
                          diff0 (Math/abs (double (- theta ear-theta)))
                          angle-diff (if (> diff0 m/pi) (- (* 2.0 m/pi) diff0) diff0)]
                      (if (< angle-diff 0.35)
                        (let [ear-y (Math/abs (double (/ (- y-pos 0.035) 0.03)))]
                          (if (< ear-y 1.0)
                            (let [bulge (* (- 1.0 (Math/pow (/ angle-diff 0.35) 2)) (- 1.0 (Math/pow ear-y 2)))]
                              [(+ x (* ear-side bulge 0.015)) (- z (* bulge 0.005))])
                            [x z]))
                        [x z])))
                  [x0 z10] [-1.0 1.0])]
             [x11 y-pos z11])))
        indices
        (vec
         (mapcat
          (fn [i]
            (mapcat
             (fn [j]
               (let [a (+ (* i (inc n-lon)) j)
                     b (+ a n-lon 1)]
                 [a b (inc a) (inc a) b (inc b)]))
             (range n-lon)))
          (range n-lat)))]
    {:vertices verts :indices indices}))

(defn compute-normals
  "Compute smooth vertex normals from triangle faces."
  [verts indices]
  (let [n (count verts)
        norms (object-array (repeat n m/vec3-zero))]
    (doseq [[i0 i1 i2] (partition 3 indices)]
      (let [v0 (nth verts i0) v1 (nth verts i1) v2 (nth verts i2)
            e1 (m/vec3- v1 v0)
            e2 (m/vec3- v2 v0)
            fnorm (m/vec3-cross e1 e2)]
        (aset norms i0 (m/vec3+ (aget norms i0) fnorm))
        (aset norms i1 (m/vec3+ (aget norms i1) fnorm))
        (aset norms i2 (m/vec3+ (aget norms i2) fnorm))))
    (mapv m/vec3-normalize-or-zero (seq norms))))

(defn laplacian-smooth
  "Laplacian smoothing. Returns smoothed vertices."
  [verts indices iterations factor]
  (let [n (count verts)
        adj (object-array (repeat n []))]
    (doseq [[a b c] (partition 3 indices)]
      (aset adj a (conj (aget adj a) b c))
      (aset adj b (conj (aget adj b) a c))
      (aset adj c (conj (aget adj c) a b)))
    (loop [iter 0 verts (vec verts)]
      (if (= iter iterations)
        verts
        (let [prev verts
              next-verts
              (vec
               (for [i (range n)]
                 (let [neighbors (aget adj i)]
                   (if (empty? neighbors)
                     (nth prev i)
                     (let [avg (m/vec3-scale
                                (reduce m/vec3+ m/vec3-zero (map #(nth prev %) neighbors))
                                (/ 1.0 (count neighbors)))]
                       (m/vec3+ (nth prev i) (m/vec3-scale (m/vec3- avg (nth prev i)) factor)))))))]
          (recur (inc iter) next-verts))))))

(defn frontal-uv
  "Frontal projection UV mapping."
  [verts]
  (mapv (fn [[x y _z]]
          [(m/clamp (+ (* (/ (+ x 0.1) 0.2) 0.7) 0.15) 0.0 1.0)
           (m/clamp (- 1.0 (+ (* (/ (+ y 0.14) 0.28) 0.7) 0.15)) 0.0 1.0)])
        verts))

(defn- generate-eye-sphere [cx cy cz r n-lat n-lon]
  (let [verts
        (vec
         (for [i (range (inc n-lat))
               :let [phi (+ (* m/pi 0.25) (* m/pi 0.5 (/ (double i) n-lat)))]
               j (range (inc n-lon))]
           (let [theta (+ (* -1.0 m/pi 0.45) (* m/pi 0.9 (/ (double j) n-lon)))
                 x (+ cx (* r (m/sin phi) (m/cos theta)))
                 y (+ cy (* r (m/cos phi)))
                 z (+ cz (* r (m/sin phi) (m/sin theta)))
                 n (m/vec3-normalize [(* (m/sin phi) (m/cos theta)) (m/cos phi) (* (m/sin phi) (m/sin theta))])]
             {:position [x y z] :normal n :uv [0.0 0.0]})))
        indices
        (vec
         (mapcat
          (fn [i]
            (mapcat
             (fn [j]
               (let [a (+ (* i (inc n-lon)) j)
                     b (+ a n-lon 1)]
                 [a b (inc a) (inc a) b (inc b)]))
             (range n-lon)))
          (range n-lat)))]
    [verts indices]))

(defn- generate-disc [cx cy cz r n-rings n-seg]
  (let [verts
        (vec
         (for [i (range (inc n-rings))
               :let [ri (* r (/ (double i) n-rings))]
               j (range n-seg)]
           (let [theta (* 2.0 m/pi (/ (double j) n-seg))]
             {:position [(+ cx (* ri (m/cos theta))) (+ cy (* ri (m/sin theta))) cz]
              :normal [0.0 0.0 1.0] :uv [0.0 0.0]})))
        indices
        (vec
         (mapcat
          (fn [i]
            (mapcat
             (fn [j]
               (let [a (+ (* i n-seg) j)
                     b (+ a n-seg)
                     c (if (< (inc j) n-seg) (inc a) (* i n-seg))
                     d (if (< (inc j) n-seg) (inc b) (* (inc i) n-seg))]
                 [a b c c b d]))
             (range n-seg)))
          (range n-rings)))]
    [verts indices]))

(defn generate-eyebrows
  "Generate eyebrow meshes (a thin arc-shaped strip per side). `params` is
  a BrowParams map (`:thickness :arch-height :spacing :angle`, plus
  `:color` which `character.material/for-part`'s `:eyebrow` case does not
  yet consume — it currently tints eyebrows from `:hair :color` instead;
  a real but pre-existing gap this fn doesn't attempt to fix, since fixing
  it means changing `for-part`'s arity and its cross-repo call site in
  `kami-app-character-creator`, out of scope here). Anchored at the SAME
  brow-ridge coordinates `character.blendshape`'s `targets-spec` already
  established (`browInnerUp` x=+-0.014 y=0.068, `browOuterUp*` x=+-0.050
  y=0.066, `browDown*` x=+-0.032 y=0.068) rather than re-deriving head
  topology blind — so a real eyebrow's rest shape lines up with where the
  brow-raise/brow-lower expression morphs already push vertices. Returns a
  vector of 2 MeshPart maps (`eyebrow_l`/`eyebrow_r`, `:material :eyebrow`
  — that material id already existed in `character/material.cljc` and
  `character.material-ids`, unused until now: this fn is what was missing,
  not the material)."
  [{:keys [thickness arch-height spacing angle] :or {thickness 0.5 arch-height 0.5 spacing 0.5 angle 0.5}}]
  (let [n-seg 6
        base-y 0.068
        z 0.071
        inner-x0 (+ 0.014 (* spacing 0.006))
        outer-x0 (+ 0.048 (* spacing 0.006))
        arch (+ 0.002 (* arch-height 0.007))
        tilt (* (- angle 0.5) 0.014)
        half-thick (+ 0.0009 (* thickness 0.0022))]
    (vec
     (mapcat
      (fn [side]
        (let [suffix (if (neg? side) "l" "r")
              pts (for [seg (range n-seg)]
                    (let [t (/ (double seg) (dec n-seg))
                          x-local (+ inner-x0 (* t (- outer-x0 inner-x0)))
                          x (* side x-local)
                          y (+ base-y (* arch (m/sin (* m/pi t))) (* tilt t))]
                      [x y z]))
              vertices
              (vec (mapcat (fn [[x y z]]
                             [{:position [x (+ y half-thick) z] :normal [0.0 0.0 1.0] :uv [0.0 0.0]}
                              {:position [x (- y half-thick) z] :normal [0.0 0.0 1.0] :uv [0.0 1.0]}])
                           pts))
              indices
              (vec (mapcat (fn [seg]
                             (let [i (* seg 2)]
                               [i (+ i 2) (+ i 1) (+ i 1) (+ i 2) (+ i 3)]))
                           (range (dec n-seg))))]
          [{:name (str "eyebrow_" suffix) :vertices vertices :indices indices :material :eyebrow}]))
      [-1.0 1.0]))))

(defn generate-eyes
  "Generate eye meshes (white + iris + pupil per side). `params` is an
  EyeParams map. Returns a vector of MeshPart maps."
  [{:keys [size spacing height depth iris-size] :as _params}]
  (let [spacing (+ 0.025 (* spacing 0.015))]
    (vec
     (mapcat
      (fn [side]
        (let [cx (* side spacing)
              cy (+ 0.035 (* (or height 0.0) 0.02))
              cz (+ 0.065 (* (- 1.0 depth) 0.015))
              r-eye (* 0.01 size)
              suffix (if (neg? side) "l" "r")
              [wv wi] (generate-eye-sphere cx cy cz r-eye 10 14)
              r-iris (* r-eye 0.5 iris-size)
              [iv ii] (generate-disc cx cy (+ cz (* r-eye 1.02)) r-iris 8 12)
              r-pupil (* r-iris 0.4)
              [pv pi] (generate-disc cx cy (+ cz (* r-eye 1.04)) r-pupil 6 10)]
          [{:name (str "eye_white_" suffix) :vertices wv :indices wi :material :eye-white}
           {:name (str "iris_" suffix) :vertices iv :indices ii :material :iris}
           {:name (str "pupil_" suffix) :vertices pv :indices pi :material :pupil}]))
      [-1.0 1.0]))))
