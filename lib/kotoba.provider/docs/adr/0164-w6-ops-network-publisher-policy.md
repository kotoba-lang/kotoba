# ADR 0164: T8.3 ops/network publisher policy (packaging bar vs signed-wasm flip)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0153 readiness, ADR 0161 pure-allowlist publisher policy,
  ADR 0162 http-post real-bytes, ADR 0163 secret-get real-bytes

## Context

ADR 0161 flips readiness `:signed-wasm :ready` **only** for pure-allowlist kits.
ADR 0162–0163 shipped real non-fixture ops wasm for http-post and secret-get,
but left ops without a written publisher policy. Residual T8.3 asked for an
**ops publisher policy before `:signed-wasm :ready`**.

Ops packages are not pure compute: http-post is a host-import forwarder;
secret-get ships pure name policy while fetch stays host-injected. Flipping
`:signed-wasm :ready` on thin `:wasm-module` pilots would over-claim AOT
Component readiness.

## Decision

### Packaging bar (`ops-network-publisher-policy-satisfied?`)

An ops kit (readiness name `:http` or `:secret`) clears the packaging bar when:

1. not pure-allowlist
2. `schema`, `dual-runtime`, `deny-fixtures`, `quota`, `package`, `host-parity`
   are `:ready`
3. `audit` is `:ready` or `:partial` (ops host surfaces may be partial)
4. registry package-entry is non-fixture, `:class :ops-network`, digest-matches

Today's http-post and secret-get pilots **satisfy** this bar.

### Signed-wasm flip gate (`ops-signed-wasm-ready-allowed?`)

Readiness `:signed-wasm :ready` for ops is allowed only when:

1. packaging bar is satisfied
2. package-entry `:artifact-kind` is `:wasm-component` (full AOT Component)

Current pilots are `:wasm-module` → gate **false**. Kit-readiness keeps
`:signed-wasm :pending`.

### Production claim path

Unchanged: `production-signed-allowed?` still requires readiness
`:signed-wasm :ready` plus signed non-fixture receipts. Ops remain
production-inadmissible until a Component lands and readiness flips.

## Non-claims

- Does **not** flip http/secret `:signed-wasm` to `:ready`
- Does **not** ship full AOT Components
- Does **not** replace host secret/http transport authority
- Does **not** change pure-allowlist ADR 0161

## Evidence

- `provider.kit-package/ops-network-publisher-policy-satisfied?`
- `provider.kit-package/ops-signed-wasm-ready-allowed?`
- tests: packaging true for http/secret real-bytes; signed-wasm flip false

## Related

- Reliability WBS T8.3
- ADR 0152–0163
