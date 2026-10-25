# ADR 0159: T8.3 real non-fixture Wasm package pilot (hash-sha256)

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0155–0158 defined signed Wasm **receipts**, identity inject, and
`package-manifest` with production blockers. All automated proofs used the
**empty-module fixture** (`\0asm` + version), so
`:wasm-artifact-is-fixture` always blocked production claims.

T8.3 still needs a path that content-addresses **real** provider module
bytes without falsely flipping readiness `:signed-wasm` to `:ready`.

## Decision

### Registry + loaders

| piece | role |
|---|---|
| `resources/kotoba/lang/wasm-packages/wasm-packages-v1.edn` | name → resource path, expected SHA-256, source repo |
| `hash-sha256-v1.wasm` | real module from `capability-hash-sha256` (`artifacts/provider.core.wasm`) |
| `load-wasm-package-bytes` | classpath load of real package bytes |
| `verify-wasm-package-digest` | content-address check vs registry |
| `real-wasm-provider-receipt` | unsigned receipt with non-fixture `:artifact-kind` |

### Kit + readiness

- Ship `capability-kits/hash-sha256-v1.edn` as packaging surface for the pure
  allowlist pilot.
- Add `:hash-sha256` readiness row with `:signed-wasm :pending` (and
  `:audit :n/a` for pure compute).

### Honesty gates (unchanged)

Production claim still requires **all** of:

1. readiness checklist including `:signed-wasm :ready`
2. signed kit EDN + signed Wasm receipts
3. **not** fixture artifact

This ADR only proves (3) can clear for real bytes. **Do not** set
`:signed-wasm :ready` until host-grant binding + publisher policy for that
kit are complete (network/secret ops kits remain fixture-less and AOT-pending).

### Qualification

Kit `:wasm-aot` may be `:partial` when real module bytes ship and digest-match;
`:signed-content-addressed-package` stays `:pending`.

## Non-claims

- Not a production signed provider for network or secret kits
- Does not replace capability-* repository identity (definition CID)
- Does not compile AOT via compiler wasm path in this PR
- Does not flip readiness `:signed-wasm`

## Evidence

- `provider.kit-package` real-package APIs
- tests: digest match, non-fixture manifest, production still blocked by
  `:signed-wasm-not-ready`

## Related

- ADR 0152–0158
- Reliability WBS T8.3
- `kotoba-lang/capability-hash-sha256`
