# kami-usd-native

Restored from `kotoba-lang/kami-engine` (Rust workspace deleted in PR #82,
"Remove Rust workspace"). Original source recovered at commit
`a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`. Restored per ADR-2607010930
(kami-engine crate restoration wave).

## What this crate was

`kami-usd-native` was reserved as a **contingent fallback**: a from-scratch
Rust USD (`.usda` / `.usdc` / `.usdz`) parser and composition engine,
per ADR-2605261800 §D10.4. It was **never implemented** — the crate was
a path reservation, not a working parser. Its activation was contingent on
a future event (tinyusdz WASM failing the R1.1 viability gate — iPhone 12+
Safari parsing a 10MB USD file in ≤2s) and required Council Lv6+ ≥3
attestation (§D10.2) before any real implementation work would begin.

The sibling crate `kami-usd` (the primary, tinyusdz-WASM-backed facade) was
the intended R1.0 default; `kami-usd-native` would only replace it as
backend if that gate failed. As of the deleted-workspace snapshot,
`kotoba-lang/kami-usd` does not yet exist as a repo either.

## Native-facade determination

This assignment's brief flagged `kami-usd-native` as *likely* a real FFI
binding to a native OpenUSD C++ library (per ADR-2605261800 §D10.3's
kami-* facade invariant: NVIDIA-branded APIs accessed only through the
`kami-*` namespace, no direct PhysX/OmniKit/OpenUSD imports outside it).

**That assumption does not hold for this crate.** Reading the actual
recovered source (`Cargo.toml`, `README.md`, `src/lib.rs`) shows:

- `Cargo.toml` dependencies: `log`, `thiserror`, `serde`, `serde_json` only.
  No `cxx`, `bindgen`, `pyo3`, or any native/C++ interop crate.
- `src/lib.rs` contained **only 8 `pub const` declarations** (strings and
  a string slice) documenting the crate's status, trigger condition, and
  intended (not-yet-built) API surface. There was no parser code, no
  composition engine, no `extern "C"` blocks, no FFI of any kind.
- The README explicitly labels the crate "R1.0 path reservation" and
  "Status: contingent-fallback-pending-viability-gate" — i.e. this was a
  placeholder for future work, not a native binding layer.

So `kami-usd-native` is the **opposite** of a native-only facade: it is
100% pure, portable metadata with no native/vendor dependency surface at
all. All of it has been ported.

## What was ported

`src/usd_native.kotoba` preserves every constant from the original
`src/lib.rs` through typed string getters compiled for restricted JavaScript
and Wasm:

| Rust const | Value |
|---|---|
| `ADR` | `"ADR-2605261800"` |
| `PHASE` | `"R1.0-path-reservation"` |
| `KAMI_NAME` | `"kami-usd-native"` |
| `STATUS` | `"contingent-fallback-pending-viability-gate"` |
| `TRIGGERED_BY` | `"tinyusdz WASM gate fail (R1.1)"` |
| `NV_COMPAT_TARGETS` | `["omni.usd" "pxr.Usd" "pxr.UsdGeom"]` |
| `SUPPORTED_FORMATS` | `["usda" "usdc" "usdz"]` |

No Rust `#[test]`s existed in the original source to port; tests here are
new coverage asserting the constants match the original values exactly,
plus a smoke test.

## Usage

```clojure
(defn kami-name-value [] :string "kami-usd-native")
(defn supported-format-0 [] :string "usda")
```

## Testing

```sh
kbb -M:test
```

## License

Apache 2.0 + Charter Compliance Rider v2.0 (matching original crate).
