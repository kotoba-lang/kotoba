# kotoba-lang/graph

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-graph` Rust crate
(982 lines across `src/lib.rs`, `src/data.rs`, `src/layout.rs`; deleted in PR #82,
"Remove Rust workspace from kami-engine", `kotoba-lang/kami-engine`) as part of the
**clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

## What's here

- `src/graph/data.cljk` — transforms haisen/systemofsystem JSON (from the `gftd` CLI,
  already parsed into plain keyword maps) into a unified `GraphData` (`{:nodes :edges
  :groups}`). Ported from `data.rs`.
- `src/graph/layout.cljk` — force-directed graph layout (Fruchterman-Reingold style,
  pure `layout -> [layout' running?]` tick function) and the Merkle-DAG-style PCB
  layout (writer apps on top, reader apps on the bottom, shared "collection" nodes
  with >=3 incoming edges rendered as horizontal bus lines). Ported from `layout.rs`.
- `src/graph.cljk` — edge/group color palettes, instance-transform/color/line-vertex
  builders, and orthographic camera-extent helpers for rendering the layouts (mirrors
  the render-glue functions in `lib.rs`; actual GPU rendering stays substrate).

All data is plain maps/vectors (no records, no mutation) — `Vec2`/`[f32;2]` positions
are plain `[x y]` vectors, `Mat4` is a 16-float column-major vector matching
`glam::Mat4::to_cols_array`, and the simulation state is threaded functionally rather
than mutated in place. JVM/JS platform divergence (there is none currently needed here)
would use `#?(:clj ... :cljs ...)` reader conditionals.

## Status

Implemented. The original crate's one `#[test]` (`layout::tests::test_basic_layout`)
is ported 1:1 in `test/graph_test.cljk`, plus additional coverage for `graph.data`
(haisen/SoS JSON transforms, `shorten-label`), `graph.layout` (`pcb-layout`, tick/
reheat/settled semantics), and `graph` (colors, instance builders, camera extents) —
16 tests / 49 assertions, 0 failures.

## Develop

```bash
kbb -M:test
```
