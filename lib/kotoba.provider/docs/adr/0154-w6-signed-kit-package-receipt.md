# ADR 0154: T8.3 first slice — signed kit package receipts

- Status: Accepted
- Date: 2026-07-28

## Context

T8.3 asks for network/secret **signed** reference providers. Full signed Wasm
Components (content-addressed Component + host grant binding) is XL. After
unsigned kit fingerprints (ADR 0152–0153), we need a **honest intermediate**:
prove a publisher signed the **kit EDN package** without claiming Wasm AOT.

## Decision

### Layers

| layer | claim | status |
|---|---|---|
| Unsigned kit EDN SHA-256 | content-address of package text | landed (#35) |
| **Signed kit EDN receipt** | host-injected sign over digest+resource | **this ADR** |
| Signed Wasm provider Component | production T8.3 end state | **still pending** |

### API (`provider.kit-package`)

- `signing-input` — canonical message: format / sha256 / digest / resource path
- `sign-kit-package-receipt` — host `sign-fn` inject (identity.sign / HMAC test)
- `verify-kit-package-receipt` — host `verify-fn` inject
- `test-hmac-signer` — deterministic test double (not production identity)

### Non-claims

- Does **not** flip kit `:signed-wasm` or `:signed-content-addressed-package` to ready
- Does **not** set `production-signed-claim-allowed?` true
- Does **not** produce a Component / Wasm AOT artifact

### Production identity

Hosts SHOULD inject `identity.sign` / `identity.verify` (capability contract).
HMAC test signer is for unit tests only.

## Evidence

- `src/provider/kit_package.cljk` signed receipt path
- `test/provider/kit_package_test.cljk` sign/verify round-trip + forgery reject

## Related

- ADR 0153 kit ready checklist (signed-wasm gate)
- Reliability WBS T8.3
