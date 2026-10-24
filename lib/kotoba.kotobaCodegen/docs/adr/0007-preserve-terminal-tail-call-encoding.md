# ADR 0007: Preserve terminal tail-call encoding

## Decision

MC v3 admits target-selected `tail-call` instructions with an exact callee and
ABI argument keyset, but no destination register. Revalidation through MIR
keeps callee resolution, arity, frame policy, and physical-register assignment
closed before byte emission.

The native encoder is responsible for restoring the current function frame and
resolving a non-linking branch to the target function.
