(ns character.blendshape
  "Blendshape system — shape deformations + 52 ARKit expression
  targets. Restored from the legacy kami-engine/kami-character Rust
  crate's `blendshape.rs` (deleted in kotoba-lang/kami-engine PR #82)
  as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root)."
  (:require [character.math :as m]))

(defn apply-face-shape
  "Apply face shape blendshapes to base mesh vertices (FaceShapeParams
  map). Returns a new vertex vector."
  [verts {:keys [jaw-width jaw-length chin-shape cheekbone-width forehead-height face-length]}]
  (mapv
   (fn [[x y z]]
     (let [x-abs (Math/abs (double x))
           x (if (< y 0.0)
               (let [t (min 1.0 (/ (- y) 0.12))
                     scale (+ 1.0 (* (- jaw-width 0.5) 0.3 t))]
                 (* x scale))
               x)
           y (if (< y -0.06)
               (let [t (min 1.0 (/ (- (- y) 0.06) 0.06))]
                 (- y (* (- jaw-length 0.5) 0.02 t)))
               y)
           x (if (< y -0.08)
               (let [t (min 1.0 (/ (- (- y) 0.08) 0.04))
                     narrowing (* (- 1.0 chin-shape) 0.3 t)]
                 (* x (- 1.0 (* narrowing (max 0.0 (- 1.0 (/ x-abs 0.05)))))))
               x)
           cheek-y (max 0.0 (- 1.0 (Math/pow (/ (- y 0.01) 0.03) 2)))
           x (if (> cheek-y 0.0)
               (+ x (* (m/signum x) (- cheekbone-width 0.5) 0.01 cheek-y))
               x)
           y (if (> y 0.08)
               (let [t (min 1.0 (/ (- y 0.08) 0.04))]
                 (+ y (* (- forehead-height 0.5) 0.015 t)))
               y)
           scale-y (+ 1.0 (* (- face-length 0.5) 0.15))
           y (* y scale-y)]
       [x y z]))
   verts))

(defn apply-eye-shape
  "Apply eye socket depth deformations (EyeParams map)."
  [verts {:keys [depth]}]
  (mapv
   (fn [[x y z]]
     (let [z (reduce
              (fn [z eye-x]
                (let [ed (m/sqrt (+ (Math/pow (- x eye-x) 2) (Math/pow (- y 0.045) 2)))]
                  (if (and (< ed 0.025) (> z 0.0))
                    (let [depth-mod (* (- depth 0.5) 0.005)]
                      (- z (* depth-mod (- 1.0 (Math/pow (/ ed 0.025) 2)))))
                    z)))
              z [-0.032 0.032])]
       [x y z]))
   verts))

(defn apply-nose-shape
  "Apply nose shape deformations (NoseParams map)."
  [verts {:keys [bridge-height width]}]
  (mapv
   (fn [[x y z]]
     (let [front (m/clamp (/ z 0.1) 0.0 1.0)
           nose-region (max 0.0 (- 1.0 (Math/pow (/ (- y 0.01) 0.04) 2)))
           center (max 0.0 (- 1.0 (Math/pow (/ x 0.02) 2)))
           z (if (and (> nose-region 0.0) (> center 0.0))
               (+ z (* (- bridge-height 0.5) 0.01 nose-region center front))
               z)
           tip-y (max 0.0 (- 1.0 (Math/pow (/ (+ y 0.005) 0.015) 2)))
           x (if (> tip-y 0.0)
               (+ x (* (m/signum x) (- width 0.5) 0.005 tip-y front))
               x)]
       [x y z]))
   verts))

(defn apply-mouth-shape
  "Apply mouth shape deformations (MouthParams map)."
  [verts {:keys [width upper-lip-thickness lower-lip-thickness]}]
  (mapv
   (fn [[x y z]]
     (let [front (m/clamp (/ z 0.08) 0.0 1.0)
           lip-y (max 0.0 (- 1.0 (Math/pow (/ (+ y 0.035) 0.015) 2)))
           lip-x (max 0.0 (- 1.0 (Math/pow (/ x 0.03) 2)))]
       (if (and (> lip-y 0.0) (> lip-x 0.0) (> front 0.0))
         (let [x (+ x (* (m/signum x) (- width 0.5) 0.005 lip-y front))
               thickness (* (+ upper-lip-thickness lower-lip-thickness) 0.5)
               z (+ z (* (- thickness 0.5) 0.004 lip-y lip-x front))]
           [x y z])
         [x y z])))
   verts))

(def arkit-names
  ["eyeBlinkLeft" "eyeBlinkRight"
   "eyeLookDownLeft" "eyeLookDownRight"
   "eyeLookInLeft" "eyeLookInRight"
   "eyeLookOutLeft" "eyeLookOutRight"
   "eyeLookUpLeft" "eyeLookUpRight"
   "eyeSquintLeft" "eyeSquintRight"
   "eyeWideLeft" "eyeWideRight"
   "jawForward" "jawLeft" "jawRight" "jawOpen"
   "mouthClose" "mouthFunnel" "mouthPucker"
   "mouthLeft" "mouthRight"
   "mouthSmileLeft" "mouthSmileRight"
   "mouthFrownLeft" "mouthFrownRight"
   "mouthDimpleLeft" "mouthDimpleRight"
   "mouthStretchLeft" "mouthStretchRight"
   "mouthRollLower" "mouthRollUpper"
   "mouthShrugLower" "mouthShrugUpper"
   "mouthPressLeft" "mouthPressRight"
   "mouthLowerDownLeft" "mouthLowerDownRight"
   "mouthUpperUpLeft" "mouthUpperUpRight"
   "browDownLeft" "browDownRight"
   "browInnerUp"
   "browOuterUpLeft" "browOuterUpRight"
   "cheekPuff" "cheekSquintLeft" "cheekSquintRight"
   "noseSneerLeft" "noseSneerRight"
   "tongueOut"])

;; --- procedural ARKit blendshape content -------------------------------
;; Real (not captured-scan) per-vertex deltas for the 32 ARKit targets
;; `character-creator.expression-bridge/preset->arkit-weights` actually
;; references (covers all 18 VRM 1.0 presets). Standard procedural
;; blendshape authoring — a named anatomical region falls off smoothly
;; (quadratic, same `max(0, 1-(d/r)^2)` shape `apply-*-shape` above already
;; uses) from an anchor point, contributing a fixed delta at full weight.
;; Anchors reuse the SAME head-local coordinate conventions `base-mesh/
;; generate-head` builds the mesh from and `apply-eye-shape`/`apply-nose-
;; shape`/`apply-mouth-shape`/`apply-face-shape` already deform it with:
;; head ellipsoid radius x=0.09/y=0.12/z=0.08; eyes x=+-0.032 y=0.045;
;; nose bridge y=0.02 tip y=-0.005; lips y=-0.035; brow ridge y~0.07.
;; Side convention: avatar's own left = +X (matches `kotoba.vrm`'s
;; humanoid-rest comment "left arm (avatar's left = +X)").

(def ^:private targets-spec
  "ARKit name -> `[[anchor-x anchor-y radius dx dy dz] ...]` (head-local
  coords/metres; multiple points sum, e.g. `browInnerUp` touches both
  inner brows from one target). Not derived from any spec or captured
  scan — a documented, editable approximation, same honesty convention as
  `character-creator.expression-bridge/preset->arkit-weights`."
  {"eyeBlinkLeft"      [[ 0.032  0.045 0.026  0.0    -0.012  0.0]
                        [ 0.032  0.038 0.018  0.0     0.007  0.0]]
   "eyeBlinkRight"     [[-0.032  0.045 0.026  0.0    -0.012  0.0]
                        [-0.032  0.038 0.018  0.0     0.007  0.0]]
   "eyeSquintLeft"     [[ 0.032  0.040 0.022  0.0    -0.006  0.0]]
   "eyeSquintRight"    [[-0.032  0.040 0.022  0.0    -0.006  0.0]]
   "eyeWideLeft"       [[ 0.032  0.050 0.024  0.0     0.008  0.0]
                        [ 0.032  0.036 0.018  0.0    -0.005  0.0]]
   "eyeWideRight"      [[-0.032  0.050 0.024  0.0     0.008  0.0]
                        [-0.032  0.036 0.018  0.0    -0.005  0.0]]
   ;; The 8 eyeLook* targets are the one honest exception: real gaze needs
   ;; eyeball-mesh/bone rotation (`base-mesh/generate-eyes`'s separate
   ;; iris/pupil parts, not this head mesh) — this fn only deforms the head
   ;; mesh, so these get a small, clearly-approximate eyelid shift instead
   ;; of true gaze redirection.
   "eyeLookUpLeft"     [[ 0.032  0.045 0.026  0.0     0.004  0.0]]
   "eyeLookUpRight"    [[-0.032  0.045 0.026  0.0     0.004  0.0]]
   "eyeLookDownLeft"   [[ 0.032  0.045 0.026  0.0    -0.004  0.0]]
   "eyeLookDownRight"  [[-0.032  0.045 0.026  0.0    -0.004  0.0]]
   "eyeLookInLeft"     [[ 0.032  0.045 0.026 -0.003   0.0    0.0]]
   "eyeLookInRight"    [[-0.032  0.045 0.026  0.003   0.0    0.0]]
   "eyeLookOutLeft"    [[ 0.032  0.045 0.026  0.003   0.0    0.0]]
   "eyeLookOutRight"   [[-0.032  0.045 0.026 -0.003   0.0    0.0]]
   "browDownLeft"      [[ 0.032  0.068 0.032  0.0    -0.010  0.0]]
   "browDownRight"     [[-0.032  0.068 0.032  0.0    -0.010  0.0]]
   "browInnerUp"       [[ 0.014  0.068 0.020  0.0     0.012  0.0]
                        [-0.014  0.068 0.020  0.0     0.012  0.0]]
   "browOuterUpLeft"   [[ 0.050  0.066 0.022  0.0     0.010  0.0]]
   "browOuterUpRight"  [[-0.050  0.066 0.022  0.0     0.010  0.0]]
   "cheekPuff"         [[ 0.050  0.020 0.032  0.006   0.0    0.008]
                        [-0.050  0.020 0.032 -0.006   0.0    0.008]]
   "cheekSquintLeft"   [[ 0.045  0.028 0.028  0.0     0.008  0.004]]
   "cheekSquintRight"  [[-0.045  0.028 0.028  0.0     0.008  0.004]]
   "noseSneerLeft"     [[ 0.018  0.010 0.020  0.003   0.006  0.0]]
   "noseSneerRight"    [[-0.018  0.010 0.020 -0.003   0.006  0.0]]
   "jawOpen"           [[ 0.0   -0.090 0.090  0.0    -0.018 -0.006]]
   "mouthFunnel"       [[ 0.0   -0.035 0.032  0.0     0.0    0.010]]
   "mouthPucker"       [[ 0.024 -0.035 0.030 -0.006   0.0    0.012]
                        [-0.024 -0.035 0.030  0.006   0.0    0.012]]
   "mouthStretchLeft"  [[ 0.024 -0.035 0.026  0.013   0.0    0.0]]
   "mouthStretchRight" [[-0.024 -0.035 0.026 -0.013   0.0    0.0]]
   "mouthSmileLeft"    [[ 0.024 -0.035 0.028  0.010   0.014  0.0]]
   "mouthSmileRight"   [[-0.024 -0.035 0.028 -0.010   0.014  0.0]]
   "mouthFrownLeft"    [[ 0.024 -0.035 0.028 -0.004  -0.011  0.0]]
   "mouthFrownRight"   [[-0.024 -0.035 0.028  0.004  -0.011  0.0]]})

(defn- eval-region-deltas
  "`verts` (head-local `[x y z]` positions) + a `targets-spec` entry ->
  one delta per vertex, summed across the entry's anchor points."
  [verts spec]
  (mapv (fn [[x y z]]
          (reduce (fn [[dx dy dz] [ax ay r tdx tdy tdz]]
                    (let [d (m/sqrt (+ (Math/pow (- x ax) 2) (Math/pow (- y ay) 2)))
                          w (max 0.0 (- 1.0 (Math/pow (/ d r) 2)))]
                      [(+ dx (* w tdx)) (+ dy (* w tdy)) (+ dz (* w tdz))]))
                  m/vec3-zero
                  spec))
        verts))

(defn generate-arkit-targets
  "Generate 52 ARKit expression blendshape targets. `verts-or-n` is either
  the real head-mesh vertex positions (`[[x y z] ...]`, head-local coords —
  what `character/generate-character` passes) or a bare vertex COUNT (back-
  compat / no-position callers, e.g. the original `(generate-arkit-targets
  10)` test) — with a bare count there is nothing to compute a region from,
  so those targets stay the zero placeholder, same as before this fix.

  With real positions: the 32 targets `character-creator.expression-bridge/
  preset->arkit-weights` references (`targets-spec`, above — covers every
  VRM 1.0 preset) get real procedural deltas. The other 20 ARKit names
  (`jawForward/Left/Right`, `mouthClose`, `mouthLeft/Right`, `mouthDimpleLeft/
  Right`, `mouthRollLower/Upper`, `mouthShrugLower/Upper`, `mouthPressLeft/
  Right`, `mouthLowerDownLeft/Right`, `mouthUpperUpLeft/Right`, `tongueOut`)
  stay the zero placeholder — genuinely unreferenced by any VRM preset
  today, so they don't yet have an observable effect through this pipeline
  to validate against; documented here rather than silently guessed at."
  [verts-or-n]
  (if (number? verts-or-n)
    (mapv (fn [name] {:name name :deltas (vec (repeat verts-or-n m/vec3-zero))}) arkit-names)
    (let [verts verts-or-n n (count verts)]
      (mapv (fn [name]
              {:name name
               :deltas (if-let [spec (get targets-spec name)]
                         (eval-region-deltas verts spec)
                         (vec (repeat n m/vec3-zero)))})
            arkit-names))))
