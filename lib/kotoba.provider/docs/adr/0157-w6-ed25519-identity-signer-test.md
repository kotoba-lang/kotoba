# ADR 0157: Ed25519 identity.sign inject (test-proven)

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0156 defined `identity-signer` without hard crypto deps. Production hosts
need a proven Ed25519 path.

## Decision

- Keep `org-ietf-ed25519` as a **test-only** dependency of provider.
- Prove kit EDN + Wasm fixture receipts round-trip with real Ed25519 sign/verify
  via `identity-signer` inject.
- Production apps remain free to inject kagi/CACAO/other without provider
  taking a hard runtime dep.

## Non-claims

- Does not flip readiness `:signed-wasm`
- Does not ship production AOT Components

## Evidence

- `test/provider/kit_package_test.cljk` `ed25519-identity-signer-kit-and-wasm`
