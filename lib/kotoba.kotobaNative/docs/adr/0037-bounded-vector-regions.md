# ADR 0037: Scalar regions for bounded non-escaping vector literals

- Status: accepted
- Date: 2026-08-30

## Decision

Before x86-64 or AArch64 instruction selection, run one shared conservative
lexical escape analysis over each KIR function body. A `vector-new` or
`vector-f64-new` literal containing at most 32 items is replaced by scalar
locals only when all uses are count or checked reads. Item expressions retain
their original order and are evaluated exactly once. Dynamic indices are also
evaluated once and retain the `at` trap / `get` fallback distinction.

Any function-boundary escape, return, storage, identity observation,
unsupported operation, or uncertain shadowing leaves the literal materialized
through the existing checked host-vector ABI. The optimization is therefore a
proof-directed fast path, never an alternate vector meaning.

## Consequences

- Proven local literals allocate neither a vector-table entry nor element
  arena storage.
- Both native ISAs consume the same rewrite and cannot drift semantically.
- Escaping and large vectors remain bounded host values.
- This does not claim general region inference, stack allocation of arbitrary
  vectors, or benchmark superiority. Those require separate evidence.
