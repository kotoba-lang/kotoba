# ADR 0031: Admit recursive record handles

## Decision

Aggregate ABI v6 admits inline nested records on x86-64 and AArch64. Every
record remains a declaration-order pair chain and every nested field occupies
one native word containing the inner chain handle. Lowering is post-order, so
an inner constructor is boxed before the enclosing constructor consumes it.

Inline schema nesting is limited to 32 record levels. Runtime allocation keeps
the existing context-owned 4,096-cell arena limit. Both limits fail closed;
this change adds no instruction, callback, loader field, ambient allocation, or
legacy emitter route.

## Evidence

Production emitter tests compare nested construction, sibling projection,
chained projection, and a record-valued projection byte-for-byte with the
equivalent hand-written `pair`/`pair-first`/`pair-second` programs on both ISAs.
ABI tests admit depth 32 and reject depth 33.

## Held boundary

Variants containing aggregate payloads, indirect calls, varargs, and external
linkage remain fail-closed non-native boundaries.
