# kotoba-lang/scene-graph

Zero-dep portable `.cljc` — restored from the legacy `kami-scene-graph` Rust crate
(`kotoba-lang/kami-engine`, `kami-scene-graph/src/lib.rs`, 139 lines, deleted in PR #82
"Remove Rust workspace from kami-engine") as part of the **clj-wgsl migration**
(ADR-2607010930, `com-junkawasaki/root`).

## What this is

A scene DAG with parent/child transform hierarchy and top-down world-transform
propagation. Entities are plain CLJC values (keywords/ints/strings) keyed into a
"world" map of `entity-id -> {:local-transform :world-transform :parent :children :root?}`.
`propagate-transforms` walks from every root entity, composing each entity's local
transform matrix (position/rotation/scale -> 16-element column-major Mat4, glam
`Mat4::from_scale_rotation_translation` conventions) with its parent's already-computed
world matrix. `attach`/`detach` manage the parent/children links.

**Adaptation note**: the original Rust crate stored entities/components in a
`hecs::World` ECS (`hecs::Entity` handles, `world.query`/`world.get`/`world.insert_one`).
hecs is an ECS storage library with no meaningful CLJC equivalent, so it was dropped
entirely — entities are plain map keys and the "world" is a plain CLJC map. The
scene-hierarchy + transform-propagation *behavior* is preserved 1:1; only the
ECS-storage plumbing was adapted.

## Tests

`test/scene_graph_test.cljk` ports the original Rust `#[test] fn test_scene_graph`
1:1 (root at `(10,0,0)`, child at `(5,0,0)`, expects composed world position
`(15,0,0)`), plus a namespace-loads smoke test and additional coverage for
`detach`, identity/default behavior, and multi-level hierarchies made easy to
test by the plain-map adaptation.

**8 tests / 12 assertions, 0 failures, 0 errors.**

## Develop

```bash
kbb -M:test
```
