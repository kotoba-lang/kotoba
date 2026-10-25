# ADR 0024: Admit the scalar record pair-chain boundary

Status: superseded by ADR 0031

## Decision

Aggregate ABI v4 admits named, non-empty records whose unique fields are
`:i64` or `:bool`. At a function boundary the value is one word: a
declaration-order `pair(field, rest)` chain terminated by `0`. The context pair
arena owns the cells and retains its 4,096-cell execution limit.

The KIR-to-GMIR producer normalizes constructors and projections only when a
module signature exposes such a record. Calls, parameters, and results then use
the existing one-word register ABI and closed runtime-call operation. Local
records in modules without a record boundary remain allocation-free SROA.

## Consequences

- Record boundary construction/projection no longer requires either legacy ISA
  emitter.
- Field order is the declared schema order and is validated independently.
- Nested or non-scalar record fields remain outside this bounded boundary.
- The representation is portable across x86-64 and AArch64 and introduces no
  new host callback or context offset.
