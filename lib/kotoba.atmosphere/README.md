# kotoba-lang/atmosphere

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-atmosphere` Rust crate
(deleted in kotoba-lang/kami-engine PR #82, "Remove Rust workspace from kami-engine") as part of
the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## Status

Restored. Ports the full original crate (523 lines across `src/lib.rs` and `src/wind_field.rs`,
recovered from commit `a8368f9c0d784dbc9d11e8fa8f407aa95c7ce4fa`) to zero-dep portable CLJC:

- `src/atmosphere.cljk` — from `lib.rs`: `DayNightCycle` (sun direction / color / fog color /
  `SkyUniform`), Rayleigh sky-color scattering approximation, `WindSystem` (gusting, Beaufort-style
  direction/speed), `CloudSystem` (wind-driven scroll), and a combined `Weather` snapshot with
  `overcast` / `clear` presets.
- `src/atmosphere/wind_field.cljk` — from `wind_field.rs`: 2-octave hash-based value-noise wind
  field (`sample-wind`, `sample-gust-scalar`), re-exported from `atmosphere` mirroring the
  original `pub use wind_field::{...}`.

Rust structs become plain CLJC maps with keyword keys; `Vec3`/`Vec2` become plain CLJC vectors
`[x y z]` / `[x z]` with local vec-math helpers. Platform divergence (trig, `Math.imul` for
overflow-safe 32-bit hashing on ClojureScript) is isolated behind `#?(:clj ... :cljs ...)` reader
conditionals so the code runs unchanged on the JVM and in ClojureScript.

All 12 original Rust `#[test]`s ported 1:1 to `test/atmosphere_test.cljk` (+1 smoke test) —
12 tests / 115 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
