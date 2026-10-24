(ns mangaka-scene.lexicon
  "Pose lexicon — semantic labels (\"action.dash\", \"expression.angry\") mapped
  to VRM standard bone rotations and ARKit-style expression weights.

  Restored from `kami-mangaka-scene/src/lexicon.rs` (kotoba-lang/kami-engine,
  deleted in PR #82) as zero-dependency portable CLJC, per ADR-2607010930.

  LLM nodes in `lg_mangaka.compose_scene_3d` emit these labels; resolution
  happens here. Rotations are deliberately coarse — manga storytelling needs
  readable silhouettes, not biomechanical fidelity. Refined animation comes
  from the caller via explicit `BoneRotation` overrides in `PoseSpec.bones`.

  The original depended on `kami_vrm::vrm_types::HumanBoneName` purely for
  its `.as_str()` camelCase string form (e.g. `LeftUpperArm` -> \"leftUpperArm\");
  since that crate is not part of this restoration's zero-dependency scope,
  bone identity here is the camelCase string directly — the same string the
  Rust `as_str()` call produced and the same string `BoneRotation.bone`
  round-trips as JSON-LD."
  (:require [kotoba.lang.text :as str]
            [mangaka-scene.pose :as pose]))

;; ── Euler(XYZ, degrees) -> Quat[x y z w] ────────────────────────────────
;; Mirrors `glam::Quat::from_euler(EulerRot::XYZ, ...)`: intrinsic rotations
;; applied in order X, then Y, then Z about the body's own (already-rotated)
;; axes, i.e. q = qx * qy * qz (Hamilton product, qx applied last onto qy*qz's
;; frame — matches glam's XYZ convention).

(defn- deg->rad [d] (/ (* d Math/PI) 180.0))

(defn- axis-angle-quat [[ax ay az] rad]
  (let [half (/ rad 2.0)
        s (Math/sin half)
        c (Math/cos half)]
    [(* ax s) (* ay s) (* az s) c]))

(defn- hamilton
  "Quaternion Hamilton product `q1 * q2`, both `[x y z w]`."
  [[x1 y1 z1 w1] [x2 y2 z2 w2]]
  [(+ (* w1 x2) (* x1 w2) (* y1 z2) (- (* z1 y2)))
   (+ (* w1 y2) (- (* x1 z2)) (* y1 w2) (* z1 x2))
   (+ (* w1 z2) (* x1 y2) (- (* y1 x2)) (* z1 w2))
   (- (* w1 w2) (* x1 x2) (* y1 y2) (* z1 z2))])

(defn euler-quat
  "`[deg-x deg-y deg-z]` -> `[x y z w]` quaternion, XYZ intrinsic order."
  [[dx dy dz]]
  (let [qx (axis-angle-quat [1.0 0.0 0.0] (deg->rad dx))
        qy (axis-angle-quat [0.0 1.0 0.0] (deg->rad dy))
        qz (axis-angle-quat [0.0 0.0 1.0] (deg->rad dz))]
    (hamilton (hamilton qx qy) qz)))

;; ── Pose presets ─────────────────────────────────────────────────────────

(def ^:private preset-table
  {"action.rest" []
   "rest" []
   "action.idle" [["spine" [0.0 0.0 0.0]]
                  ["leftUpperArm" [0.0 0.0 70.0]]
                  ["rightUpperArm" [0.0 0.0 -70.0]]]
   "action.dash" [["spine" [10.0 0.0 0.0]]
                  ["chest" [8.0 0.0 0.0]]
                  ["leftUpperArm" [-45.0 0.0 75.0]]
                  ["leftLowerArm" [-65.0 0.0 0.0]]
                  ["rightUpperArm" [45.0 0.0 -75.0]]
                  ["rightLowerArm" [-65.0 0.0 0.0]]
                  ["leftUpperLeg" [-30.0 0.0 0.0]]
                  ["leftLowerLeg" [55.0 0.0 0.0]]
                  ["rightUpperLeg" [30.0 0.0 0.0]]
                  ["rightLowerLeg" [10.0 0.0 0.0]]]
   "action.run" :dash
   "action.walk" [["leftUpperArm" [-12.0 0.0 72.0]]
                  ["rightUpperArm" [12.0 0.0 -72.0]]
                  ["leftUpperLeg" [-10.0 0.0 0.0]]
                  ["rightUpperLeg" [10.0 0.0 0.0]]]
   "action.swing" [["spine" [0.0 -20.0 0.0]]
                   ["chest" [0.0 -10.0 0.0]]
                   ["rightShoulder" [0.0 0.0 -20.0]]
                   ["rightUpperArm" [-90.0 0.0 -45.0]]
                   ["rightLowerArm" [-45.0 0.0 0.0]]
                   ["leftUpperArm" [0.0 0.0 60.0]]
                   ["leftLowerArm" [-30.0 0.0 0.0]]]
   "action.attack" :swing
   "action.hit" [["spine" [-15.0 0.0 0.0]]
                 ["chest" [-10.0 0.0 0.0]]
                 ["neck" [-10.0 0.0 0.0]]
                 ["head" [-15.0 10.0 0.0]]
                 ["leftUpperArm" [-30.0 0.0 95.0]]
                 ["rightUpperArm" [-30.0 0.0 -95.0]]]
   "action.impact" :hit
   "action.fall" [["spine" [-30.0 0.0 0.0]]
                  ["leftUpperLeg" [-70.0 0.0 0.0]]
                  ["rightUpperLeg" [-70.0 0.0 0.0]]
                  ["leftUpperArm" [-60.0 0.0 110.0]]
                  ["rightUpperArm" [-60.0 0.0 -110.0]]]
   "action.cower" [["spine" [20.0 0.0 0.0]]
                   ["chest" [15.0 0.0 0.0]]
                   ["neck" [12.0 0.0 0.0]]
                   ["head" [12.0 0.0 0.0]]
                   ["leftUpperArm" [-30.0 0.0 110.0]]
                   ["leftLowerArm" [-95.0 0.0 0.0]]
                   ["rightUpperArm" [-30.0 0.0 -110.0]]
                   ["rightLowerArm" [-95.0 0.0 0.0]]]
   "action.flinch" :cower
   "action.shout" [["spine" [-5.0 0.0 0.0]]
                   ["neck" [-15.0 0.0 0.0]]
                   ["head" [-20.0 0.0 0.0]]
                   ["leftUpperArm" [-10.0 0.0 110.0]]
                   ["rightUpperArm" [-10.0 0.0 -110.0]]]
   "action.yell" :shout
   "action.point" [["rightShoulder" [0.0 -10.0 -5.0]]
                   ["rightUpperArm" [0.0 0.0 -95.0]]
                   ["rightLowerArm" [0.0 0.0 0.0]]
                   ["rightIndexProximal" [0.0 0.0 0.0]]]
   "action.reach" [["spine" [-5.0 0.0 0.0]]
                   ["rightUpperArm" [0.0 0.0 -110.0]]
                   ["rightLowerArm" [0.0 0.0 5.0]]]
   "action.stand_proud" [["spine" [-2.0 0.0 0.0]]
                         ["chest" [-3.0 0.0 0.0]]
                         ["head" [-5.0 0.0 0.0]]
                         ["leftUpperArm" [0.0 0.0 78.0]]
                         ["rightUpperArm" [0.0 0.0 -78.0]]]
   "action.heroic" :stand_proud})

(defn- resolve-alias [label]
  (loop [v (get preset-table label ::not-found)]
    (cond
      (= v ::not-found) nil
      (keyword? v) (recur (get preset-table (str "action." (name v)) ::not-found))
      :else v)))

(defn pose-preset
  "Resolve a semantic pose label into a coarse VRM bone rotation set.
  Returns `nil` when the label is unknown so the caller can fall back to
  `pose/rest-pose` or an explicit override list."
  [label]
  (when-some [bones (resolve-alias label)]
    (mapv (fn [[bone euler-deg]]
            (pose/bone-rotation bone (euler-quat euler-deg)))
          bones)))

(defn expression-preset
  "Resolve an ARKit-style expression preset name to an `Expression` tag.
  Unknown names fall back to `:neutral`."
  [name]
  (case (str/lower (or name ""))
    ("happy" "joy" "smile") :happy
    ("angry" "rage") :angry
    ("sad" "sorrow" "grief") :sad
    ("surprised" "surprise" "shock") :surprised
    ("determined" "resolve" "focus") :determined
    ("pained" "pain" "hurt") :pained
    ("smirk" "smug") :smirk
    :neutral))
