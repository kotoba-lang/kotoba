(ns spice
  "KAMI SPICE — circuit simulation engine. Restored from the legacy
  kami-engine/kami-spice Rust crate (deleted in kotoba-lang/kami-engine
  PR #82 'Remove Rust workspace from kami-engine') as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  Modified Nodal Analysis (MNA) based SPICE simulator: DC operating point,
  device model library, and SPICE netlist parser/exporter — one namespace
  per original Rust module:
    spice.circuit  — circuit elements + circuit container
    spice.analysis — DC-op solver (MNA + Gaussian elimination w/ partial pivoting)
    spice.model    — MOSFET/BJT/diode compact-model parameters + library
    spice.netlist  — SPICE netlist parser/exporter, engineering-notation values

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. Circuit
  sizes are node-count scale (coarse-grained per ADR-2607010930), not a
  per-pixel/per-frame hot loop. Nonlinear devices (MOSFET/BJT/diode) are
  solved via `spice.analysis/solve-dc-op-nonlinear`, which re-linearizes
  each device into a companion MNA model every Newton-Raphson iteration
  (documented simplifications: MOSFET has no channel-length modulation or
  body effect, BJT is forward-active-only, no temperature sweep — see
  `spice.analysis`'s namespace docstring). `spice.analysis/solve-dc-op`
  remains the original purely-linear fast path, unchanged. Depends on
  kotoba-lang/engineer for shared contracts.")
