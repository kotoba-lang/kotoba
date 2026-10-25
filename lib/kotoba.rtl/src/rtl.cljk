(ns rtl
  "KAMI RTL — HDL editor (Verilog/VHDL parsing), event-driven simulation,
  waveform viewer, and synthesis netlist. Restored from the legacy
  kami-engine/kami-rtl Rust crate (deleted in kotoba-lang/kami-engine
  PR #82 'Remove Rust workspace from kami-engine') as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  One namespace per original Rust module:
    rtl.hdl       — Verilog/VHDL AST + minimal Verilog module-header parser
    rtl.simulator — event-driven RTL simulator (four-valued IEEE 1164 logic)
    rtl.waveform  — waveform view + IEEE 1364 VCD export
    rtl.synthesis — gate-level netlist, depth estimation, constant folding

  Zero-dep portable CLJC — pure data + pure functions/parsers, no IO/GPU.
  Depends on kotoba-lang/{engineer,engineer-render} for shared contracts.")
