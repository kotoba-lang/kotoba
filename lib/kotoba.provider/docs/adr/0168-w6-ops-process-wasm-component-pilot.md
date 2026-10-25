# ADR 0168: T8.3 ops process real-bytes + Component (spawn bounds policy)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0164 ops publisher policy, ADR 0167 entropy Component

## Context

Http, secret, and entropy cleared ops `:signed-wasm` via Components. Residual
T8.3 asked for **process**/scoped-fs/git real-bytes/Component. Process spawn
authority is host-injected; pure embeddable surface is **spawn bounds**
(provider.process limits: argc ≤ 32, max-stdout ≤ 65536, timeout ≤ 600000).

## Decision

### Artifacts

| package | kind | role |
|---|---|---|
| `process-spawn-v1.wasm` | `:wasm-module` | pure `process_spawn_bounds_ok(argc, max_out, timeout)` |
| `process-spawn-v1.component.wasm` | `:wasm-component` | embeds core via `wasm-tools component new` |

`:class :ops`. Error codes: -1 empty argv, -2 argc>32, -3 bad max_out, -4 bad timeout, 0 ok.

### Policy surface

`ops-network-kit-names` gains `:process`. Packaging bar + Component gate
apply unchanged.

### Readiness

- process `:signed-wasm :ready`
- kit `:wasm-aot :partial`, `:signed-content-addressed-package :ready`
- host OS spawn (`provider.process-transport`) remains the spawn authority
- basename allowlist / path-command checks remain host-side (not in this pilot)

### Non-claims

- Not ambient process / shell inheritance
- Not basename allowlist encoding in Wasm
- Not scoped-fs/git pilots
- Not compiler-AOT of full kit request/result EDN

## Evidence

- digest match module + Component
- `ops-signed-wasm-ready-allowed?` true for process + Component entry
- production-signed-allowed? true for process readiness

## Related

- Reliability WBS T8.3
- ADR 0164–0167
