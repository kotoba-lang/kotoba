# ADR 0169: T8.3 ops scoped-fs real-bytes + Component (path policy)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0164 ops publisher policy, ADR 0168 process Component

## Context

Http/secret/entropy/process cleared ops `:signed-wasm` via Components. Residual
asked for **scoped-fs**/git. Scoped-fs store is host-injected; pure embeddable
surface is **path policy** (`provider.scoped-fs/resolve-path` rejects).

## Decision

### Artifacts

| package | kind | role |
|---|---|---|
| `scoped-fs-path-v1.wasm` | `:wasm-module` | pure `fs_path_ok(ptr,len)` |
| `scoped-fs-path-v1.component.wasm` | `:wasm-component` | embeds core |

Error codes: -1 empty, -2 too long, -3 NUL, -4 backslash, -5 absolute, -6 home,
-7 escape (`..` / `.` segments), 0 ok. Max path 1024 bytes.

### Policy surface

`ops-network-kit-names` gains `:scoped-fs`. Packaging bar + Component gate
apply unchanged (`:class :ops`).

### Readiness

- scoped-fs `:signed-wasm :ready`
- kit `:wasm-aot :partial`, `:signed-content-addressed-package :ready`
- host root-scoped store remains the I/O authority

### Non-claims

- Not ambient filesystem / OS mounts in the Component
- Not git pilot
- Not compiler-AOT of full kit request/result EDN

## Evidence

- digest match module + Component
- `ops-signed-wasm-ready-allowed?` true for scoped-fs + Component entry
- production-signed-allowed? true for scoped-fs readiness

## Related

- Reliability WBS T8.3
- ADR 0164–0168
