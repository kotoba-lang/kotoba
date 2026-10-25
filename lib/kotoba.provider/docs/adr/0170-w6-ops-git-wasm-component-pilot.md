# ADR 0170: T8.3 ops git real-bytes + Component (run bounds policy)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0164 ops publisher policy, ADR 0169 scoped-fs Component

## Context

All ops kits except **git** had real-bytes + Component packages clearing
`:signed-wasm`. Git run authority is host-injected; pure embeddable surface is
**run bounds** (provider.git limits: argc ≤ 64, max-stdout ≤ 65536, timeout ≤ 600000).

## Decision

### Artifacts

| package | kind | role |
|---|---|---|
| `git-run-v1.wasm` | `:wasm-module` | pure `git_run_bounds_ok(argc, max_out, timeout)` |
| `git-run-v1.component.wasm` | `:wasm-component` | embeds core |

Error codes: -1 empty args, -2 argc>64, -3 bad max_out, -4 bad timeout, 0 ok.

### Policy surface

`ops-network-kit-names` gains `:git`. Packaging bar + Component gate apply.

### Readiness

- git `:signed-wasm :ready`
- kit `:wasm-aot :partial`, `:signed-content-addressed-package :ready`
- host git binary / subcommand allowlist / path-escape checks remain host-side

### Non-claims

- Not ambient git/exec
- Not subcommand allowlist encoding in Wasm
- Not compiler-AOT of full kit request/result EDN

## Evidence

- digest match module + Component
- `ops-signed-wasm-ready-allowed?` true for git + Component entry
- production-signed-allowed? true for git readiness

## Related

- Reliability WBS T8.3
- ADR 0164–0169
