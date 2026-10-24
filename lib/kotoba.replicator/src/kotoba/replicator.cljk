(ns kotoba.replicator
  "kami-replicator (utsushimi 写身) — synthetic data generation + domain
  randomization, `omni.replicator.core` API-compat target.

  Ported 1:1 from the Rust path-reservation crate `kami-replicator`
  (kotoba-lang/kami-engine, per ADR-2607010930 clj-wgsl migration Phase 4).
  The Rust source is itself only a set of status constants — R1.0 path
  reservation per ADR-2605261800, no runtime code. This port preserves
  exactly that: a pure-data status record, no network, no I/O.

  R1.3 gate (deferred, unimplemented in both source and this port):
  omni.replicator.core same-script -> same output schema (JSON diff = 0)."
  )

(def adr
  "ADR governing this path reservation."
  "ADR-2605261800")

(def phase
  "Current implementation phase."
  "R1.0-path-reservation")

(def kami-name
  "KAMI-internal short name for this capability (utsushimi, 写身)."
  "utsushimi")

(def nv-compat-target
  "NVIDIA Omniverse API this crate targets API-compatibility with."
  "omni.replicator.core")

(def status
  "Full status map — mirrors the Rust crate's public consts 1:1."
  {:adr              adr
   :phase            phase
   :kami-name        kami-name
   :nv-compat-target nv-compat-target})
