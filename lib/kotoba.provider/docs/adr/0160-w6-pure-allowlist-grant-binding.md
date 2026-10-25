# ADR 0160: Pure allowlist wasm set + host-grant digest binding (T8.3)

- Status: Accepted
- Date: 2026-07-28

## Context

ADR 0159 shipped a single real wasm pilot (`hash-sha256`). Pure allowlist
capability packages (sin/cos/sha256/cbor/json/clock/random/now-days) already
publish `artifacts/provider.core.wasm` in their repos, but provider packaging
only listed one. Hosts still had no API to **bind a grant key** to content
digests before admitting a package.

## Decision

### 1. Full pure allowlist registry

`wasm-packages-v1.edn` lists all eight pure allowlist modules with expected
SHA-256 digests and kit-resource paths. Matching thin kit EDNs and readiness
rows ship under `:id :pure-allowlist`. Qualification stays:

- `:wasm-aot :partial` (real bytes present; not full AOT Component pipeline)
- `:signed-content-addressed-package :pending`
- readiness `:signed-wasm :pending`

### 2. Host-grant digest binding API

| fn | role |
|---|---|
| `grant-key` | canonical multi-line key (format, kit, digests, key-id) |
| `grant-binding` | build binding from signed receipts + optional registry check |
| `verify-grant-binding` | re-check digests/key-id/grant-key (not crypto) |

### Host vs production admissibility

| flag | requires |
|---|---|
| `:host-admissible?` | signed kit + signed wasm, non-fixture, digest chain, optional registry match |
| `:production-admissible?` | host-admissible **and** empty production blockers (includes readiness `:signed-wasm :ready`) |

Hosts may store host-admissible bindings for **reference** pure providers.
They must **not** treat host-admissible as production-signed until
`:production-admissible?` is true.

### Non-claims

- Does not flip readiness `:signed-wasm` for any kit
- Does not implement crypto re-verify inside `verify-grant-binding` (use
  `verify-kit-package-receipt` / `verify-wasm-provider-receipt` first)
- Does not ship ops/network (http/secret) real AOT Components
- Does not replace capability definition CIDs

## Evidence

- eight wasm packages + digest tests
- grant-binding host-admissible for math-sin; production blocked
- fixture path remains host-inadmissible

## Related

- ADR 0155–0159
- Reliability WBS T8.3
- pure allowlist capability-* repos
