# ADR-0006: Maturity R2 browser parity + R3 fleet skeleton

- **Status:** accepted
- **Date:** 2026-07-10

## Context

R1 made JVM tender operator-ready. Remaining gaps:

1. **R2** — browser path existed (`web/`) but docs understated actor-host
   (gen-keypair/sign/verify already in wasm-webcomponent); no host-free
   fact/peak fixtures in web/; no pure parity matrix in cljc.
2. **R3** — durable multi-tenant outer loop was “planned” with no code.

## Decision

### R2 advanced-partial

- `kototama.browser` parity matrix (7/9 browser-yes; http-post/llm missing in tab)
- `web/host-free-fact.wasm` + `web/host-free-peak-cells.wasm` + `verify-host-free.mjs`
- CI web job runs `verify-host-free.mjs`
- Honest README: browser implements sync crypto+log; not full network

### R3 skeleton

- `kototama.fleet` pure cljc: lease, budget, tick, governor, registry,
  checkpoint/restore, `run-loop-step` with injectable execute
- CLI `fleet-demo`
- Status remains **skeleton** (no cross-node, no durable store)

Declared current level: **R2 advanced-partial** (+ R3 skeleton).

## Consequences

- doctor prints r2 + r3 reports
- R3 production claims still forbidden until not-yet list shrinks
