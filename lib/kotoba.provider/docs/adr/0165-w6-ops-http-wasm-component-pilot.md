# ADR 0165: T8.3 ops http-post first :wasm-component package + signed-wasm flip

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0162 http real-bytes, ADR 0164 ops publisher policy

## Context

ADR 0164 gated ops readiness `:signed-wasm :ready` on package
`:artifact-kind :wasm-component`. Http only shipped a core `:wasm-module`
host-import forwarder (ADR 0162), so the flip gate stayed closed.

## Decision

### Component artifact

Ship `http-post-v1.component.wasm` — a **thin Component Model** binary that
imports and re-exports the host `http-post` function (ABI-compatible
param surface). Validated with `wasm-tools` (Component layer version 13).

Registry entry `:http-post-component` with `:artifact-kind :wasm-component`
and `:class :ops-network`. Core module entry `:http-post` retained for
module-level digest continuity.

### Readiness inventory

For readiness kit `:http`:

- `:signed-wasm :ready` (ops-signed-wasm-ready-allowed? true with Component entry)
- kit EDN `:signed-content-addressed-package :ready`
- `:wasm-aot` remains `:partial` (not full compiler-AOT of kit product logic)

### Honesty

- This is **not** a compiler-emitted AOT of `http-v1` kit request/result EDN
- Network I/O still belongs to the host (tender/actor-host)
- Secret stays `:signed-wasm :pending` until a Component lands for it
- Pure-allowlist ADR 0161 is unchanged

### Production claim

`production-signed-allowed?` can clear for http readiness when signed
kit + signed Component receipts are present. Grant-binding production
path follows the same receipts as pure-allowlist once readiness is ready.

## Non-claims

- Not compiler multi-file AOT Component pipeline for ops kits
- Not secret Component
- Not a change to host SSRF / allowlist semantics

## Evidence

- `ops-signed-wasm-ready-allowed?` true for http + `:http-post-component`
- digest match for Component bytes
- readiness `:http` `:signed-wasm :ready`
- secret packaging bar true, signed-wasm flip still false

## Related

- Reliability WBS T8.3
- ADR 0153–0164
