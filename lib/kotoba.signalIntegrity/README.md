# kotoba-lang/signal-integrity

[![CI](https://github.com/kotoba-lang/signal-integrity/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/signal-integrity/actions/workflows/ci.yml)

**Signal integrity math — transmission line analysis, crosstalk
analysis, eye diagram generation, and S-parameter extraction, in pure
Clojure.** A [kotoba-lang](https://github.com/kotoba-lang) capability
library, restored from the legacy `kami-engine/kami-si` Rust crate
(deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace from
kami-engine") as part of the KAMI-engine → pure-`.cljc` kotoba migration
(ADR-2607010000 / ADR-2607010930).

No network, no I/O, no GPU. All state is plain immutable maps with
namespaced keys; all domain functions are pure.

**Named `signal-integrity`, not `si`** — the migration ledger's original
short-hand note "SI units" for this crate was ambiguous/wrong (this is
Signal Integrity, an EDA discipline, not the physical SI unit system;
same class of correction as the `kami-dft` "DFT" ambiguity found
elsewhere in the migration).

## 2026-07-07: merged in the `si` scaffold's richer implementation

The migration briefly produced two mutually-unaware parallel ports of
`kami-si`: this repo (`signal-integrity`, the policy-canonical name) and
a scaffold repo named `si`. `si`'s implementation had pulled ahead —
separate `math`/`constants` modules, `constants.edn`-backed physical
constants instead of inline magic numbers, fuller per-module docs, a
portability writeup for the eye-diagram PRNG, CI, and an Apache-2.0
LICENSE — while this repo kept the canonical name policy actually wants.
On 2026-07-07 `si`'s implementation was merged into this repo (namespaces
rewritten from `kotoba.si.*` to `signal-integrity.*`, keeping this
repo's existing flat, non-`kotoba.`-prefixed convention — a `kotoba.`
root prefix belongs to the separate `kotoba-lang/kotoba` core-language
repo and would collide here) and the `si` scaffold was retired for real.

## Modules

* `signal-integrity` — shared vocabulary and overview doc.
* `signal-integrity.constants` — physical/empirical constants for the
  domain namespaces below (`:tline/*` `:crosstalk/*` `:eye/*`), extracted
  from `kami-si`'s Rust `const` definitions and inline magic numbers into
  `resources/signal_integrity/constants.edn` (JVM: read via
  `clojure.edn`; cljs: an inlined literal, since ClojureScript has no
  `io/resource`).
* `signal-integrity.math` — cross-platform (JVM/cljs) math primitives
  (`sqrt`/`ln`/`log10`/`exp`/`floor`/`pow`/`abs`/`pi`) used by the domain
  namespaces below, per this monorepo's `#?(:clj ... :cljs ...)`
  convention (`kami-si::transmission_line`, `::crosstalk`,
  `::eye_diagram`, `::s_param`).
* `signal-integrity.transmission-line` — characteristic impedance
  (`calculate-z0`), propagation delay, and loss for microstrip
  (IPC-2141), stripline, and coplanar-waveguide geometry
  (`kami-si::transmission_line`).
* `signal-integrity.crosstalk` — near-end (backward/NEXT) and far-end
  (forward/FEXT) crosstalk coupling between adjacent transmission lines
  (`analyze-crosstalk`) (`kami-si::crosstalk`).
* `signal-integrity.eye-diagram` — eye-diagram waveform sample generation
  (`generate-eye-data`) and quality metrics (height, width, jitter, BER
  estimate) for serial link analysis (`kami-si::eye_diagram`).
* `signal-integrity.s-param` — 2-port S-parameter summary metrics
  (`metrics`) and Touchstone `.s2p` export (`export-touchstone`)
  (`kami-si::s_param`).
* `signal-integrity.ibis-adapter` — derives `eye-diagram/generate-eye-data`
  parameters from a real IBIS I/O buffer model
  (`kotoba-lang/org-ibis`'s `ibis.model`): `:amplitude-mv` from the
  buffer's `:pullup`/`:pulldown` V-I table voltage swing, and
  `:rise-time-ps` from the `[Ramp]` section's dV/dt. Link-level params
  the buffer model doesn't know about (`:bit-rate-gbps` `:noise-rms-mv`
  `:jitter-rms-ps` `:num-bits`) still come from the caller — see below.

Physical/empirical constants (trace thickness, speed of light, coupling
coefficients, LCG parameters, etc.) live in
`resources/signal_integrity/constants.edn`, loaded at runtime by
`signal-integrity.constants/constants` and consumed by each domain
namespace.

## Usage

```clojure
(require '[signal-integrity.transmission-line :as tl]
         '[signal-integrity.crosstalk :as xt]
         '[signal-integrity.eye-diagram :as eye]
         '[signal-integrity.s-param :as sp])

(let [tline (tl/microstrip {:width 0.2 :height 0.2 :er 4.3})
      params (tl/calculate-z0 tline 25.0)]
  params)
;; => #:tline{:z0-ohm 62.7... :delay-ps-per-mm 8.5... :loss-db-per-mm 0.0016... :length-mm 25.0}

(xt/analyze-crosstalk victim-params aggressor-params 10.0 #_coupling-length-mm
                       0.2 #_spacing-mm 50.0 #_rise-time-ps)
;; => #:crosstalk{:victim-net "victim" :aggressor-net "aggressor"
;;                :coupling-type :backward :peak-mv ... :width-ps ...}

(eye/generate-eye-data {:bit-rate-gbps 10.0 :amplitude-mv 800.0 :rise-time-ps 30.0
                         :noise-rms-mv 10.0 :jitter-rms-ps 5.0 :num-bits 100})
;; => #:eye{:samples [[t-ps v-mv] ...] :metrics #:eye{:height-mv ... :width-ps ...
;;                                                     :jitter-rms-ps ... :jitter-pp-ps ...
;;                                                     :ber-estimate ...}}

(sp/export-touchstone (sp/s-parameter {:freq-ghz [...] :s11 [...] :s21 [...] :s12 [...] :s22 [...]}))
;; => "! Touchstone .s2p generated by signal-integrity\n# GHz S MA R 50\n..."

;; Deriving eye-diagram params from a real IBIS buffer model
;; (kotoba-lang/org-ibis) instead of hand-picking amplitude/rise-time:
(require '[ibis.model :as ibis-model]
         '[signal-integrity.ibis-adapter :as ibis-adapter])

(let [model (ibis-model/model
             {:name "OUTPUT_3V3" :model-type :output
              :pullup [[1.0 0.01] [3.3 0.08]]
              :pulldown [[0.0 0.0] [1.0 0.05]]
              :ramp {:dv 0.8 :dt 2.0e-10 :r-load 50.0}})]
  (ibis-adapter/eye-data-from-ibis
   model
   {:bit-rate-gbps 5.0 :noise-rms-mv 10.0 :jitter-rms-ps 5.0 :num-bits 100}))
;; => #:eye{:samples [...] :metrics #:eye{...}}
;; :amplitude-mv/:rise-time-ps came from the model's V-I tables/ramp;
;; :bit-rate-gbps/:noise-rms-mv/:jitter-rms-ps/:num-bits are link-level
;; and always come from the caller — see `signal-integrity.ibis-adapter`'s
;; namespace docstring for why the split is drawn there.
```

## Testing / linting

```bash
kbb -M:test
kbb -M:lint
```

Status: 14 tests / 30 assertions, 0 failures, 0 errors (8 tests ported
1:1 from `kami-si`'s Rust `#[cfg(test)]` modules across the 4 domain
namespaces, +1 `coplanar-z0-positive` test exercising the third geometry
kind — not in the original Rust suite, +1 `namespace-loads` smoke test
carried forward from this repo's pre-merge test suite, +4 tests /
16 assertions for `signal-integrity.ibis-adapter` — the IBIS-derived
amplitude/rise-time math, its `nil`-safe handling of a missing/partial
`[Ramp]`, the buffer-vs-link param split in `model->eye-params`, and an
end-to-end `eye-data-from-ibis` run).

## What was ported

All four `kami-si` modules were entirely pure domain math with no
external I/O — the full formula set was ported verbatim:

* **`transmission_line.rs`** — the IPC-2141 microstrip Z0 formula, the
  simplified stripline and coplanar-waveguide closed-form
  approximations, effective-permittivity and propagation-delay formulas,
  and the loss coefficients — all ported term-for-term.
* **`crosstalk.rs`** — the exponential spacing-decay coupling model, the
  NEXT (backward) saturation-length logic, and the FEXT (forward)
  coefficient formula — ported term-for-term.
* **`eye_diagram.rs`** — the bit-pattern generator, the exponential
  rise/fall transition model, the eye-center statistics (mean/sample
  stddev with `n-1` divisor), and the Q-factor/BER formula, plus the
  deterministic PRNG used to generate reproducible noise/jitter — see
  "Portability notes" below for how the PRNG differs by platform.
* **`s_param.rs`** — the insertion-loss / return-loss / 3dB-bandwidth
  metrics (dB = `20*log10(|S|)`) and the Touchstone `.s2p` exporter,
  including a from-scratch port of Rust's `{:.6e}` scientific-notation
  formatting (unsigned, unpadded exponent — distinct from Java's `%e`),
  since the Rust test suite only asserts on the exported format's
  structure (header + line count), not exact digit strings.

## Portability notes: the `eye-diagram` PRNG

`signal-integrity.eye-diagram/generate-eye-data` needs a deterministic
PRNG to generate reproducible noise/jitter samples, matching the Rust
port's inline `next_rand` closure — a Knuth MMIX-style 64-bit LCG
(multiplier `6364136223846793005`, increment `1442695040888963407`, seed
`0xDEAD_BEEF_CAFE_1234`).

* **JVM**: runs the *exact* Rust LCG on a primitive `long`. Wraparound
  multiply/add on a two's-complement `long` is bit-identical to Rust's
  `u64::wrapping_mul`/`wrapping_add` regardless of whether the 64 bits
  are interpreted as signed or unsigned, so this is a byte-exact port,
  not an approximation.
* **cljs**: ClojureScript has no native 64-bit integer type. Rather than
  pay for `js/BigInt` arithmetic in the per-sample hot loop, the cljs
  branch substitutes a 32-bit xorshift PRNG (seeded from
  `:eye/xorshift32-seed` in `constants.edn`), which cljs's native 32-bit
  bitwise ops handle directly.

The two platforms are therefore **not** bit-identical to each other —
only the JVM branch is byte-exact to the original Rust. This is safe
because the Rust test suite (ported verbatim as this repo's parity
tests) only ever asserts on *structural* properties of the generated
waveform (eye height positive, sample list non-empty, eye width bounded
by the bit period) — never on exact sample values — so both PRNGs
satisfy the same parity tests. If a future consumer needs byte-identical
eye-diagram output between JVM and cljs, swap the cljs branch for
`js/BigInt`-based 64-bit LCG arithmetic (mask to `0xFFFFFFFFFFFFFFFF`
after each multiply/add).

## What was NOT ported, and why

The recovered `kami-si` crate (5 files, all in `src/`) contained no
GPU/OS/wasm-bindgen bridge code, plotting/visualization glue, or
network/file I/O — every function in every module was pure domain math
or a pure data-structure builder. **Nothing was skipped on those
grounds; the port is complete.** The only things not carried over are
Rust-specific mechanics with no Clojure equivalent needed:

* **`serde`/`serde_json` `Serialize`/`Deserialize` derives** on
  `CrosstalkResult`, `EyeDiagramData`, `EyeMetrics`, `SParameter`,
  `SParamMetrics`, `TLineParams`, `TLineType` — a Rust-specific
  serialization concern. Clojure EDN maps (`pr-str` /
  `clojure.edn/read-string`) give this for free; no explicit port
  needed.
* **`thiserror`/`log`/`glam` `Cargo.toml` dependencies** — declared in
  `kami-si/Cargo.toml` for workspace-wide error/logging/vector-math
  conventions but never referenced by any function in `kami-si/src/*.rs`
  (there is no `glam::Vec2`/`Vec3` usage, no `log::*` call, no custom
  `thiserror` error type in this crate). Nothing to port.

If a future need arises for wasm/GPU-side rendering of eye diagrams or
Smith charts, or for a host-side Touchstone file-I/O adapter, that
belongs in a host-adapter layer built directly against the kotoba
runtime — not in this pure-math domain repo, per ADR-2607010000's
host-adapter boundary.

## License

Apache License 2.0.
