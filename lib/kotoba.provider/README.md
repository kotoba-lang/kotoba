# provider

Narrow, capability-gated host adapters — the named providers a runtime binds after aiueos grants.

**Tier**: `T3`  **Role**: `provider`

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside.

## Owns

- `provider.conformance (the shared provider contract)`
- `provider.clock / .http / .llm / .log / .state / .storage / .ui`
- `provider.dataspace` (Syndicate-style document tuple space; member of the
  application closed set, wire id 24).
  Each assertion is a distinct provider-local publication: explicit retract
  and facet leave affect only the facet that published it, even when another
  facet asserted structurally equal documents.
- `their -transport backings`

## Does not own

- be linked into a compiler
- grant itself authority
- expose ambient WASI

## Depends on

- nothing (contract/leaf tier)

## Test

```bash
kbb -M:test
```
