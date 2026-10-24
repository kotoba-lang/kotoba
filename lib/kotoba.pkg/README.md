# kotoba-pkg

[![CI](https://github.com/kotoba-lang/pkg/actions/workflows/ci.yml/badge.svg)](https://github.com/kotoba-lang/pkg/actions/workflows/ci.yml)

**IC package modeling, wire bond / flip chip bonding diagrams, and thermal
analysis, in pure Clojure.** A [kotoba-lang](https://github.com/kotoba-lang)
capability library, ported from the Rust crate `kami-pkg` (chip packaging:
bonding/package/thermal) that lived in
[`kotoba-lang/kami-engine`](https://github.com/kotoba-lang/kami-engine),
per [ADR-2607010000](https://github.com/com-junkawasaki/root/blob/main/90-docs/adr/2607010000-kotoba-runtime-sdk-cljc-migration.md)
(kami-engine Rust workspace retirement in favor of pure `.cljc` kotoba
authority repos).

No network, no I/O in any domain namespace. Portable `.cljc` across JVM /
ClojureScript / SCI / GraalVM.

## Namespaces

- `kotoba.pkg` — facade re-exporting the public API of the three domain
  namespaces below (mirrors the original crate's `lib.rs` `pub use`).
- `kotoba.pkg.bonding` — wire bond / flip chip / thermo-compression bond
  types, pad locations, and `generate-bond-diagram`.
- `kotoba.pkg.package` — package type constructors (QFP, BGA, CSP, WLCSP,
  SiP, 2.5D/3D chiplet) and `estimate-package` (body geometry + simplified
  thermal-resistance-from-area estimate).
- `kotoba.pkg.thermal` — `thermal-spec` / `calculate-thermal`: junction and
  case temperature from a thermal resistance network, with an empirical
  forced-airflow reduction.
- `kotoba.pkg.registry` — data-only config (geometry clearances, per-package
  body-Z, die-size multipliers, thermal-estimation coefficients, airflow
  reduction exponent). On the JVM, `registry` is loaded from the EDN
  authority resource `resources/kotoba/pkg/registry.edn`; `default-registry`
  is a portable literal mirror for cljs/SCI/GraalVM. All domain constants
  that were hardcoded in the original Rust source were extracted here rather
  than left inline, and `estimate-package` / `calculate-thermal` both accept
  an optional registry override for a different process/technology profile.

## Usage

```clojure
(require '[kotoba.pkg :as pkg])

(pkg/estimate-package (pkg/bga 16 16 0.8) [5.0 5.0])
;; => {:name "BGA-256" :pkg-type {...} :body-size-mm [13.8 13.8 1.2]
;;     :die-size-mm [5.0 5.0] :pin-count 256
;;     :thermal-resistance-jc ... :thermal-resistance-ja ...}

(pkg/calculate-thermal (pkg/thermal-spec 2.0 25.0 5.0 20.0))
;; => {:junction-temp-c 75.0 :case-temp-c 65.0 :power-w 2.0
;;     :ambient-c 25.0 :theta-ja 25.0}

(pkg/generate-bond-diagram
  [(pkg/pad-location "VDD" 0.1 0.1) (pkg/pad-location "GND" 0.2 0.1)]
  [(pkg/pad-location "P1" 1.0 0.5) (pkg/pad-location "P2" 2.0 0.5)]
  (pkg/wire-bond 25.0 150.0))
;; => {:bonds [{:pad-name "VDD" ...} {:pad-name "GND" ...}]}
```

Run:

```sh
kbb -M:test
kbb -M:lint
```

## Port notes

Ported from `kami-pkg` (Rust): `src/lib.rs`, `src/bonding.rs`,
`src/package.rs`, `src/thermal.rs` (recovered from `kami-engine` git history;
the crate had been deleted from the working tree but was never committed as
deleted, so `HEAD` still has it).

- The original crate had **no GPU/OS bridge code** — it depended only on
  `glam`/`serde`/`serde_json`/`log`/`thiserror` in `Cargo.toml`, none of
  which were actually referenced from the packaging domain logic itself.
  All four source files are fully ported; there is nothing unported.
- All `#[test]` cases from `bonding.rs`, `package.rs`, and `thermal.rs` were
  ported as parity tests (`test/kotoba/pkg/*_test.cljc`), plus a few
  additional cases (truncation behavior, fixed-pin-count packages, WLCSP
  geometry, zero-airflow edge case) and a registry EDN/literal parity check.
- Enum variants (`BondType`, `PackageType`) became plain maps tagged with a
  `:bond-type/kind` / `:pkg-type/kind` keyword rather than Clojure records,
  keeping the domain data-oriented and directly serializable.
- Hardcoded numeric constants (package body clearances, per-type body-Z,
  SiP/chiplet die-size multipliers and fixed pin counts, the
  `theta_jc`/`theta_ja` area-based empirical coefficients, and the
  forced-airflow reduction exponent) were extracted into
  `resources/kotoba/pkg/registry.edn` — see `kotoba.pkg.registry`.

## License

Apache License 2.0.
