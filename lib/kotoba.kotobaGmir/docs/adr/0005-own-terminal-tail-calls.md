# ADR 0005: Own terminal tail calls

## Decision

GMIR v3 admits `:gmir/tail-call` with a canonical callee and at most five
scalar virtual-register arguments. It has no destination because control never
returns to the current function. The module validator resolves its callee and
checks its arity exactly like a direct call.

Versions 1 and 2 reject the operation. MIR owns ABI argument assignment and
frame release; codegen owns the final non-linking branch encoding.

## Consequence

Source tail recursion and mutual tail calls no longer need a backend-private
emitter fast path or a native call frame per iteration.
