# kotoba-lang/articulated-scene

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-articulated-scene` Rust crate
(`kotoba-lang/kami-engine`, deleted in PR #82 "Remove Rust workspace from kami-engine") as part of
the **clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## Status

Implemented. `src/articulated_scene.cljk` ports the original 431-line `kami-articulated-scene/src/lib.rs`
1:1: the `:arm/*` EDN authoring surface for an articulated-scene (robot arm) description — tolerant
EDN accessors, `from-edn` parsing into an `ArticulatedSystem` (links + joints), the per-joint actuator
BOM read from `:joint/actuator` (`chain-actuators-from-edn` / `default-bom-from-edn` / `bom-from-edn`
with `:arm/realization :variants` overrides), and `validate-torque` for continuous-torque integrity
checks. The `giemon_arm6` fixture EDN/URDF pair is embedded as string constants
(`giemon-arm6-edn` / `giemon-arm6-urdf`), mirroring the original's `include_str!` constants. Pure
data + pure functions throughout — no IO, no GPU, no solver.

All 5 original Rust `#[test]`s are ported 1:1 to `test/articulated_scene_test.cljk` (plus a small
test-local URDF parser standing in for the out-of-scope `kami_articulated::parse_urdf` oracle, and
the pre-existing `namespace-loads` smoke test) — 6 tests / 136 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
