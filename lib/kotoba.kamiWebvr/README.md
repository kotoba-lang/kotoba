# kami-webvr

The choice-based scenario engine from `kami-engine-sdk`'s `src/lib/webvr/` module —
ported 1:1 to ClojureScript. Svelte is retired for this module: **there is no TypeScript
here**, only `.cljc` (pure logic, JVM + CLJS) and `.cljs` (the reactive engine + the
network-facing cine bridge).

Originally used by `ai-gftd-cyber-drill` (incident-response training drills), the shape
generalizes to any "choices matter" branching scenario: a `.cljc` state machine
(`kami.webvr.incident-pregel`) drives node-to-node transitions and KPI deltas, a `.cljs`
reactive layer (`kami.webvr.engine`) wraps it in an atom and republishes a scene
descriptor on every transition, and an optional `.cljs` bridge
(`kami.webvr.cine-bridge`) resolves cinematic/panel artifacts from a remote generation
pipeline (or a deterministic offline mock).

## Layout

- `src/kami/webvr/types.cljk` — `IncidentKpi`/`IncidentChoice`/`IncidentNode`/
  `IncidentScenario`/`IncidentState` shapes (plain EDN maps) + `apply-kpi-delta`.
- `src/kami/webvr/incident_pregel.cljk` — `initial-state`/`apply-selection`, the pure
  state machine actually exercised at runtime. The original TS's compiled LangGraph
  `StateGraph` (8 super-steps mirroring this logic, for LangGraph-Studio parity) was
  **not** ported — it was documentation scaffolding never `.invoke()`d by the real engine
  and not covered by any test; see the file's own doc-comment.
- `src/kami/webvr/engine.cljk` — `create-incident-vr-engine`: an atom-backed reactive
  wrapper (Svelte 5 runes → atom) with `publish!`/`select!`/`reset!` and the exact
  1-to-3-calls-per-publish `on-scene` cascade timing preserved from the original.
- `src/kami/webvr/cine_bridge.cljk` — `create-cine-bridge`/`create-mock-cine-bridge`:
  live pod HTTP client + deterministic offline mock (prompt-hash-seeded, regex-derived
  camera hint/mood palette), fetch injectable for testability.

## Test

```bash
npm test                           # pure .cljc (types + incident-pregel), JVM, 9 tests
npm install
amu compile --target wasm32-browser node-test  # cine-bridge + engine, node, 11 tests
node out/kami-webvr-tests.js
```

All 20 tests port the original `webvr.test.ts`/`cine-bridge.test.ts` assertions 1:1
(same fixtures, same expected values) plus 4 new tests covering the engine's
publish/select/reset cascade that weren't previously isolated from the Svelte component
tree.

## Status

Milestone 1 of the `kami-engine-sdk` Svelte→CLJS migration (ADR-2607052000): the
`webvr` module, fully ported (not the incremental "delegate one function, keep the TS
host" shape genko used — `webvr` has no live embedded-HTML host to preserve
compatibility with, so a full-module port was the right increment size here).
`ai-gftd-cyber-drill` (the module's original TS-side consumer) is out of scope entirely
— not a pending follow-up, not migrated, not planned to be.

## License

Apache-2.0.
