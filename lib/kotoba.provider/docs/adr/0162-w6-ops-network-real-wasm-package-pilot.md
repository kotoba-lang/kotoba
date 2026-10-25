# ADR 0162: T8.3 ops/network real non-fixture Wasm package pilot (http-post)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0153 readiness gate, ADR 0159 pure real-bytes pilot, ADR 0161 pure publisher policy

## Context

ADR 0159–0161 landed content-addressed **pure-allowlist** Wasm packages and a
publisher policy that may flip readiness `:signed-wasm :ready` **only** for
`:id :pure-allowlist`. Ops kits (http/secret/…) still used the empty-module
fixture for signed Wasm receipts, so `:wasm-artifact-is-fixture` always
blocked production claims — and there was **no** real ops package bytes path
to content-address at all.

T8.3 residual is production AOT Components for network/secret. Full compiler
AOT Component packaging is not ready; this ADR lands the same **real-bytes**
honesty step ADR 0159 did for pure kits, without falsely flipping
`:signed-wasm` for ops.

## Decision

### Registry + artifact

| piece | role |
|---|---|
| `wasm-packages/http-post-v1.wasm` | real non-fixture core module (host-import forwarder) |
| registry entry `:http-post` | digest, kit-resource → `http-v1.edn`, `:class :ops-network` |
| kit `http-v1.edn` | `:wasm-aot :partial`; signed package stays `:pending` |

### Module shape

Thin forwarder: import `kotoba.http_post` and re-export as `http_post`.
Network I/O remains in the host (kototama tender / actor-host). The module
proves packaging + digest gates, not end-to-end network correctness.

### Honesty gates (unchanged for production)

Ops kits may **not** set readiness `:signed-wasm :ready` under ADR 0161
(`pure-allowlist-kit?` is false for http). Production claim still requires:

1. readiness including `:signed-wasm :ready` (ops: still pending)
2. signed kit EDN + signed Wasm receipts
3. non-fixture artifact (now clearable for http-post)

### Non-claims

- Not a production signed provider for http or secret
- Not a full compiler AOT Component / WIT package
- Does not flip readiness `:signed-wasm` for any ops kit
- Does not implement secret real-bytes pilot in this ADR
- Does not replace capability-http-post definition CIDs

## Evidence

- `verify-wasm-package-digest` for `:http-post`
- `real-wasm-provider-receipt` non-fixture
- http readiness still `production-signed-allowed?` false
- pure-allowlist package count still 8; ops entry separate

## Related

- Reliability WBS T8.3
- ADR 0152–0161
- `kotoba-lang/capability-http-post` (contract-only upstream; follow-up to ship artifact there)
