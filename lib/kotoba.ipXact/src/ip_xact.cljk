(ns ip-xact
  "KAMI IP Management — IP-XACT component catalog, bus protocol
  generation, NoC topology synthesis, and CDC analysis. Restored from the
  legacy kami-engine/kami-ip Rust crate (deleted in kotoba-lang/
  kami-engine PR #82 'Remove Rust workspace from kami-engine') as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Named `ip-xact` (not `ip`) to avoid IP-address / intellectual-property
  ambiguity in a large, actively-developed org — same class of
  correction as `kami-si` -> `signal-integrity`.

  One namespace per original Rust module:
    ip-xact.component    — IP-XACT component catalog + IEEE 1685-2014 XML export
    ip-xact.bus-protocol — AXI4/APB bus config + Verilog RTL port generation
    ip-xact.noc          — Network-on-Chip topology synthesis (mesh/ring/crossbar/tree)
    ip-xact.cdc          — Clock Domain Crossing analysis + violation detection

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.")
