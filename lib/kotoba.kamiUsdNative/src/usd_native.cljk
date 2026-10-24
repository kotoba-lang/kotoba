(ns usd-native
  "kami-usd-native — from-scratch Rust USD parser + composition engine
  path-reservation constants.

  R1.0 path reservation per ADR-2605261800 §D10.4.
  **Contingent fallback** — activated only if tinyusdz WASM fails the R1.1
  viability gate (iPhone 12+ 10MB USD parse ≤2s). Activation requires
  Council Lv6+ ≥3 attestation per §D10.2.

  In the original Rust crate this module contained ONLY these constants —
  no parser, no composition engine, no FFI/native bindings of any kind. The
  crate was a reserved path/placeholder awaiting a future activation
  decision, not yet implemented. All content here is a direct, faithful,
  1:1 port of that constants-only stub."
  (:refer-clojure :exclude [name]))

(def adr
  "ADR governing this crate's contingent-fallback status."
  "ADR-2605261800")

(def phase
  "Current lifecycle phase of this crate."
  "R1.0-path-reservation")

(def kami-name
  "The kami-* facade name of this crate."
  "kami-usd-native")

(def status
  "Activation status: pending the tinyusdz WASM viability gate outcome."
  "contingent-fallback-pending-viability-gate")

(def triggered-by
  "The condition that would trigger activation of this crate."
  "tinyusdz WASM gate fail (R1.1)")

(def nv-compat-targets
  "NVIDIA/Pixar API surfaces this crate would mirror if activated."
  ["omni.usd" "pxr.Usd" "pxr.UsdGeom"])

(def supported-formats
  "USD file formats this crate would support if activated."
  ["usda" "usdc" "usdz"])
