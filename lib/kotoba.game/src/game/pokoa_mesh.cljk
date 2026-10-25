(ns game.pokoa-mesh
  "Zero-dep portable CLJC. Restored from the legacy kami-engine/kami-game Rust
  crate (`kami-game/src/pokoa_mesh.rs`, 755 lines, `kotoba-lang/kami-engine`,
  deleted in PR #82 \"Remove Rust workspace from kami-engine\") as part of the
  clj-wgsl migration (ADR-2607010930, `com-junkawasaki/root`). Restored as part
  of a 7-cluster parallel restoration of `kami-game` — this is Cluster D
  (procedural mesh generation).

  Purpose: procedural mesh generators for Pokoa (ぽこあ) brainrot creatures
  (toilettle/skibidrain/mega-skibidi, sigpup/sigmachu/gigachad,
  ohiolet/ohiodon, grimini/grimaceon, rizzlord, fanumoth, plus the catch-ball
  item). Reuses shared primitives from `game.brainrot-mesh` — no local
  duplication, matching the original's `use crate::brainrot_mesh::{...}`.
  Every function returns a mesh as a `[vertices indices]` pair (flat
  interleaved pos3+norm3+uv2, stride 8). Pure data + pure functions
  throughout; no IO/GPU."
  (:require [game.brainrot-mesh :as bm]))

;; ---------------------------------------------------------------------------
;; Portable math helpers
;; ---------------------------------------------------------------------------

(defn- sin* [x] #?(:clj (Math/sin (double x)) :cljs (js/Math.sin x)))
(defn- cos* [x] #?(:clj (Math/cos (double x)) :cljs (js/Math.cos x)))

(def ^:private PI #?(:clj Math/PI :cljs js/Math.PI))

;; ---------------------------------------------------------------------------
;; Shared primitives (mirrors `use crate::brainrot_mesh::{...}`)
;; ---------------------------------------------------------------------------

(def ^:private capsule bm/capsule)
(def ^:private character-mesh bm/character-mesh)
(def ^:private cylinder bm/cylinder-mesh)
(def ^:private merge-meshes bm/merge-meshes)
(def ^:private offset-mesh bm/offset-mesh)
(def ^:private rounded-box bm/rounded-box)
(def ^:private scale-mesh bm/scale-mesh)
(def ^:private sphere bm/sphere-mesh)

;; ---------------------------------------------------------------------------
;; Pokoa Creature Meshes
;; ---------------------------------------------------------------------------

(defn toilettle-mesh
  "Toilettle: tiny toilet creature with stubby legs and big eyes. Mirrors
  `toilettle_mesh`."
  []
  (let [segs 12
        body (scale-mesh (sphere segs segs 0.6 0.0 0.4 0.0) 1.0 0.7 1.0)
        tank (offset-mesh (rounded-box 0.5 0.6 0.3 0.05) 0.0 0.5 -0.5)
        left-eye (sphere 8 8 0.15 -0.2 0.7 0.35)
        right-eye (sphere 8 8 0.15 0.2 0.7 0.35)
        left-pupil (sphere 6 6 0.07 -0.2 0.72 0.47)
        right-pupil (sphere 6 6 0.07 0.2 0.72 0.47)
        left-leg (cylinder 8 0.1 0.15 -0.25 0.0 0.0)
        right-leg (cylinder 8 0.1 0.15 0.25 0.0 0.0)
        lid (sphere 6 segs 0.5 0.0 0.55 0.0)]
    (merge-meshes [body tank left-eye right-eye left-pupil right-pupil left-leg right-leg lid])))

(defn skibidrain-mesh
  "Skibidrain: medium toilet creature with rotating head and arms. Mirrors
  `skibidrain_mesh`."
  []
  (let [segs 14
        body (scale-mesh (sphere segs segs 0.9 0.0 0.6 0.0) 1.0 0.75 1.0)
        tank (offset-mesh (rounded-box 0.8 0.9 0.5 0.08) 0.0 0.7 -0.7)
        head (sphere segs segs 0.45 0.0 1.3 0.1)
        left-eye (sphere 8 8 0.12 -0.2 1.4 0.45)
        right-eye (sphere 8 8 0.12 0.2 1.4 0.45)
        left-arm (offset-mesh (cylinder 8 0.08 0.3 0.0 0.0 0.0) -0.9 0.6 0.0)
        right-arm (offset-mesh (cylinder 8 0.08 0.3 0.0 0.0 0.0) 0.9 0.6 0.0)
        left-leg (cylinder 8 0.12 0.2 -0.35 0.0 0.0)
        right-leg (cylinder 8 0.12 0.2 0.35 0.0 0.0)]
    (merge-meshes [body tank head left-eye right-eye left-arm right-arm left-leg right-leg])))

(defn mega-skibidi-mesh
  "MegaSkibidi: giant toilet boss with massive head and laser eyes. Mirrors
  `mega_skibidi_mesh`."
  []
  (let [segs 16
        body (scale-mesh (sphere segs segs 1.5 0.0 1.0 0.0) 1.0 0.7 1.0)
        tank (offset-mesh (rounded-box 1.5 1.8 0.8 0.1) 0.0 1.2 -1.3)
        head (sphere segs segs 0.8 0.0 2.5 0.2)
        left-eye (offset-mesh (cylinder 8 0.08 0.4 0.0 0.0 0.0) -0.35 2.6 0.9)
        right-eye (offset-mesh (cylinder 8 0.08 0.4 0.0 0.0 0.0) 0.35 2.6 0.9)
        spike1 (sphere 6 6 0.15 0.0 3.3 0.2)
        spike2 (sphere 6 6 0.12 -0.3 3.1 0.1)
        spike3 (sphere 6 6 0.12 0.3 3.1 0.1)
        left-arm (offset-mesh (cylinder 10 0.15 0.5 0.0 0.0 0.0) -1.5 1.0 0.0)
        right-arm (offset-mesh (cylinder 10 0.15 0.5 0.0 0.0 0.0) 1.5 1.0 0.0)
        left-fist (sphere 8 8 0.2 -1.5 0.5 0.0)
        right-fist (sphere 8 8 0.2 1.5 0.5 0.0)
        left-leg (cylinder 8 0.18 0.35 -0.6 0.0 0.0)
        right-leg (cylinder 8 0.18 0.35 0.6 0.0 0.0)]
    (merge-meshes [body tank head left-eye right-eye spike1 spike2 spike3 left-arm right-arm
                   left-fist right-fist left-leg right-leg])))

(defn sigpup-mesh
  "Sigpup: small electric puppy with spiky fur and determined eyes. Mirrors
  `sigpup_mesh`."
  []
  (let [segs 10
        body (offset-mesh (capsule 0.25 0.2 segs) 0.0 0.35 0.0)
        head (sphere segs segs 0.22 0.0 0.7 0.15)
        left-ear (offset-mesh (cylinder 6 0.06 0.15 0.0 0.0 0.0) -0.12 0.95 0.1)
        right-ear (offset-mesh (cylinder 6 0.06 0.15 0.0 0.0 0.0) 0.12 0.95 0.1)
        tail (offset-mesh (cylinder 6 0.04 0.2 0.0 0.0 0.0) 0.0 0.4 -0.35)
        fl (cylinder 6 0.06 0.12 -0.15 0.0 0.15)
        fr (cylinder 6 0.06 0.12 0.15 0.0 0.15)
        bl (cylinder 6 0.06 0.12 -0.15 0.0 -0.15)
        br (cylinder 6 0.06 0.12 0.15 0.0 -0.15)
        nose (sphere 6 6 0.04 0.0 0.68 0.35)]
    (merge-meshes [body head left-ear right-ear tail fl fr bl br nose])))

(defn sigmachu-mesh
  "Sigmachu: electric fighting mouse with buff arms and sunglasses. Mirrors
  `sigmachu_mesh`."
  []
  (let [segs 12
        body (offset-mesh (capsule 0.3 0.3 segs) 0.0 0.5 0.0)
        head (sphere segs segs 0.25 0.0 1.0 0.1)
        left-ear (offset-mesh (cylinder 6 0.05 0.25 0.0 0.0 0.0) -0.15 1.3 0.0)
        right-ear (offset-mesh (cylinder 6 0.05 0.25 0.0 0.0 0.0) 0.15 1.3 0.0)
        glasses (offset-mesh (rounded-box 0.4 0.08 0.05 0.01) 0.0 1.05 0.3)
        left-arm (offset-mesh (capsule 0.1 0.2 8) -0.45 0.6 0.0)
        right-arm (offset-mesh (capsule 0.1 0.2 8) 0.45 0.6 0.0)
        left-fist (sphere 8 8 0.1 -0.45 0.35 0.0)
        right-fist (sphere 8 8 0.1 0.45 0.35 0.0)
        left-leg (cylinder 8 0.1 0.18 -0.15 0.0 0.0)
        right-leg (cylinder 8 0.1 0.18 0.15 0.0 0.0)
        tail (offset-mesh (cylinder 6 0.04 0.3 0.0 0.0 0.0) 0.0 0.5 -0.4)]
    (merge-meshes [body head left-ear right-ear glasses left-arm right-arm left-fist right-fist
                   left-leg right-leg tail])))

(defn gigachad-mesh
  "Gigachad: ultimate sigma evolution — massive jaw, huge muscles, golden
  aura. Mirrors `gigachad_mesh`."
  []
  (let [segs 14
        body (offset-mesh (capsule 0.5 0.4 segs) 0.0 0.8 0.0)
        head (sphere segs segs 0.3 0.0 1.5 0.1)
        jaw (offset-mesh (rounded-box 0.25 0.12 0.2 0.03) 0.0 1.3 0.3)
        crown (sphere 8 8 0.1 0.0 1.85 0.0)
        left-arm (offset-mesh (capsule 0.15 0.3 10) -0.7 0.9 0.0)
        right-arm (offset-mesh (capsule 0.15 0.3 10) 0.7 0.9 0.0)
        left-fist (sphere 10 10 0.15 -0.7 0.5 0.0)
        right-fist (sphere 10 10 0.15 0.7 0.5 0.0)
        left-leg (cylinder 10 0.15 0.3 -0.25 0.0 0.0)
        right-leg (cylinder 10 0.15 0.3 0.25 0.0 0.0)
        aura-parts (for [i (range 8)
                         :let [angle (* (/ (double i) 8.0) 2.0 PI)
                               x (* (cos* angle) 0.8)
                               z (* (sin* angle) 0.8)]]
                     (sphere 4 4 0.06 x 1.0 z))]
    (merge-meshes (concat [body head jaw crown left-arm right-arm left-fist right-fist left-leg right-leg]
                          aura-parts))))

(defn ohiolet-mesh
  "Ohiolet: glitchy ghost creature — distorted body with floating cube
  fragments. Mirrors `ohiolet_mesh`."
  [glitch-phase]
  (let [segs 10
        phase (* glitch-phase 2.0 PI)
        body-verts (vec (apply concat
                          (for [i (range (inc segs))
                                :let [phi (* PI (/ (double i) segs)) y (cos* phi) r (sin* phi)]
                                j (range (inc segs))
                                :let [theta (* 2.0 PI (/ (double j) segs))
                                      nx (* r (cos* theta)) nz (* r (sin* theta)) ny y
                                      glitch (* 0.1 (* (sin* (+ (* 3.0 phi) phase)) (cos* (+ (* 2.0 theta) (* phase 1.7)))))
                                      radius (+ 0.4 glitch)]]
                            [(* nx radius) (+ (* ny radius) 0.5) (* nz radius) nx ny nz
                             (/ (double j) segs) (/ (double i) segs)])))
        ring (inc segs)
        body-idxs (vec (apply concat (for [i (range segs) j (range segs)
                                            :let [a (+ (* i ring) j) b (+ a ring)]]
                                        [a b (inc a) (inc a) b (inc b)])))
        body [body-verts body-idxs]
        eye (sphere 8 8 0.12 0.0 0.7 0.35)
        frag1 (offset-mesh (rounded-box 0.12 0.12 0.12 0.02) (+ 0.5 (* (sin* phase) 0.1)) 0.6 0.3)
        frag2 (offset-mesh (rounded-box 0.08 0.08 0.08 0.01) (+ -0.4 (* (cos* phase) 0.1)) 0.8 -0.2)
        frag3 (offset-mesh (rounded-box 0.1 0.1 0.1 0.02) 0.0 (+ 1.0 (* (sin* phase) 0.15)) 0.0)]
    (merge-meshes [body eye frag1 frag2 frag3])))

(defn ohiodon-mesh
  "Ohiodon: the Ohio final boss — massive distorted creature with
  reality-warping aura. Mirrors `ohiodon_mesh`."
  [warp-phase]
  (let [segs 14
        phase (* warp-phase 2.0 PI)
        body-verts (vec (apply concat
                          (for [i (range (inc segs))
                                :let [phi (* PI (/ (double i) segs)) y (cos* phi) r (sin* phi)]
                                j (range (inc segs))
                                :let [theta (* 2.0 PI (/ (double j) segs))
                                      nx (* r (cos* theta)) nz (* r (sin* theta)) ny y
                                      warp (* 0.2 (+ (* (sin* (+ (* 4.0 phi) phase)) 0.5)
                                                      (* (sin* (+ (* 3.0 theta) (* phase 0.8))) 0.3)
                                                      (* (cos* (+ (* 5.0 phi) (* 2.0 theta))) 0.2)))
                                      radius (+ 0.8 warp)]]
                            [(* nx radius) (+ (* ny radius) 1.0) (* nz radius) nx ny nz
                             (/ (double j) segs) (/ (double i) segs)])))
        ring (inc segs)
        body-idxs (vec (apply concat (for [i (range segs) j (range segs)
                                            :let [a (+ (* i ring) j) b (+ a ring)]]
                                        [a b (inc a) (inc a) b (inc b)])))
        body [body-verts body-idxs]
        eye1 (sphere 8 8 0.15 -0.3 1.3 0.6)
        eye2 (sphere 8 8 0.15 0.3 1.3 0.6)
        eye3 (sphere 8 8 0.1 0.0 1.6 0.5)
        fragments (for [i (range 6)
                        :let [angle (+ (* (/ (double i) 6.0) 2.0 PI) phase)
                              r 1.2
                              x (* (cos* angle) r)
                              z (* (sin* angle) r)
                              y (+ 1.0 (* (sin* (+ (* angle 2.0) phase)) 0.3))
                              size (+ 0.08 (* i 0.02))]]
                    (offset-mesh (rounded-box size size size 0.01) x y z))
        left-horn (offset-mesh (cylinder 6 0.06 0.3 0.0 0.0 0.0) -0.4 1.8 0.0)
        right-horn (offset-mesh (cylinder 6 0.06 0.3 0.0 0.0 0.0) 0.4 1.8 0.0)]
    (merge-meshes (concat [body eye1 eye2 eye3 left-horn right-horn] fragments))))

(defn grimini-mesh
  "Grimini: cute baby blob — small purple ball with a smile. Mirrors
  `grimini_mesh`."
  [wobble]
  (let [stacks 14 slices 14
        phase (* wobble 2.0 PI)
        verts (vec (apply concat
                    (for [i (range (inc stacks))
                          :let [phi (* PI (/ (double i) stacks)) y (cos* phi) r (sin* phi)]
                          j (range (inc slices))
                          :let [theta (* 2.0 PI (/ (double j) slices))
                                nx (* r (cos* theta)) nz (* r (sin* theta)) ny y
                                wobble-disp (* 0.08 (sin* (+ (* 3.0 phi) phase)) (cos* (* 2.0 theta)))
                                radius (+ 0.5 wobble-disp)]]
                      [(* nx radius) (+ (* ny radius) 0.5) (* nz radius) nx ny nz
                       (/ (double j) slices) (/ (double i) stacks)])))
        ring (inc slices)
        idxs (vec (apply concat (for [i (range stacks) j (range slices)
                                       :let [a (+ (* i ring) j) b (+ a ring)]]
                                   [a b (inc a) (inc a) b (inc b)])))
        body [verts idxs]
        left-eye (sphere 6 6 0.08 -0.15 0.65 0.4)
        right-eye (sphere 6 6 0.08 0.15 0.65 0.4)
        smile (sphere 4 4 0.04 0.0 0.5 0.45)]
    (merge-meshes [body left-eye right-eye smile])))

(defn grimaceon-mesh
  "Grimaceon: full Grimace evolution — massive purple blob with toxic puddle
  base. Mirrors `grimaceon_mesh`."
  [wobble]
  (let [stacks 18 slices 18
        phase (* wobble 2.0 PI)
        verts (vec (apply concat
                    (for [i (range (inc stacks))
                          :let [phi (* PI (/ (double i) stacks)) y (cos* phi) r (sin* phi)]
                          j (range (inc slices))
                          :let [theta (* 2.0 PI (/ (double j) slices))
                                nx (* r (cos* theta)) nz (* r (sin* theta)) ny y
                                wobble-disp (* 0.15 (+ (* (sin* (+ (* 3.0 phi) phase)) 0.5)
                                                        (* (sin* (+ (* 2.0 theta) (* phase 1.3))) 0.3)
                                                        (* (sin* (+ (* 4.0 phi) (* 3.0 theta))) 0.2)))
                                radius (+ 1.0 wobble-disp)]]
                      [(* nx radius) (+ (* ny radius) 1.0) (* nz radius) nx ny nz
                       (/ (double j) slices) (/ (double i) stacks)])))
        ring (inc slices)
        idxs (vec (apply concat (for [i (range stacks) j (range slices)
                                       :let [a (+ (* i ring) j) b (+ a ring)]]
                                   [a b (inc a) (inc a) b (inc b)])))
        body [verts idxs]
        left-eye (sphere 8 8 0.15 -0.35 1.3 0.75)
        right-eye (sphere 8 8 0.15 0.35 1.3 0.75)
        smile (sphere 6 6 0.08 0.0 1.0 0.9)
        puddle-segs 16
        puddle-verts0 [0.0 0.02 0.0 0.0 1.0 0.0 0.5 0.5]
        puddle-ring (vec (apply concat
                           (for [j (range (inc puddle-segs))
                                 :let [theta (* 2.0 PI (/ (double j) puddle-segs))
                                       x (* (cos* theta) 1.5) z (* (sin* theta) 1.5)]]
                             [x 0.02 z 0.0 1.0 0.0 (+ 0.5 (* 0.5 (cos* theta))) (+ 0.5 (* 0.5 (sin* theta)))])))
        puddle-verts (into puddle-verts0 puddle-ring)
        puddle-idxs (vec (apply concat (for [j (range puddle-segs)] [0 (+ 1 j) (+ 2 j)])))
        puddle [puddle-verts puddle-idxs]]
    (merge-meshes [body left-eye right-eye smile puddle])))

(defn rizzlord-mesh
  "Rizzlord: legendary fire/psychic — elegant humanoid with flame crown and
  charm aura. Mirrors `rizzlord_mesh`."
  []
  (let [body (character-mesh "slim" 1.2)
        flame1 (sphere 8 8 0.12 0.0 1.7 0.0)
        flame2 (sphere 6 6 0.1 -0.15 1.6 0.05)
        flame3 (sphere 6 6 0.1 0.15 1.6 0.05)
        flame4 (sphere 6 6 0.08 -0.08 1.75 -0.05)
        flame5 (sphere 6 6 0.08 0.08 1.75 -0.05)
        heart1 (sphere 6 6 0.06 0.6 1.0 0.3)
        heart2 (sphere 6 6 0.06 -0.6 1.0 0.3)
        heart3 (sphere 6 6 0.06 0.0 1.2 -0.5)
        cape (offset-mesh (rounded-box 0.8 1.0 0.05 0.02) 0.0 0.5 -0.4)]
    (merge-meshes [body flame1 flame2 flame3 flame4 flame5 heart1 heart2 heart3 cape])))

(defn fanumoth-mesh
  "Fanumoth: legendary steel/normal — bulky collector with metal armor
  plates. Mirrors `fanumoth_mesh`."
  []
  (let [body (character-mesh "stocky" 1.15)
        chest-plate (offset-mesh (rounded-box 0.5 0.4 0.15 0.04) 0.0 0.3 0.3)
        left-shoulder (offset-mesh (rounded-box 0.25 0.15 0.2 0.03) -0.5 0.5 0.0)
        right-shoulder (offset-mesh (rounded-box 0.25 0.15 0.2 0.03) 0.5 0.5 0.0)
        bag (offset-mesh (rounded-box 0.35 0.4 0.25 0.05) 0.55 0.1 -0.1)
        crown (sphere 8 8 0.12 0.0 1.2 0.0)
        left-claw (offset-mesh (rounded-box 0.1 0.2 0.05 0.01) -0.55 -0.1 0.1)
        right-claw (offset-mesh (rounded-box 0.1 0.2 0.05 0.01) 0.55 -0.1 0.1)]
    (merge-meshes [body chest-plate left-shoulder right-shoulder bag crown left-claw right-claw])))

(defn pokoa-ball-mesh
  "Pokoa Ball: catch ball item mesh — sphere with horizontal line. Mirrors
  `pokoa_ball_mesh`."
  []
  (let [ball (sphere 12 12 0.3 0.0 0.3 0.0)
        button (sphere 6 6 0.06 0.0 0.3 0.28)
        line-segs 16
        line-verts0 [0.0 0.3 0.0 0.0 1.0 0.0 0.5 0.5]
        line-ring (vec (apply concat
                         (for [j (range (inc line-segs))
                               :let [theta (* 2.0 PI (/ (double j) line-segs))
                                     x (* (cos* theta) 0.31) z (* (sin* theta) 0.31)]]
                           [x 0.3 z 0.0 1.0 0.0 (+ 0.5 (* (cos* theta) 0.5)) (+ 0.5 (* (sin* theta) 0.5))])))
        line-verts (into line-verts0 line-ring)
        line-idxs (vec (apply concat (for [j (range line-segs)] [0 (+ 1 j) (+ 2 j)])))
        line [line-verts line-idxs]]
    (merge-meshes [ball button line])))
