(ns pnr
  "KAMI Place and Route — physical design backend for VLSI/ASIC layout.
  Restored from the legacy kami-engine/kami-pnr Rust crate (deleted in
  kotoba-lang/kami-engine PR #82 'Remove Rust workspace from kami-engine')
  as part of the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Floorplanning, cell placement, clock tree synthesis (CTS), maze routing,
  and GDSII stream export — one namespace per original Rust module:
    pnr.floorplan — block placement, IO pin assignment, utilization analysis
    pnr.placement — greedy left-to-right row-based standard cell placement
    pnr.cts       — clock tree synthesis via recursive bisection
    pnr.routing   — Lee/BFS maze routing on a multi-layer grid
    pnr.gdsii     — GDSII binary stream export (JVM-only, java.io)

  Zero-dep portable CLJC (gdsii is JVM-only) — pure data + pure functions,
  no GPU. Depends on kotoba-lang/engineer for shared contracts.")
