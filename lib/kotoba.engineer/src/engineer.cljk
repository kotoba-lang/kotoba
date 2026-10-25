(ns engineer
  "KAMI Engineering SDK — shared CAD/EDA foundation. Restored from the legacy
  kami-engine/kami-eng-core Rust crate (deleted in kotoba-lang/kami-engine
  PR #82 'Remove Rust workspace from kami-engine') as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  Cross-domain primitives for all engineering tools, one namespace per
  original Rust `pub mod`:
    engineer.constraint   — geometric + parametric constraint status solver
    engineer.parameter    — named parameters with bounds
    engineer.history      — command-pattern undo/redo
    engineer.measurement  — distance/angle measurement
    engineer.selection    — pick/box-select/chain-select sets
    engineer.layer        — layer visibility/lock/color manager
    engineer.grid         — grid config + point-snap
    engineer.drc          — Design Rule Check violation reporter

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. Consumed by
  domain repos (dft/spice/pdk/pnr/bim/rtl/cad/cae-solver/eda) and
  kotoba-lang/{engineer-io,engineer-render}.")
