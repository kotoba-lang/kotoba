# ADR 0015: Scalar replacement for non-escaping variants

## Status

Accepted.

## Context

The legacy native emitters materialize a directly matched sealed variant in a
stack region containing a discriminant and the widest payload. That contract
is safe and supports flattened record payloads, but it keeps local scalar
variants outside the extracted KIR-to-GMIR pipeline introduced for arithmetic,
control flow, and scalar records.

A sealed variant whose every payload is one scalar word has no observable
runtime identity when it remains inside one expression. Its discriminant and
payload can travel independently in SSA just as a fixed record's fields do.

## Decision

The bounded KIR-to-GMIR producer scalar-replaces non-empty
`[:variant name cases]` values when case names are unique and every payload is
`:i64` or `:bool`.

- `variant-new` resolves the declared case to its zero-based ordinal, evaluates
  its payload exactly once, and records an internal `{tag, payload}` SSA bundle;
- lexical `let` may bind the bundle without allocating a stack region;
- variant-valued `if` requires the identical canonical schema and emits one phi
  for the tag and one for the payload;
- `variant-match` requires exactly one branch per case in declaration order,
  compares the tag through ordinary GMIR control flow, and exposes the payload
  register only through that branch's binder;
- branch bodies may use the already admitted scalar, record, and variant forms,
  but the enclosing function must still return one scalar word.

The bundle is producer state, not a new serialized GMIR operation. Consequently
GMIR, MIR, target selection, allocation, and MC validation retain their existing
closed schemas. The extracted path never accepts a variant parameter or result,
so an invalid external discriminant cannot enter this representation.

Unknown cases, reordered or incomplete branches, schema mismatches, nested or
non-scalar payloads, and escaping variant values fail the pilot predicate and
fail closed before target selection. ADR 0026 removed the former test-only
legacy routing seam.

## Consequences

Eligible local variants reach x86-64 and AArch64 without a variant stack frame.
The same target-neutral CFG is selected and allocated for both ISAs. A
variant-valued branch exercises the real multi-phi path, while payload
evaluation and unselected-branch control flow preserve KIR trap behavior.

This decision does not define an aggregate function-boundary ABI, scalarize
record payloads inside variants, accept variant parameters/results, or define
an external invalid-tag ABI. Those are separate migration stages and must not
be inferred from this local SROA contract.
