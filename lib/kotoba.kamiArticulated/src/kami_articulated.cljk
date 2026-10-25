(ns kami_articulated
  "Restored from the legacy kami-engine/kami-articulated Rust crate
  (kotoba-lang/kami-engine, deleted in PR #82 \"Remove Rust workspace from
  kami-engine\") as zero-dep portable CLJC, per ADR-2607010930 (clj-wgsl
  migration, com-junkawasaki/root).

  Purpose (from the original crate's `lib.rs` docstring): a URDF / MJCF /
  USD physics loader feeding a `kami-genesis` articulation. R1.1 PoC scope
  (ADR-2605261800) only implemented the URDF path:
    - URDF parser supporting prismatic + revolute (+ fixed/continuous) joints
    - link mass / inertia / axis extraction
    - hand-off to `kami-genesis` as an `ArticulatedSystem`
  Full URDF spec coverage (visual/collision meshes, mimic, transmission,
  Gazebo extensions), MJCF, and USD were never implemented in the original
  and remain out of scope here too.

  This restoration ports ONLY the portable URDF -> data parsing step
  (`kami_articulated::parse_urdf` and its supporting types), which lives in
  `kami_articulated.urdf`, re-exported below exactly like the original
  `pub use urdf::{...}` in `lib.rs`. The downstream `kami-genesis`
  articulated rigid-body-dynamics solver (PxArticulationReducedCoordinate
  -shaped, native/vendor-facade) that CONSUMES the `ArticulatedSystem` this
  namespace produces is explicitly OUT OF SCOPE — restoring it is a separate
  effort.

  Sibling: `kotoba-lang/articulated-scene` (restored kami-articulated-scene)
  is a DIFFERENT, related crate — an EDN authoring surface for robot-arm
  scenes that originally depended on this crate's `ArticulatedSystem`/
  `Link`/`Joint`/`Inertia`/`Pose`/`JointKind` types (reimplemented locally
  there as plain maps, since that restoration predates this one)."
  (:require [kami_articulated.urdf :as urdf]))

;; ---------------------------------------------------------------------------
;; Crate-level constants (mirrors the original `lib.rs` `pub const`s).
;; ---------------------------------------------------------------------------

(def ADR "ADR-2605261800")
(def PHASE "R1.1-cartpole-poc")
(def KAMI_NAME "kami-articulated")
(def NV_COMPAT_TARGET "isaacsim.core.prims.Articulation")
(def SUPPORTED_FORMATS ["urdf"])

;; ---------------------------------------------------------------------------
;; Re-exports (mirrors `pub use urdf::{ArticulatedSystem, Inertia, Joint,
;; JointKind, Link, ParseError, Pose, parse_urdf};` — CLJC has no structs or
;; a `ParseError` type to re-export, so we re-export the parsing fn and the
;; error-type set / vocabulary instead).
;; ---------------------------------------------------------------------------

(def parse-urdf urdf/parse-urdf)
(def link-index urdf/link-index)
(def joint-index urdf/joint-index)
(def joint-kind-values urdf/joint-kind-values)
(def error-types urdf/error-types)
(def default-pose urdf/default-pose)
(def default-inertia urdf/default-inertia)
(def parse-xml urdf/parse-xml)
