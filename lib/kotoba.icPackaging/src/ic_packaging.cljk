(ns ic-packaging
  "KAMI Packaging — IC package modeling, wire bond/flip chip bonding, and
  thermal analysis. Restored from the legacy kami-engine/kami-pkg Rust
  crate (deleted in kotoba-lang/kami-engine PR #82 'Remove Rust workspace
  from kami-engine') as part of the clj-wgsl migration (ADR-2607010930,
  com-junkawasaki/root).

  Named `ic-packaging` (not `pkg`) for clarity — `pkg` is a generic term
  (software package, npm/Debian package, etc.) that would have been
  confusing, same class of correction as `kami-si` -> `signal-integrity`.

  One namespace per original Rust module:
    ic-packaging.package — IC package type (QFP/BGA/CSP/WLCSP/SiP/Chiplet)
                            geometry + thermal-resistance estimation
    ic-packaging.bonding — wire bond / flip chip bonding diagram generation
    ic-packaging.thermal — junction/case temperature thermal-network analysis

  Zero-dep portable CLJC — pure data + pure functions, no IO/GPU.")
