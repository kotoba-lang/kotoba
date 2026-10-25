# ADR 0166: T8.3 ops secret-get :wasm-component package + signed-wasm flip

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0163 secret real-bytes, ADR 0164 ops publisher policy, ADR 0165 http Component

## Context

ADR 0165 flipped readiness `:signed-wasm :ready` for **http** via a thin
`:wasm-component` package. Secret still only had a core `:wasm-module`
pure name-policy pilot (ADR 0163), so `ops-signed-wasm-ready-allowed?`
stayed false for secret.

## Decision

### Component artifact

Ship `secret-get-v1.component.wasm` produced by
`wasm-tools component new secret-get-v1.wasm` — a Component that **embeds**
the pure name-policy core module (no ambient secret read; no host import).
Validated with `wasm-tools print` (core module + component wrapper).

Registry entry `:secret-get-component` with `:artifact-kind :wasm-component`
and `:class :ops-network`. Core module entry `:secret-get` retained.

### Why embed (not host re-export)

Unlike http-post (network must stay on host), secret's shippable pure surface
is **name validation**. Embedding that policy in a Component is the honest
packaging of the pilot; host-injected fetch remains the authority boundary
outside the Component.

### Readiness inventory

For readiness kit `:secret`:

- `:signed-wasm :ready`
- kit EDN `:signed-content-addressed-package :ready`
- `:wasm-aot` remains `:partial` (not full compiler-AOT of kit request/result)

### Honesty

- Not compiler multi-file AOT of secret kit EDN product logic
- Not host secret transport / env / keychain
- Host-injected named fetch is still required for secret **values**
- Pure-allowlist ADR 0161 unchanged

## Non-claims

- Not a change to secret host transports
- Not process/scoped-fs/git Component path
- Not compiler AOT pipeline completeness

## Evidence

- `ops-signed-wasm-ready-allowed?` true for secret + `:secret-get-component`
- digest match for Component bytes
- readiness `:secret` `:signed-wasm :ready`
- grant-binding production-admissible with signed Component receipts

## Related

- Reliability WBS T8.3
- ADR 0153–0165
