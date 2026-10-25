(ns model-checking
  "KAMI Verify — formal verification (equivalence checking, model
  checking, SVA assertions) and coverage analysis for digital designs.
  Restored from the legacy kami-engine/kami-verify Rust crate (deleted in
  kotoba-lang/kami-engine PR #82 'Remove Rust workspace from
  kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Named `model-checking` (not `verify`) to avoid the generic-verb
  collision risk `verify` carries in a large, actively-developed org —
  same class of correction as `kami-si` -> `signal-integrity`.

  One namespace per original Rust module:
    model-checking.equivalence — exhaustive combinational equivalence checking
    model-checking.model-check — BFS-based bounded model checking (safety/liveness/reachability)
    model-checking.assertion   — SVA-style assertion evaluation over signal traces
    model-checking.coverage    — coverage collection/reporting with cross-bin support

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.")
