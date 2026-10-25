# kotoba-lang/actor-ipc

Zero-dep portable `.cljc` — restored from the legacy `kami-engine/kami-core` Rust crate
(`kami-core/src/{lib,actor,ipc,time}.rs`, 572 lines total; deleted in
`kotoba-lang/kami-engine` PR #82 "Remove Rust workspace from kami-engine") as part of the
**clj-wgsl migration** (ADR-2607010930, `com-junkawasaki/root`).

**Renamed from `kotoba-lang/core` to `actor-ipc`** (2026-07-02, owner request) — "core" is
too generic; the restored content is specifically an Actor model plus columnar zero-copy IPC
plus a fixed-timestep clock, so the name now names the capability directly.

## Status

Restored. `kami-core` was "Actor + hecs ECS + KAMI Interface (columnar zero-copy)" — a
network-authoritative actor model plus a columnar zero-copy game-data IPC format plus a
fixed-timestep game clock. All of it ports to pure CLJC data + functions:

- `actor_ipc.cljc` — `EntityId` / `IslandId` / `Tick` type-alias documentation (root `lib.rs`).
- `actor_ipc/actor.cljc` — `Authority`, `ActorType`, `ActorId`, and the standard ECS component
  shapes (`Position`, `Rotation`, `Velocity`, `Scale`, `AnimationState`, `Health`, `MeshId`,
  `MaterialId`) as plain CLJC maps (`actor.rs`).
- `actor_ipc/ipc.cljc` — `Dtype`, `Column`, `Frame`, `Delta`, and `compute-delta`, the columnar
  zero-copy KAMI Interface frame/delta format, including `Delta` wire (de)serialization
  (`ipc.rs`).
- `actor_ipc/time.cljc` — `GameClock`, a fixed-timestep game loop clock (`time.rs`).

**hecs-ECS-to-plain-map adaptation:** the original crate partitioned entity state in a
`hecs::World` (a native archetype-storage ECS). hecs's raw entity-storage internals have no
portable CLJC equivalent and are NOT ported; entities are represented as plain integer IDs
keyed into ordinary CLJC maps instead, matching the pattern used in the sibling
`kotoba-lang/scene-graph` restoration (also originally hecs-based).

**Zero-copy-to-canonical-value adaptation:** the original `Column` held a raw pointer into shared memory
with `unsafe` typed-slice views, and `Delta::to_bytes`/`from_bytes` hand-rolled little-endian
byte packing. CLJC has no raw pointers, so `Column` data is an ordinary typed vector, and the
`Delta` wire is a versioned, bounded `kotoba.value.v1` byte envelope from the org-owned
`kotoba.value.codec`. Float tagging is private to the adapter: actor-facing data remains
ordinary numeric vectors, while the CLJ/CLJS wire identity stays canonical. Legacy EDN
strings are rejected rather than accepted as ambiguously named “bytes.” The runtime
dependency is the kotoba-lang org codec only; Node tooling is test-only and no external
hash package is required by actor IPC.

All 3 original Rust `#[test]`s from `ipc.rs` (`column_size`, `frame_efficiency`,
`delta_roundtrip` — `actor.rs`/`time.rs` had no `#[test]`s in the original crate) are ported
1:1 to `test/actor_ipc_test.cljk`, plus light shape checks for `actor`/`time` and a namespace-load
smoke test plus canonical wire boundary cases: **7 tests / 31 assertions on both JVM and
real ClojureScript/Node, 0 failures.**

Pure data + pure functions throughout; no IO/GPU. Native execution (wgpu / wasmtime / wasmi)
stays substrate.

## Kotoba bounded profile

`src/actor_ipc/bounded_clock.kotoba` is a capability-free Kotoba port of
`actor_ipc.time`'s fixed-timestep `GameClock` (`make-clock`/
`advance-clock`/accessors/`clock-alpha`/`wrap32`), represented as a fixed
4-field record instead of the legacy open map. `actor_ipc.cljc`/
`actor_ipc/actor.cljc`/`actor_ipc/ipc.cljc` stay CLJC oracle (not
reviewed this pass). See
[migration/bounded-clock-v1.edn](migration/bounded-clock-v1.edn) for the
full record.

## Develop

```bash
kbb -M:test
npm ci && npm run test:cljs
```
