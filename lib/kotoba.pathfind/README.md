# kotoba-lang/pathfind

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-pathfind`
Rust crate (deleted in kotoba-lang/kami-engine PR #82 "Remove Rust workspace
from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Pathfind: A* grid pathfinding (for tilemaps) + NavMesh point
location (for open 3D worlds). Designed for NPC navigation in
`kami-game`.

## Status

Restored — ported from the original 206-line Rust `lib.rs`, with the
original Rust unit test mirrored 1:1 in `test/pathfind_test.cljk` (+1
smoke test) — 2 tests / 4 assertions, 0 failures. Pure data + pure
functions throughout; no IO/GPU. The open list uses a linear-scan
min-search over a plain vector (adequate for tilemap-sized grids)
rather than a JVM-only `PriorityQueue`, keeping the implementation
portable across JVM/JS.

## Develop

```bash
kbb -M:test
```
