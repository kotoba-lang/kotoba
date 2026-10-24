(ns dft
  "KAMI Design-For-Test (DFT — not Discrete Fourier Transform). Restored
  from the legacy kami-engine/kami-dft Rust crate (deleted in kotoba-lang/
  kami-engine PR #82 'Remove Rust workspace from kami-engine') as part of
  the clj-wgsl migration (ADR-2607010930, com-junkawasaki/root).

  Scan chain insertion, BIST generation, ATPG pattern generation, and
  JTAG/BSDL support — one namespace per original Rust module:
    dft.scan  — scan chain insertion (round-robin FF distribution)
    dft.bist  — memory BIST (MBIST) + logic BIST (LBIST) generation
    dft.atpg  — automatic test pattern generation (stuck-at/transition faults)
    dft.jtag  — IEEE 1149.1 boundary scan + BSDL file generation

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU. Depends on
  kotoba-lang/engineer for shared contracts (constraint/DRC/etc).")
