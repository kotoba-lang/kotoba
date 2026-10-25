# ADR 0156: Identity.sign inject adapter for kit package receipts

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0154–0155 define host-injected `sign-fn` / `verify-fn` for kit EDN and
Wasm provider receipts. Tests used HMAC doubles only. Production hosts need a
documented bridge from **identity.sign** (Ed25519 / CACAO / kagi-backed) to the
kit-package contract without hard-coding a crypto backend in the package API.

## Decision

### `provider.kit-package/identity-signer`

Wrap host-provided byte-level primitives:

| inject | type |
|---|---|
| `:sign-bytes` | `(fn [msg-bytes] -> signature-bytes)` |
| `:verify-bytes` | `(fn [msg-bytes pub-bytes sig-bytes] -> boolean)` |
| `:public-key-bytes` or `:public-key-hex` | publisher key |
| `:alg` | default `:ed25519` |
| `:encode` | `:hex` only (receipts stay UTF-8 EDN-friendly) |

Returns `{:sign :verify :key-id :public-key :alg}` compatible with
`sign-kit-package-receipt` / `sign-wasm-provider-receipt`.

### Fixture Wasm resource

`resources/kotoba/lang/fixtures/empty-module.wasm` — empty module bytes for
synthetic receipt demos (`load-fixture-wasm-bytes`). **Not** a production
provider; readiness `:signed-wasm` stays pending.

### Non-claims

- Does not add an Ed25519 runtime dependency to provider (host supplies crypto)
- Does not flip production-signed claim / readiness signed-wasm
- HMAC test double remains for pure unit tests without identity keys

## Evidence

- `identity-signer` + hex encode/decode + fixture load
- `test/provider/kit_package_test.cljk` identity inject round-trip on kit + wasm receipts

## Related

- ADR 0154–0155 signed receipts
- Reliability WBS T8.3 / handoff “Identity inject”
