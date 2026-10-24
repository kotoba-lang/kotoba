(ns kami-app-giemon.kabitori
  "Kabitori (mold-removal) brush-contact geometry.

  Ported from the `kami-app-giemon.rs` kabitori (黴取り) probe section
  (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace\") as
  part of the clj-wgsl migration (ADR-2607010930, `com-junkawasaki/root`).

  The kabitori probe itself (URDF-loaded, driven by the native
  kami-genesis 3-D rigid-body spatial solver + contact solver) is
  native-only and NOT ported. What *is* portable, and ported here, is the
  brush geometry and the pure-geometry step of `kabitori_scrub_step` that
  is independent of the solver: given the brush's world rotation +
  position, find which of its 4 bristle-tip endpoints is lowest (the
  contact point), and convert a tangential slip speed into a
  `kami-app-giemon.mold-field/scrub` intensity. Advancing the articulation
  state (`ContactWorld::step`) and computing the tangential slip velocity
  itself (`point_jacobian`) both require the native solver and are
  excluded."
  (:require [kami-app-giemon.geom :as g]))

;; Brush bristle-cross endpoints (body frame) — used both as colliders and
;; as the scrub footprint sample points, in the original.
(def brush-tips
  [[0.02 -0.025 0.0]
   [0.02 0.025 0.0]
   [0.02 0.0 -0.025]
   [0.02 0.0 0.025]])

(def brush-radius 0.012)
;; Mold removed per metre of tangential brush slip while pressed (coverage/m).
(def scrub-rate 6.0)
;; Brush footprint radius on the surface (m).
(def brush-footprint 0.03)

(defn brush-contact-point
  "Given the brush's world `rotation` (quat) and `position` (world-frame
  origin), find the lowest (by world z) of the 4 bristle-tip endpoints —
  the contact point on the surface."
  [rotation position]
  (reduce (fn [best tip]
            (let [w (g/v3+ position (g/quat-rotate-vec3 rotation tip))]
              (if (or (nil? best) (< (nth w 2) (nth best 2))) w best)))
          nil
          brush-tips))

(defn scrub-intensity
  "Erosion intensity for one contact step: proportional to tangential slip
  speed x dt (a pressure proxy is folded into `scrub-rate`)."
  [v-tangent dt]
  (* scrub-rate v-tangent dt))
