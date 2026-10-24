# provider-postgres

PostgreSQL pool provider — a narrow, capability-gated host adapter.

**Tier**: `T3`  **Role**: `provider`

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside.

## Owns

- `provider.postgres.pool`

## Does not own

- be linked into a runtime core
- grant itself authority

## Depends on

- nothing (contract/leaf tier)

## Test

```bash
kbb -M:test
```
