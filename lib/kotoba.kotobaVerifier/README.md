# kotoba-verifier

Independent artifact verifier — re-derives emission from KIR and rejects drift.

**Tier**: `T2`  **Role**: `verifier`

Split out of the overloaded core repos by ADR-2607266000 so that each
responsibility has exactly one owner and the dependency direction is
checkable from outside.

## Owns

- `kotoba.verifier (target contract + re-emission equality check)`

For native record scalar replacement, the verifier independently admits only
one `if` with two direct constructors of the same non-empty fixed
`:i64`/`:bool` record, either projected directly or named by one `let`. It
continues to reject schema drift, symbol forwarding, nested/non-scalar
aggregates, and escaping aggregate ABI claims.

For native variant scalar replacement, the verifier independently admits a
sealed variant only when every payload is `:i64` or `:bool` and the value is a
direct constructor, one local binding, or one same-schema variant-valued `if`.
Matches must cover every case in declaration order. Legacy directly nested
matches retain their established wider payload support; local symbol
forwarding remains rejected. Aggregate ABI v7 separately admits variant
parameters/results as one pair handle; this verifier independently re-derives
the qualified identity, 1--32 unique ordered cases, and `:i64`/`:bool` or
admitted-record payload restriction, and tracks parameter/call-result schemas
for exhaustive dispatch.

The verifier pins the native producer containing aggregate-boundary contract
v7. It checks that record and aggregate-payload variant boundaries remain
one-word, context-owned pair handles, callable dispatch stays ordinal-sealed,
bounded `apply` remains capped at four arguments, linkage rejects ambient and
unresolved symbols, and calls are admitted only with the complete per-function
frame/clobber guarantee set. It also re-emits a two-function call module with
the pinned production emitter and checks that its representative caller uses
the liveness-minimal `:call-live` policy with one slot, save, and reload.
It also gates the pinned producer's function-entry ABI: four live scalar
parameters must retain exact ABI markers and reach both native ISAs with zero
frame slots and no spill operations. Five live scalar parameters must retain
the five exact markers while using one bounded entry slot, one direct store,
and one lazy load in each function rather than the all-vreg policy.
Reading this producer contract does not widen
the verifier's independently derived record or variant predicates.

## Does not own

- produce artifacts
- be a dependency of the producer it verifies

## Depends on

- `kotoba-lang/osaho` (formerly `kotoba-kir`)
- `kotoba-lang/artifact`
- `kotoba-lang/kotoba-wasm`
- `kotoba-lang/kotoba-native`

## Test

```bash
kbb -M:test
kbb --backend sci --classpath "src:test:$(kbb -Spath -M:test)" run-tests.cljk
```

Both, not either. This verifier runs on two compiler hosts and they represent
a `.kotoba` literal differently -- on nbb an integer literal is a JavaScript
`bigint`, which `integer?` does not recognize. A rule checked only on the JVM
is a rule the JDK-free route has never had checked (ADR-0022).
