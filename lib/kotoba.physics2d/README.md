# kotoba-lang/physics-2d

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-physics-2d` Rust crate
(deleted in the kotoba-lang Rust removal) as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

## Status

Restored. `src/physics_2d.cljk` is a zero-dep, portable (JVM Clojure + ClojureScript)
1:1 port of the deleted `kami-physics-2d/src/lib.rs` (209 lines): AABB + circle
colliders, brute-force O(n^2) broadphase/narrowphase collision detection, and
impulse-based collision resolution with positional correction over a simple 2D
rigid-body world. Mutating `World2D::step(&mut self, dt)` is modeled as a pure
`(world-step world dt) => world'` function; all other types (`Body2D`, `Collider2D`,
`Contact2D`) are plain CLJC maps.

All original Rust `#[test]`s are ported 1:1 to `test/physics_2d_test.cljk`
(plus a namespace-loads smoke test) — 2 tests / 2 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
## Unified Kotoba backend

`physics-2d.backend/backend` implements the shared `kotoba.physics.contract`
as a `:realtime` backend. Kami Engine and Network Isekai can now pass the same
immutable SI-unit scene envelope used by CAE orchestration. The adapter keeps
entity IDs stable, returns contacts by entity ID, validates frame time and
never presents this impulse approximation as a high-fidelity CAE result.

## Stairs (diagonal traversable zones)

`physics-2d.stairs` adds Castlevania-style diagonal staircases for 2D
side-scrollers (`network-isekai`), as a coarser rectangular "zone" a game loop
queries separately from the collider/body world — it does not participate in
`world-step`. Public API: `make-stair-zone`, `point-in-zone?`,
`aabb-overlaps-zone?`, `slope-y-at`, `resolve-stair-movement`. A zone is
`{:x :y :width :height :dir}` (`:x`/`:y` = bottom-left corner, +y is UP,
matching `physics-2d`'s own gravity convention); `:dir` is `:up-right`
(walking +x climbs) or `:up-left` (walking +x descends). While an entity's
AABB overlaps a zone, call `resolve-stair-movement` each frame instead of
`world-step`'s gravity integration; it snaps the entity's y to the slope
surface and reports `:on-stairs?` so the caller knows when to resume normal
platforming physics.
