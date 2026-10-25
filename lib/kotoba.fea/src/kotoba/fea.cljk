(ns kotoba.fea
  "KAMI fea — finite-element analysis domain logic in pure Clojure.

  cljc port of kami-cae (kami-engine's FEA crate), which was deleted from
  kami-engine's working tree without being committed; this repo is the
  authority going forward, per ADR-2607010000 (kotoba-runtime-sdk cljc
  migration) and ADR-2607012200-adjacent CAE/FEA substrate ADRs. See
  kami-engine's `kami-cae/src/lib.rs` (git history) for the original Rust.

  Sub-namespaces mirror kami-cae's modules 1:1:

  - `kotoba.fea.mesh`        — FEA mesh container + `generate-box-mesh`.
  - `kotoba.fea.material`    — material model + built-in presets (data in
                                `resources/kami/fea/materials.edn`).
  - `kotoba.fea.boundary`    — boundary-condition constructors + DOF mask.
  - `kotoba.fea.solver`      — linear-static solver (dense Cholesky).
  - `kotoba.fea.postprocess` — result-field range + color-map export.
  - `kotoba.fea.vec3`        — pure 3-vector math (`glam::DVec3` equivalent).

  No network, no I/O in any domain namespace (`kotoba.fea.material`'s
  resource-loading fns are the sole, explicitly `:clj`-only exception).
  See README for what kami-cae had that was intentionally left unported
  (GPU/wgpu rendering, non-bar element assembly) and why.")

(def supported-element-types
  "Element topologies `kotoba.fea.mesh` can construct — full kami-cae
  parity (mesh construction was generic over all seven; only assembly in
  `kotoba.fea.solver` is bar-only, matching kami-cae's own solver scope)."
  #{:beam2 :tri3 :tri6 :quad4 :tet4 :tet10 :hex8})

(def solver-assembly-support
  "Element types `kotoba.fea.solver/solve-linear-static` can assemble —
  bar-only, matching kami-cae (which declared but never implemented
  assembly for the other six topologies)."
  #{:beam2})
