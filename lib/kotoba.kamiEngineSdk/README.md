> **Renamed 2026-07-10 (ADR-2607102200 addendum):** `kotoba-lang/kami-engine-sdk` → `kotoba-lang/kami-engine-sdk`
> (`-clj` suffix dropped — this is the only engine SDK). The former Svelte package
> that briefly held the name `kami-engine-sdk` was renamed to
> `kami-engine-sdk-svelte` and then **archived / pruned**.

# kami-engine-sdk

KAMI Engine's Clojure/ClojureScript authoring SDK: author KAMI scenes, ECS,
and render pipelines in **Clojure/ClojureScript** with **Datomic-flavored
Datalog** (datalevin by default) as the source of truth, while the GPU work
stays on the proven `kami-render` (Rust/wgpu) backend, reached over a small
**render-IR** contract. clj is the brain, Rust is the GPU arm.

Full design doc: [`ARCHITECTURE.md`](./ARCHITECTURE.md).

In short:
- **`kami.scene` / `kami.db`** — a scene is a set of Datomic-style datoms; an
  ECS component is an attribute; editing is `transact`, undo is `as-of`,
  queries are Datalog.
- **`kami.ecs` / `kami.sim`** — the durable Datalog store is projected into a
  dense in-memory ECS for the 60 fps tick; Datomic is consulted only at
  load/save boundaries, never per frame.
- **`kami.render` / `kami.wgsl-emit` / `kami.ipc`** — a pure-data render-IR (draw
  lists, instancing) is built from the ECS each frame, shaders can be
  authored as clj data and lowered to WGSL, and the frame is packed into the
  zero-copy KAMI IPC columnar buffer.
- **`kami.gpu` / `kami.backend.browser` / `kami.backend.host`** — the
  `IGpuBackend` protocol dispatches `submit-frame` to the Rust GPU host
  (`kami-clj-host`, in the source monorepo), which decodes the exact bytes
  `kami.ipc/pack` emits and drives `kami-render`'s wgpu pipelines. This SDK
  does not reimplement wgpu — GPU execution remains Rust.
- **`wit/kami-frame.wit`** — the proposed additive WIT contract
  (`kami:engine/frame@1.0.0`) for the clj ↔ Rust boundary: upload-once
  resource registration (mesh/material/shader) plus one `submit-frame` call
  per frame.
- **`kami.benchmark`** — the shared sample-game benchmark contract: validates
  2D/3D genre manifests, resolves `:playable` / `:showcase` / `:meltdown`
  quality tiers, records portable telemetry frames, and drives capped meltdown
  load ramps. It also validates fixed-step scenarios, runs pure headless
  fixtures with a canonical deterministic digest, validates result envelopes,
  and compares candidates to hardware-profile baselines (including the ADR's
  10% p95 regression gate). See `resources/kami/samples/isekai-swarm.edn` for
  a manifest and reduced-CI scenario that can be consumed unchanged by Studio,
  browser, native, and headless runners. `deterministic-digest` is a portable
  replay/correctness marker, not a cryptographic integrity hash.
  It also validates Studio's `kami.performance-plan/v1` and runs its 2D/3D
  saturation ramp through an injected host measurement adapter, computing p95
  and stopping on the first frame-time or memory-budget violation.
- **`kami.sample-manifest`** — pure-data M5 catalog authoring helpers. `scaffold`
  creates schema-v2 EDN, `migrate-manifest` explicitly upgrades legacy v1 data,
  and `valid?` checks capability, lifecycle, license, and public source/fork/
  play/benchmark URLs. `valid-matrix?` gates 2D and 3D fixture coverage without
  making performance or visual-quality claims. Persistence remains a Studio or
  build-tool concern.
- **`kami.network`** — the M2 multiplayer thin contract: versioned input
  envelopes, per-client authoritative sequence acceptance, tick/client/sequence
  total ordering, snapshots with acknowledgements, client reconciliation with
  pending-input replay, and deterministic loss/delay/jitter injection. It is a
  pure-data transport seam, not a production socket stack or an 8-player
  performance claim. `resources/kami/samples/nightglass-strike-m2.edn` describes
  the reduced eight-bot contract fixture used by tests.
- **`kami.world-partition` / `kami.avatar`** — M3 portable thin contracts.
  World partition provides deterministic distance LOD, explicit cell lifecycle,
  and nearest-first estimated-byte budget planning. Avatar provides a bounded
  distance/capacity quality sweep plus ordered, idempotent RTC peer-state data.
  The Ashen Kingdom and Dream Stage fixtures under `resources/kami/samples/`
  are reduced contract checks only: no world-streaming throughput, VRM visual
  quality, WebRTC concurrency, frame-time, or other performance result has yet
  been measured.

## Origin

This repository was split out of
[`kotoba-lang/kami-engine`](https://github.com/kotoba-lang/kami-engine)'s
`kami-engine-sdk/` subtree, following the same pattern previously used to
split `kami-mangaka-genko-clj` into
[`kotoba-lang/kami-genko`](https://github.com/kotoba-lang/kami-genko). This
was a live, working Clojure project inside the monorepo — not a restoration
of deleted code.

**This is a different project from
[`kotoba-lang/kami-engine-sdk`](https://github.com/kotoba-lang/kami-engine-sdk)**
(no `-clj` suffix), which is an unrelated public mirror of a Svelte 5 UI
component library (VRM character components, Genko manga editor UI, trackpad
embeds). Do not confuse the two:

| Repo | What it is |
|---|---|
| `kotoba-lang/kami-engine-sdk` (this repo) | Clojure/ClojureScript scene/ECS/render-IR/WIT contract SDK for kami-engine |
| `kotoba-lang/kami-engine-sdk` | Svelte 5 UI component library mirror (unrelated) |

## Status

Design + working core + GPU bridge (as of the source snapshot, 2026-06-13).
The clj contract layer (`kami.scene`, `kami.ecs`, `kami.render`, `kami.wgsl-emit`,
`kami.ipc`, `kami.gpu`, `kami.sim`, `kami.math`, etc.) is implemented and
covered by tests. `kami.backend.browser` (the live WASM/WebGPU bridge) and
`kami.backend.host` (an optional headless backend) are stubs — see
`ARCHITECTURE.md` §10 for the full namespace status table.

## Dependencies / build notes

Unlike some sibling `kami-*-clj` splits, this project has **no `:local/root`
path dependency** on `../../kotoba/crates/kotoba-edn` or any other sibling
monorepo directory — `deps.edn` only pulls Maven coordinates (Clojure,
`transit-clj`/`transit-cljs`, `datalevin`, `shadow-cljs`,
`org.clojure/clojurescript`, `data.json`, the cognitect test-runner). As a
result the project runs standalone out of the box with no dependency
breakage.

What does still reference the original monorepo (not exercised by `:test`,
documented rather than fixed here per the migration plan):
- `dev/gen_fixture.cljk` / `dev/gen_demo.cljk` write cross-language fixtures
  intended for `../kami-clj-host/tests/fixtures/` and `../kami-clj-host/demo/`
  in the monorepo — those paths do not exist in this standalone repo.
- `ARCHITECTURE.md` §12's Rust build/test steps (`kami-clj-host`,
  `kami-render`) refer to sibling Rust crates that live in `kami-engine`, not
  here.
- `ARCHITECTURE.md` itself is the clj-side sibling of `kami-engine`'s
  top-level `ARCHITECTURE.md` and references `../kami-clj`, `../kami-render`,
  `../kami-core`, `../AGENTS.md`, etc. — all relative to the original
  monorepo layout.

## Running tests

```bash
kbb -M:test
```

Verified on this standalone repo: **66 tests / 308 assertions, 0 failures,
0 errors.**

Other aliases (see `deps.edn`):
- `kbb -M:dev` — JVM authoring REPL (Datomic/datalevin source of truth)
- `kbb -M:roundtrip` — real-datalevin round-trip (connect → tx → snapshot →
  ECS → render-IR → pack → commit)
- `kbb -M:shadow watch app` — browser ClojureScript build (needs a
  `shadow-cljs.edn` build config, not included in this split)
