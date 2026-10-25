# kotoba-lang/game

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-game` Rust crate
(17874 lines across 30 files, deleted in kotoba-lang/kami-engine PR #82 "Remove Rust
workspace from kami-engine") as part of the **clj-wgsl migration** (ADR-2607010930,
`com-junkawasaki/root`).

KAMI Game: game systems — physics, input, NPC AI, inventory, economy, triggers,
prediction, arena, addons (C5-C15), gameshell, island generation, W Protocol CQRS, and
a suite of minigames (Pokoa creature battler, Ketsu chase, Sabi-Otoshi rust-restoration,
Battle Royale, ranked matchmaking).

## Restoration method

Restored as a **7-cluster parallel restoration** (owner decision 2026-07-02) given the
crate's exceptional size (10x the next-largest restoration in this migration). Each
cluster's agent worked in isolation on its own git branch (`game-cluster-a` ..
`game-cluster-g`) against a disjoint set of source files, then all 7 branches were
merged server-side into `main`:

| Cluster | Files | Focus |
|---|---|---|
| A | common, economy, gameshell, input, inventory, platform, prediction, trigger, sprite, addons, arena | core/input systems |
| B | animation, physics, scene, npc | animation/scene/AI |
| C | battle_royale, ranked | battle royale + ranked matchmaking |
| D | brainrot_mesh, pokoa_mesh, voxel_mesh | procedural mesh generation |
| E | island_gen, terrain, voxel, quarry_scene | world/island generation |
| F | pokoa, ketsu, sabiotoshi | minigames |
| G | quality, wproto | quality scoring + wire protocol |

Because clusters worked without visibility into each other's in-progress code, several
files inline small locally duck-typed stand-ins for types that are conceptually "owned"
by another cluster's module — documented inline at each point of use. These are not
reconciled into shared types in this assembly pass (see `src/game.cljk`'s docstring).

## Status

Restored — all 29 original `pub mod` modules ported to CLJC namespaces under
`src/game/`, assembled behind a root `src/game.cljk` (mirroring the original `lib.rs`'s
module list). Every original Rust `#[test]` ported 1:1 (plus additional coverage where
the original module had none), across `test/game/*.cljc`:

**231 tests / 294,148 assertions, 0 failures.**

Pure data + pure functions throughout; no IO/GPU.

## Develop

```bash
kbb -M:test
```
