(ns pcb
  "KAMI EDA — Electronic Design Automation: schematic capture, PCB layout,
  netlist/BOM generation, and ERC/DRC validation. Restored from the
  legacy kami-engine/kami-eda Rust crate (deleted in kotoba-lang/
  kami-engine PR #82 'Remove Rust workspace from kami-engine') as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Named `pcb` (not `eda`) to avoid collision with the pre-existing,
  unrelated kotoba-lang/eda repo (OpenSTA-class timing/PVT slack analysis
  + OpenROAD-class grid routing/overflow checks — a mature, independent
  project with its own docs site and evidence-output design; discovered
  when this restoration was attempted under the 'eda' name).

  One namespace per original Rust module:
    pcb.schematic — symbol placement, wire routing, net labelling, netlist extraction
    pcb.layout    — footprint placement, trace routing, vias, zones, DRC
                    (named `pcb.layout`, not `pcb.pcb`, since the parent
                    namespace is already `pcb`)
    pcb.netlist   — SPICE/Verilog-gate-level/EDIF export + BOM generation
    pcb.erc       — Electrical Rule Check (5 rules)

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.
  Violations are plain maps matching kotoba-lang/engineer's
  `engineer.drc` violation shape. Depends on kotoba-lang/engineer for
  shared contracts.")
