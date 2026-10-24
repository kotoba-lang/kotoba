(ns cnc-toolpath
  "KAMI CAM — Computer-Aided Manufacturing: toolpath generation, G-code
  output, tool library, and stock definition. Accepts geometry as
  generic input (`[x y z]` points / mesh data) to avoid a circular
  dependency on `kotoba-lang/brep` (the restored kami-cad). Restored
  from the legacy kami-engine/kami-cam Rust crate (deleted in
  kotoba-lang/kami-engine PR #82 'Remove Rust workspace from
  kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Named `cnc-toolpath` (not `cam`) — \"cam\" is dangerously ambiguous
  (camera vs. Computer-Aided Manufacturing) in a large,
  actively-developed org with real camera-rig work elsewhere, same
  class of correction as `kami-si` -> `signal-integrity`. Ledger class
  `:port-to-CLJC-domain-interpreter` (90-docs/migration/
  clj-wgsl-ledger.edn).

  One namespace per original Rust module:
    cnc-toolpath.tool     — cutting tool definitions + tool library
    cnc-toolpath.stock    — workpiece stock definitions + material presets
    cnc-toolpath.toolpath — CAM operations + toolpath segment generation
    cnc-toolpath.gcode    — G-code generation with post-processor config

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.")
