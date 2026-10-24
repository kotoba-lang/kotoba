# ADR-0001: kami-webvr — full port of kami-engine-sdk's webvr module (local mirror)

## Status
Accepted

## Context

This repo's full architecture decision — why `webvr` was fully ported (not incrementally
delegated like `kami-genko`), why the LangGraph `StateGraph` scaffolding was dropped, and
how this fits the broader `kami-engine-sdk` Svelte retirement plan — lives in the
superproject: `90-docs/adr/2607052000-kami-engine-sdk-svelte-retirement-cljs-migration.md`
and its follow-up increment ADR. This file is a local pointer.

## Decision

- **Full-module port, not incremental delegation.** Genko's `移植#N` pattern (delegate one
  function at a time, keep the TS host, verify in a real browser) exists because
  `genko-embed.ts` is a live, embedded, production HTML runtime — incrementally
  de-risking a rewrite of that specific file matters. `webvr` has no such live host: its
  only real consumer (`ai-gftd-cyber-drill`) supplies its own renderer via `onScene` and
  isn't touched by this port at all. A full, directly-tested module port carries the same
  correctness bar (every original test assertion ported 1:1) without the incremental
  ceremony a live-embed rewrite needs.
- **cljc for pure logic, cljs for the reactive/network layer** — same split
  `net-babiniku`'s `governor.cljc` + `web.cljs` already established: `types.cljc` +
  `incident_pregel.cljc` are 100% pure (JVM-testable via `kbb -M:test`, no browser); `engine.cljs`
  (Svelte runes → atom) and `cine_bridge.cljs` (fetch/canvas) need a JS host, tested via
  shadow-cljs `:node-test`.
- **The compiled `INCIDENT_GRAPH` LangGraph `StateGraph` was not ported.** Confirmed via
  direct reading of the original TS: the real engine calls `applySelection`/`initialState`
  directly, never `INCIDENT_GRAPH.invoke(...)`, and no test exercises the graph. Porting
  non-functional documentation scaffolding wasn't worth the LangGraph-Studio-parity
  benefit it existed for; can be added later as a thin wrapper if that parity is ever
  actually needed.

## Consequences

- 20/20 tests green (9 JVM `kbb -M:test` + 11 CLJS `node-test`), 1:1 against the original
  `webvr.test.ts`/`cine-bridge.test.ts` assertions, plus 4 new engine-cascade tests.
- Consumer migration (wiring `ai-gftd-cyber-drill`'s Svelte side to this instead of
  `kami-engine-sdk`'s `./webvr` export) is explicit follow-up, not this repo's scope.

## References

- `90-docs/adr/2607052000-kami-engine-sdk-svelte-retirement-cljs-migration.md`
  (com-junkawasaki/root)
- `README.md` (this repo)
