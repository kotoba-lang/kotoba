# ADR 0001: Extract the generic machine IR contract

**Status:** accepted

## Decision

`kotoba-gmir` owns the closed target-independent GMIR v1 data model and its
validator. It has no dependency on KIR or a target backend. KIR-to-GMIR
lowering remains with the producer until that transform has another consumer.

The v1 operation set is deliberately small: argument, constant, add, label,
branch-zero, jump, and return. Values use qualified virtual-register keywords;
control flow uses qualified label keywords. Unknown operations, extra keys,
invalid signed-i64 constants, duplicate labels, and unresolved targets fail
closed.

Target selection, register allocation, MC layout, encoding, and object writing
are outside this repository. This prevents the generic contract from importing
backend policy and makes the dependency direction externally checkable.
