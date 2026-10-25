(ns mangaka-scene.sim
  "Simulation kinds (spring bone, cloth, particles, DEC fields).

  Restored from `kami-mangaka-scene/src/sim.rs` (kotoba-lang/kami-engine,
  deleted in PR #82) as zero-dependency portable CLJC, per ADR-2607010930.

  P0 skeleton in the original Rust: enum only, wiring (`kami-pipelines`
  particle emission, `kami-dec` wind/dust/Maxwell fields) was never
  implemented before deletion, so there is nothing native-only to exclude
  here — this port is complete.")

(def fx-kinds
  "Variant names verbatim from the Rust `FxKind` enum."
  #{:dust :hit-spark :splash :sparkle :smoke :speed-lines-3d})
