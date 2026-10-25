# ADR 0163: T8.3 ops secret real non-fixture Wasm package pilot (secret-get)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0153 readiness gate, ADR 0162 http-post real-bytes pilot

## Context

ADR 0162 shipped the first ops real-bytes package for http-post. Secret still
used empty-module fixtures for signed Wasm receipts. Secret's authority boundary
is **host-injected named fetch** (no list/dump); the only pure, embeddable policy
is name validation (`provider.secret/validate-name`).

## Decision

### Registry + artifact

| piece | role |
|---|---|
| `wasm-packages/secret-get-v1.wasm` | real non-fixture core module (pure name policy) |
| registry entry `:secret-get` | digest, kit-resource → `secret-v1.edn`, `:class :ops-network` |
| kit `secret-v1.edn` | `:wasm-aot :partial`; signed package stays `:pending` |

### Module shape

Export `secret_name_ok(ptr, len) -> i32` implementing the pure name policy
(empty / oversize / path / wildcard / whitespace / NUL → negative codes;
ok → 0). **No host import.** Fetch stays host-injected (`:fetch` transport).

### Honesty gates

Ops kits may **not** set readiness `:signed-wasm :ready` under ADR 0161.
Production claim still requires readiness `:signed-wasm :ready` (ops: pending),
signed receipts, and non-fixture artifact (now clearable for secret-get).

### Non-claims

- Not a production signed secret provider
- Not host secret transport / keychain / env scan
- Not a full compiler AOT Component
- Does not flip readiness `:signed-wasm` for secret

## Evidence

- digest match for `:secret-get`
- non-fixture `real-wasm-provider-receipt`
- secret readiness still production-inadmissible
- pure-allowlist package count still 8

## Related

- Reliability WBS T8.3
- ADR 0145–0146 secret custody
- ADR 0162 http-post pilot
