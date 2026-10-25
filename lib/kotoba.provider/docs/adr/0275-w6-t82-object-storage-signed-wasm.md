# ADR 0275: T8.2 object/storage signed-wasm :ready (pure-bounds Components)

- Status: Accepted
- Date: 2026-08-01
- Depends: ADR 0164 ops publisher policy; ADR 0165–0168 Component pilots;
  ADR 0271–0273 object/storage audit+deny

## Context

T8.2 residual after 0273 was object/storage **`:signed-wasm :pending`**. Ops
kits cleared that gate via non-fixture **wasm-component** pure-bounds packages
(`ops-signed-wasm-ready-allowed?`). Object/storage had no registry Component.

## Decision

1. Ship pure length-bound packages (compiler-AOT core + `wasm-tools component new`):
   - **storage-value-len** / **storage-value-len-component** (max 65536)
   - **object-digest-len** / **object-digest-len-component** (non-empty, max 65536)
2. Extend `ops-network-kit-names` with `:storage` / `:object`.
3. Accept expanded ops package classes in publisher policy entry-ok.
4. Flip kit-readiness **`:signed-wasm :ready`** for object + storage.
5. Does **not** flip host I/O authority / full kit body AOT — pure bounds only
   (same honesty as process-spawn Component pilot).

## Evidence

- Package digests; `ops-signed-wasm-ready-allowed?` true with Component entries;
  readiness tripwire

## Related

- Closes T8.2 signed-wasm residual for object/storage checklist dimensions
