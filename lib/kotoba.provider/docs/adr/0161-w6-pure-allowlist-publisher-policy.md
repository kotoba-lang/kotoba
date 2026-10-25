# ADR 0161: Pure-allowlist publisher policy (T8.3 signed-wasm flip)

- Status: Accepted
- Date: 2026-07-31
- Depends: ADR 0153 readiness gate, ADR 0159 real wasm, ADR 0160 grant-binding

## Context

ADR 0159 deferred readiness `:signed-wasm :ready` until **host-grant binding +
publisher policy** complete. ADR 0160 landed grant-binding. Ops/network kits
still lack real AOT Components, but pure-allowlist packages already ship:

- real non-fixture wasm bytes (8 modules)
- digest registry
- signed kit + signed wasm receipt APIs
- host-admissible grant bindings

Without a written publisher policy, production claim stays blocked forever
even for pure modules that are already content-addressed and signable.

## Decision

### Scope

**Only** kits with readiness `:id :pure-allowlist`. Never http / secret /
process / scoped-fs / git / storage ops kits.

### Policy (`pure-allowlist-publisher-policy-satisfied?`)

A pure-allowlist kit may set readiness `:signed-wasm :ready` when:

1. `:id` is `:pure-allowlist`
2. `schema`, `dual-runtime`, `deny-fixtures`, `quota`, `package`, `host-parity`
   are `:ready`
3. `audit` is `:ready` or `:n/a` (pure compute)
4. Optional registry package-entry is non-fixture and digest-matches bytes

### Production claim path (unchanged shape)

`production-signed-allowed?` / empty `production-claim-blockers` still require:

1. readiness including `:signed-wasm :ready` (now true for pure allowlist)
2. signed kit EDN + signed wasm receipts
3. non-fixture artifact

### Inventory

Flip all 8 pure-allowlist rows in `kit-readiness-v1.edn` to
`:signed-wasm :ready`. Kit EDN qualification
`:signed-content-addressed-package` → `:ready`. Ops kits stay pending.

## Non-claims

- Does **not** land ops/network AOT Components (http/secret remain pending)
- Does **not** claim compiler native/wasm AOT pipeline is complete
  (`:wasm-aot` stays `:partial` on pure kits)
- Does **not** replace capability-* definition CIDs
- Does **not** make fixture packages production-admissible

## Evidence

- `provider.kit-package/pure-allowlist-publisher-policy-satisfied?`
- grant-binding production-admissible for math-sin with signed receipts
- secret still production-inadmissible (fixture + signed-wasm pending)

## Related

- Reliability WBS T8.3
- ADR 0153–0160
