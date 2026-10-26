# ADR-0004 — Unify `lib/actor.*` and `clj/ kototama.*` into one `kototama.*` namespace set

- Status: accepted
- Date: 2026-06-28
- Follows: ADR-0002 (actor-organism runtime lib, `lib/actor/*`), ADR-0003
  (consolidate kototama-clj; the `kototama.*` common lib)

## Context

After ADR-0003 the repo had **two parallel organism/cell libraries**: the runtime
prelude lib `lib/actor/*` (ns `actor.*`: gates/heartbeat/membrane/identity/
atproto/didkey) and the consolidated common lib `clj/src/kototama/*` (ns
`kototama.*`: kotoba/cell/life/leash/emit/organism/gates/core). They overlapped
(both carried gate/heartbeat/membrane shapes) — the ADR-0003 follow-up.

## Decision

**One namespace set, `kototama.*`, homed in `lib/`.** `compile_actor` consumes
the kototama vocabulary directly.

- The common lib moved `clj/src/kototama/*.cljc → lib/kototama/*.cljc`.
- `actor.*` renamed into `kototama.*` and folded into the same home:
  `actor.didkey→kototama.didkey`, `actor.identity→kototama.identity`,
  `actor.atproto→kototama.atproto`, `actor.membrane→kototama.membrane`,
  `actor.heartbeat→kototama.heartbeat`; `actor.gates` **merged** into
  `kototama.gates` (the only true name-clash — my leash check renamed
  `may-draft?→leashed?`, the charter `may-draft?`/`why-refused`/`no-advice?`
  vocabulary kept). `actor:host` ABI moved to `lib/kototama/host.edn`.
- The Rust `ACTOR_PRELUDE` scalar prims renamed `actor-* → kototama-*`
  (the scalar slice of `kototama.gates`); `compile_actor` unchanged in shape.
- `clj/` now holds only the UNSPSC fleet (`kototama.unspsc.*`) + its tests, with
  `:paths` extended to `../lib` so it resolves the common lib from one home.

Result — the unified set:
`kototama.{kotoba, cell, life, gates, leash, didkey, identity, emit, atproto,
membrane, heartbeat, organism, core}` + `kototama.unspsc.*` (the fleet).

## Verification

- bb: `lib/kototama/test_actor.cljk` 6/31 · `test_atproto.cljc` 4/11 ·
  `core_test.clj` 10/36.
- fleet: `cd clj && kbb -M:test` 40/222.
- Rust: `cargo test --target aarch64-apple-darwin` 4/0 (the prelude rename
  compiles to wasm; `compiles_actor_logic_to_wasm` uses `kototama-may-draft?`).

## Consequences / follow-ups

- No more `actor.*`; a cell/organism author requires `kototama.*` only.
- `kototama.heartbeat` (pure idempotent decision) and `kototama.organism` (the
  full loop) coexist — layered, not duplicated.
- etzhayyim **kyoninka**'s emit cell classpath updates to
  `../../com-junkawasaki/kototama/lib` (the unified home) — separate small change
  in the etzhayyim repo.
- Future: have `compile_actor` load `kototama.organism` beats directly as the
  wasm subset grows (today it consumes the scalar prelude slice).
