# ADR 0120: T8.3 ops kit ids 19–23 in component-model inventory

- Status: Accepted
- Date: 2026-08-01
- Depends: kotoba-lang capability-catalog wire 19–23; provider ops kits
  ADR 0143–0270; component-model v1 inventory (ids 1–18)

## Context

Language catalog and provider kits already use stable wire ids:

| Name | Id | Kit |
|------|----|-----|
| `:fs/transact` | 19 | scoped-fs |
| `:process/spawn` | 20 | process |
| `:secret/get` | 21 | secret |
| `:git/run` | 22 | git |
| `:entropy/draw` | 23 | entropy |

Guest packages call these via `(typed-cap-call <id> :string :string …)`.
WIT emit looks up `component-model-v1.edn` by id and rejected unregistered
ids (`"typed capability has no WIT contract"`). Inventory stopped at 18.

## Decision

1. Append five capability rows with **empty `provider-wasi`** (host-injected
   Kotoba providers, not ambient WASI — same rule as storage/secret-shaped
   host kits).
2. Interface names are kit-scoped (`scoped-fs`, `process`, `secret`, `git`,
   `entropy`); functions match kit operation names.
3. Does **not** add Canonical ABI lowerings for ops request/result variants
   beyond what KIR already supplies at the call site; does **not** flip
   production signed-wasm claims.

## Evidence

- Inventory count 23; unique interface+function pairs
- WIT emit for `typed-cap-call` id 20 with `:string`→`:string` succeeds
- Unregistered id 255 still rejects

## Related

- Closes component-model residual after catalog registration
- Compiler backend-qualification inventory must list ids 19–23
