(ns pdk
  "KAMI PDK — Process Design Kit management. Restored from the legacy
  kami-engine/kami-pdk Rust crate (deleted in kotoba-lang/kami-engine
  PR #82 'Remove Rust workspace from kami-engine') as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  Technology node definitions, standard cell libraries, a statistical
  memory compiler for SRAM/ROM/RegFile estimation, and Liberty/LEF
  standards-format access — one namespace per original Rust module:
    pdk.technology — technology node + design-rule tech file
    pdk.stdcell    — generic ~20-cell standard cell library generator
    pdk.memory     — statistical memory compiler (area/timing/leakage estimation)
    pdk.liberty    — Liberty (.lib) timing characterisation facade
    pdk.lef        — LEF physical layout abstraction facade

  Liberty (.lib) timing characterisation and LEF physical layout
  abstractions were split out 2026-07-07 (ADR-2607072500) into their own
  org-<standards-body>-<spec> reverse-domain repos — kotoba-lang/
  org-synopsys-liberty and kotoba-lang/org-si2-lef — since they're
  independent industry-standard formats, not pdk-specific logic (neither
  was ever required by pdk.stdcell/pdk.memory/pdk.technology). They're
  wired back in as thin `pdk.liberty`/`pdk.lef` facade namespaces over
  those sibling repos (via :local/root deps.edn coordinates), so pdk
  remains a fully-composed PDK front-end rather than a disconnected leaf —
  the actual parsing logic still lives in the sibling repos, not here.

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.
  Depends on kotoba-lang/engineer for shared contracts.")
