# ADR 0158: Content-addressed kit package manifest (T8.3 packaging shape)

- Status: Accepted
- Date: 2026-07-28

## Context

T8.3 residual after signed kit EDN receipts (0154), signed Wasm receipts
(0155), and identity inject (0156–0157) still lacked a single **publish shape**
that binds layers and honestly reports production claim blockers.

## Decision

### `package-manifest`

Builds `:kotoba.kit-package.manifest/v1`:

| field | meaning |
|---|---|
| `:layers :kit-edn` | digest + signed? of kit EDN receipt |
| `:layers :wasm` | digest + signed? + artifact-kind + fixture? |
| `:scores` | readiness scores snapshot |
| `:production-signed-claim?` | true **only** when blockers empty |
| `:blockers` | e.g. `:signed-wasm-not-ready`, `:wasm-artifact-is-fixture` |

### Production claim gates

All must hold:

1. readiness checklist gate (`production-signed-allowed?` / ADR 0153)
2. signed kit EDN receipt
3. signed Wasm receipt
4. **not** a fixture-synthetic Wasm artifact
5. kit EDN digest matches wasm receipt chain (when both present)

### Non-claims

- Does not flip readiness `:signed-wasm` to ready
- Does not emit compiler AOT Components
- Fixture empty-module packages always have non-empty blockers

## Evidence

- `provider.kit-package/package-manifest` + `production-claim-blockers`
- tests: fixture package cannot claim production

## Related

- ADR 0152–0157
- Reliability WBS T8.3
