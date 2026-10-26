# ADR-0002 — actor / artificial-organism runtime as the third kototama layer

- Status: accepted
- Date: 2026-06-28
- Supersedes: none · Builds on: ADR-0001 (kototama clojure-wasm-runtime)

## Context

kototama (ADR-0001) is the seam between two compilers, layered:

```
kotoba-clj (general core)  +  kami-engine-clj (GAME_PRELUDE + kami:engine ABI)
        compile_clj                     compile_game
```

A *third* family of programs keeps recurring and had **no shared home**: the
**atproto actors + artificial organisms** of the etzhayyim `20-actors/*` lineage
(iriai / kaname / tsubasa / ibuki / danjo / …). Every one of them re-implements the
same runtime by hand:

- a **self-certifying did:key** identity (Ed25519, present-only, seed sealed — the actor
  holds its own key, the server holds none);
- a content-addressed **commit-DAG** on the kotoba Datom log (idempotent-by-content
  heartbeat, tamper-evident verify-chain);
- a **charter-gate vocabulary** (≥2 sources · cash≡0 · no-server-key · dry-run · sim-only ·
  no-advice) that decides whether an outward act is permitted;
- an **outward self-publication membrane** (dry-run posts; live broadcast Council-gated);
- a **live-engine bridge** (push the local commit-DAG to a kotoba node).

This is exactly the shape ADR-0001 already solved for games — a PRELUDE of helpers written
in the language itself, plus a host ABI for the capabilities the wasm subset can't do
natively. We make the actor runtime the third such layer.

## Decision

Add an **actor/organism layer** to kototama, mirroring the game layer:

| layer | prelude | host ABI | seam fn |
|---|---|---|---|
| core | — | — | `compile_clj` |
| game | `GAME_PRELUDE` (vec/map/timer/vec3) | `kami:engine` | `compile_game` |
| **actor** | **`ACTOR_PRELUDE`** (gate + heartbeat decisions) | **`actor:host`** (crypto/net/storage) | **`compile_actor`** |

1. **`lib/actor/*.cljc`** — the portable common-lib (the "共通 lib"): `actor.gates`,
   `actor.membrane`, `actor.heartbeat`, `actor.didkey`. Pure, dependency-free, deterministic.
   Runs **today** under bb/JVM (the etzhayyim actors converge onto it) and is the readable
   source of truth for the prelude. Tests: `lib/actor/test_actor.clj` (bb).
2. **`ACTOR_PRELUDE`** (`src/lib.rs`) — the scalar slice of the gate/heartbeat decisions that
   compiles under the *current* `compile_clj` subset (which today supports
   `defn/if/let/cond/arith/compare/and/or/not/=/def/do/string/keyword`, but **not** vector/
   map/str/count/reduce literals — those are host helpers). `compile_actor(src)` prepends it
   and emits real wasm (cargo test `compiles_actor_logic_to_wasm`).
3. **`actor:host` ABI** (`lib/actor/host.edn`) — the capability boundary, analogous to
   `kami:engine`: `gen-keypair/sign/verify` (self-key, present-only), `sha256-hex`,
   `http-post` (allowlisted), `log-read/log-append!`, `now`. The pure layers **decide**; the
   host **acts**. The native bb/JVM host implements these today; a wasm host over the same
   imports is next, as kotoba-clj's subset grows byte-vector/map ops.

## Boundaries (kept, not relaxed)

- **no-server-key**: the actor is the *bearer* of capability, never the holder of a custodial
  server key. The host signs *present-only* with the actor's OWN sealed did:key; the seed is
  never exfiltrated (etzhayyim ADR-2605231525).
- **outward broadcast** (AT-proto `:published`) is a governance gate (§1.12 + ADR-2606272355)
  layered ON TOP of this ABI — it is *not* a host function. `actor.membrane/build-live`
  refuses by construction at R0.
- The pure logic never hides I/O: it returns a *decision*; the host performs the effect.

## Consequences

- One canonical actor runtime instead of N hand-copied ones; the etzhayyim actors converge
  onto `actor.*` and shrink.
- The same CLJ that runs an actor under bb/JVM can compile (its scalar gate slice today, more
  as the subset grows) to a wasm Component — the path to running actors browser-local / on the
  donated mesh (etzhayyim "One Worker, many WASM actors").
- License: MIT (kototama) — the lib is dependency-free and portable.

## Status of this cut

- `compile_actor` + `ACTOR_PRELUDE` + tests: **landed, wasm-verified** (cargo test green).
- `lib/actor/{gates,membrane,heartbeat,didkey}.cljc` + `test_actor.clj`: **landed, bb-green**.
- `actor:host` ABI: **specified** (`host.edn`); native bb/JVM host exists in the etzhayyim
  actors; a wasm host implementing the imports + widening the prelude beyond the scalar slice
  is the next increment.
