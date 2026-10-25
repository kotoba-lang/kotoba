# kotoba-lang/kisekae

**kisekae** (着せ替え, "dress-up") — the VRM character editor **domain library**
(ADR-2607071610, `com-junkawasaki/root`). A user-friendly character editor's
whole state is a small, plain-EDN **character spec**: pick a base avatar, swap
its hair/outfit/face/accessory parts from donor VRMs, recolor materials, stamp
your own name/license — and the `.vrm` file is *rebuilt deterministically from
the spec on demand*, never stored as an opaque binary blob of record.

```text
                 ┌──────────────  kisekae (this repo)  ──────────────┐
user's choices → kisekae.spec  → kisekae.edit → kisekae.build ────────→ .vrm bytes
  (plain EDN)    (document)      (pure ops,     (selection + engine     (GLB)
       │                          undo/redo)     calls)
       └── kisekae.store (SpecStore contract; MemSpecStore today,
           kotobase/datomic via the :db-api map as the production follow-up)

engine (NOT here): kotoba-lang/org-vrmc-vrm — parse / decompose (body/hair/
face/outfit/accessory) / compose (skeleton-unifying merge) / export (GLB),
restored from the kami-vrm Rust crate as zero-dep .cljc.
```

## Why an editor *layer*, not an editor *app*

The hard parts of a VRM editor already exist in `kotoba-lang/org-vrmc-vrm`:
`vrm.part/decompose` splits an avatar into swappable parts, `vrm.compose/compose`
merges parts from different documents onto one unified skeleton, and
`vrm.export/export-glb` writes a spec-conformant VRM 1.0 GLB back out. What was
missing is everything *around* the engine — a persisted document model for "what
the user chose," pure edit operations with undo/redo, the selection logic that
turns choices + fetched documents into `compose` inputs, and a storage contract.
That's this library. It is pure `.cljc` with one dependency (the engine) and
**no UI** — a consuming app supplies:

- viewport interaction → [`kotoba-lang/canvaskit`](../canvaskit) (UIScrollView-vocabulary pan/pinch/zoom/hit-test)
- live preview render → [`kotoba-lang/webgpu`](../webgpu) (kami-webgpu, the same render substrate `net-babiniku`/`network-isekai` use)
- "simple mode" controls → [`kotoba-lang/editor`](../editor) (walk the spec EDN, surface every number/color as a slider/picker)
- persistence backend → `kotobase` (datomic-shaped, via the `:db-api` map — see below)

First consumer: **babiniku.net**'s "create your own character" flow
(ADR-2607071600 — user-created characters are the creators its monetization
model serves).

## Design invariants

- **The spec is the artifact.** A character is a small, diffable EDN value; the
  `.vrm` is derived output. This is what makes characters datomic-persistable,
  versionable, and cheap to store.
- **`:body` is never overridable.** The base avatar's body is the canonical
  skeleton `compose` unifies onto; swapping skeletons is a rigging problem this
  editor does not pretend to solve.
- **Part vocabulary comes from the engine.** `kisekae.spec/overridable-kinds`
  derives from `vrm.part/part-categories` — a spec can never name a part kind
  `decompose` won't produce.
- **Fail loudly, never silently substitute.** Unknown edit ops throw; an
  unfetched URL throws; a donor VRM lacking the requested part kind throws. An
  editor that drops an edit or swaps in a part you didn't pick is corrupting
  user work.
- **License metadata is first-class.** `kisekae.build/apply-meta` stamps the
  *user's* name/authors/license into the exported VRM. Whether the base/donor
  models' own licenses permit recomposition is a spec-authoring concern the
  consuming app must surface — build can't check it, and doesn't pretend to.

## Persistence (kotobase / datomic)

`kisekae.store` has two honest layers:

1. `SpecStore` protocol + `MemSpecStore` — the swappable-backend contract
   (the `talent.store` MemStore ≡ DatomicStore precedent). This is what exists
   and is tested today.
2. `spec->tx` / `entity->spec` — the **pure datom mapping** (one entity per
   spec: `:kisekae/id`, `:kisekae/name`, `:kisekae/spec-edn`) that a
   kotobase-backed `SpecStore` transacts through the `:db-api` map
   (`{:q :transact! :db :pull :entid}`, `langchain.kotoba-db/kotoba-api`).
   The mapping is written and tested now; the kotobase-backed record itself is
   a follow-up (wiring, not design).

## Runtime priority (`.cljc`)

Per the repo-wide rule (kototama WASM > ClojureScript > nbb > JVM): every
namespace here is pure, interop-free `.cljc`, executable on cljs today and in
the kototama-compatible subset by construction. No `#?(:kototama ...)` branches
exist anywhere — that reader feature does not exist yet (AGENTS.md, 2026-07-06
decision), and this library doesn't pretend otherwise. Numeric cores (e.g.
future blendshape-weight interpolation) are `.kotoba`-expressible candidates
*when that toolchain matures* — an aspiration recorded here, not a claim.

## Status

Thin slice, real and tested (47 checks, `kbb --backend sci scripts/run-task.cljk kisekae`):

Capability compositor increment (ADR 0002):

- `kisekae.capability` — fail-closed scoped authority for asset read, compose,
  preview, export and publish; a URL/CID alone is never authority.
- `kisekae.compositor` — portable CLJC phase plan and Murakumo job envelope.
- `:op/set-base` — body changes select a new skeleton anchor and force skin
  rebind semantics; body is still not treated as an ordinary donor part.
- `:op/set-expression` and persisted preview expression defaults.

- `kisekae.spec` — character-spec document, validation (problem list, not a
  bare boolean), fetch-list derivation.
- `kisekae.edit` — ops (`:op/rename`, `:op/set-meta`, `:op/add-part` with
  replace-per-kind dress-up semantics, `:op/remove-part`,
  `:op/set-base-color`), op-log history with undo/redo + redo-tail truncation.
- `kisekae.build` — `effective-sources` (base parts minus overridden kinds +
  donor parts, skeleton-base tracking), `apply-material-edits`, `apply-meta`,
  `build-document`/`export-bytes` delegating to the engine.
- `kisekae.store` — `MemSpecStore` + the pure kotobase datom mapping.

**Not yet built** (follow-ups, in rough order):

- Full `compose` → `export-glb` integration test against a real fixture `.vrm`
  (unit tests use synthetic documents that exercise selection/transforms but
  not buffer merge — the engine's own 116-assertion suite covers its side).
- The kotobase-backed `SpecStore` record (`:db-api` wiring).
- The editor **app** (canvaskit viewport + kami-webgpu live preview +
  kotoba-lang/editor controls) — a consumer of this library, likely first
  materializing inside babiniku.net's character-creation flow.
- Expression/blendshape default edits, texture swaps, spring-bone parameter
  edits — engine supports all three; specs/ops for them are additive.

## Develop

```bash
kbb --backend sci scripts/run-task.cljk kisekae   # the contract gate (47 checks; non-zero exit on failure)
kbb --backend sci scripts/run-task.cljk lint      # clj-kondo across src + test
```

It was `kbb -M:kisekae` until 2026-08-13. babashka was retired as this workspace's
script host by ADR-2607173000, and that conversion left `scripts/tasks.edn` a
literal empty registry — so the gate this README pointed at had no runnable
entrypoint for four weeks (ADR-2608131600). It is registered again now, running
the same `test/kisekae_test.cljk` under JVM Clojure instead of babashka; measured
2026-08-13 as `Kisekae gate: 47/47 passed`. The count in this block also said 33,
which had been stale for some time.

Requires checkout at the canonical monorepo location
(`orgs/kotoba-lang/kisekae`, sibling to `org-vrmc-vrm` and `org-khronos-glb`)
— `deps.edn`/`bb.edn` use sibling relative paths, the kotoba-lang convention.

## License

MIT — kotoba-lang.
