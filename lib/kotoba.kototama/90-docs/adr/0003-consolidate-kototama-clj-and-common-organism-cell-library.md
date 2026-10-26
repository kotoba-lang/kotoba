# ADR-0003 — Consolidate kototama-clj into kototama; the common organism/cell library

- Status: accepted
- Date: 2026-06-28
- Supersedes/absorbs: the archived `com-junkawasaki/kototama-clj` repo
- Relates to: ADR-0001 (Clojure→WASM runtime), ADR-0002 (actor-organism runtime
  lib, `lib/actor/*`); etzhayyim ADR-2606281500 (autonomous-publication 種をまく
  doctrine), ADR-2606111400 (revocable CACAO leash), ADR-2605312345 (kotoba Datom
  first-class state)

## Context

The Clojure/organism work was split across two repos:

- **kototama** (this repo) — the Clojure/EDN→WASM runtime (`compile_clj` /
  `compile_game` / `compile_actor`) + the `lib/actor/*` cljc prelude (gates,
  heartbeat, membrane, identity, atproto, didkey).
- **kototama-clj** — a Clojure deps.edn project: a distilled common organism/cell
  library (`kototama.{kotoba,cell,life,leash,emit,organism,gates,core}`) **plus**
  the 18,342-actor UNSPSC fleet (`kototama.unspsc.*`).

Two repos for one concept (kototama) caused drift and a dangling cross-repo
dependency (etzhayyim kyoninka's autonomous-publication cell requires the common
lib). kototama-clj is now **archived (read-only)** on GitHub.

## Decision

**一本化 — consolidate kototama-clj into kototama.** The entire Clojure subtree
moves into this repo under `clj/`:

```
kototama/
  Cargo.toml  src/lib.rs  examples/      # the Rust→WASM runtime (unchanged)
  lib/actor/*.cljc                        # runtime-compiled actor prelude (unchanged)
  clj/                                    # ← consolidated from kototama-clj
    deps.edn                              #   (local roots repointed to ../../<lib>)
    src/kototama/*.cljc                   #   the common organism/cell library
    src/kototama/unspsc/*                 #   the 18,342-actor UNSPSC fleet
    resources/unspsc-taxonomy.edn
    test/kototama/**                      #   10 + 50 tests green
```

The common library is the distilled subset of the kotodama cell framework + the
ibuki organism pattern, dependency-free `.cljc` (bb/JVM + WASM):

| ns | role |
|---|---|
| `kototama.kotoba` | append-only content-addressed Datom log (the DB) |
| `kototama.cell` | `defcell` — pure `solve : state → state` |
| `kototama.life` | joucho (mood) + metabolism, folded off the log |
| `kototama.gates` | charter membrane — `may-draft?` / §2 `scan` / `may-actuate?` |
| `kototama.leash` | revocable member CACAO capability (present-only) |
| `kototama.emit` | member-signed post → app-aozora / com-etzhayyim (never `:published`) |
| `kototama.organism` | the heartbeat `beat`/`autorun` |
| `kototama.core` | re-exports |

Invariants the lib enforces: kotoba Datom log = first-class state; content-
addressed + tamper-evident (`verify-chain`) + idempotent-by-content; no-server-
key (present-only leash, never signs); **publication ≠ actuation** (autonomous
posting on by default per 種をまく; high-stakes actuation behind `may-actuate?`);
§2 content scan before emit; no wall-clock (replay-safe).

### Scope / what is NOT changed here

- The Rust runtime (`src/lib.rs`, `examples/`) and the `lib/actor/*` cljc prelude
  are **untouched** — zero risk to the WASM compile path.
- The `lib/actor.*` prelude and the `clj/ kototama.*` common lib currently
  OVERLAP (both carry gates/heartbeat-shaped code). They are left parallel in
  this consolidation; **unifying the two namespaces is a follow-up** (the runtime
  prelude is compiled standalone, the common lib is a bb/JVM dep — they converge
  once `compile_actor` consumes `kototama.organism` directly).
- The browser/shadow-cljs bits of the old kototama-clj are dropped (the Rust
  runtime already provides the browser compile→run path, ADR-0001).

## Consequences

- One repo named kototama holds the runtime + the common lib + the fleet.
- kyoninka's cross-repo dependency resolves to `kototama/clj` (deps local root).
- Tests green from the new location: `clj` common-lib 10/36 (bb), UNSPSC fleet
  50/258 (`kbb -M:test`).
- The archived kototama-clj remains as a historical pointer; no new work lands
  there.

## Follow-ups

- Unify `lib/actor.*` ⇄ `clj/ kototama.*` (single organism/cell namespace set);
  have `compile_actor` consume `kototama.organism`.
- Wire the live `kotoba_bridge` (real CIDv1 + XRPC) behind
  `kototama.kotoba/->bridge-edn`.
- Add a top-level note in kototama-clj's README pointing here (manual, repo is
  archived/read-only).
