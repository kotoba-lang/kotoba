(ns engineer-io
  "KAMI Engineering SDK — CAD/EDA file-format I/O. Restored from the legacy
  kami-engine/kami-eng-io Rust crate (deleted in kotoba-lang/kami-engine
  PR #82 'Remove Rust workspace from kami-engine') as part of the clj-wgsl
  migration (ADR-2607010930, com-junkawasaki/root).

  One namespace per original Rust `pub mod`, plus a top-level FileFormat
  registry:
    engineer-io.format  — FileFormat keywords + extension/mime-type/detection
    engineer-io.stl     — STL ASCII + binary exporter
    engineer-io.gerber  — Gerber RS-274X generator
    engineer-io.step    — STEP AP214 header/footer generator

  Zero-dep portable CLJC (stl/export-binary is #?(:clj ...) — JVM ByteBuffer;
  a CLJS arm can be added if a browser consumer needs it). Depends on
  kotoba-lang/engineer for shared contracts (constraint/DRC/etc).")
