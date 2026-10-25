# ADR 0042: typed-bool-value always-on (remove has-bool-value? gate)

- Status: accepted
- Date: 2026-07-31
- Supersedes: gating claim in ADR 0041 Non-claims

## Decision

Remove the dead `has-bool-value? false` gate and its conditional second
registration of `kotoba:typed/bool-value`. The import remains in the base
typed-import list (always-on), matching emit-get which already calls
`typed-bool-value` for aggregate `:bool` slots.

## Why

Profile 5 (compiler#451) + export wrappers (wasm#42/#44) + host `bool-value`
are landed. The gate no longer protects anything: the base list already
registered the import, so the `when has-bool-value?` branch was unreachable
duplicate code.
