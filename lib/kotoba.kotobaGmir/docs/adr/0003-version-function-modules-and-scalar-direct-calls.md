# ADR 0003: Version function modules and scalar direct calls

## Status

Accepted.

## Context

GMIR v1/v2 describes one anonymous instruction vector. A call instruction in
that shape cannot prove that its target exists, that argument count matches, or
that labels and virtual registers belong to separate function scopes.

## Decision

GMIR v3 is a non-empty module with an explicit entry function. Every function
has a unique symbolic name, an arity from zero through five, and its own
instruction vector. `:gmir/call` names a module-local callee, a fresh scalar
destination, and zero through five scalar virtual-register arguments.

Validation is two-pass: module signatures are collected first, then every
function body is validated with local labels and vregs. Calls to missing
functions and arity mismatches fail closed. Argument loads must be unique and
within their owning function's arity. v1 and v2 retain their exact shapes and
cannot acquire calls.

This contract describes scalar values only. It does not admit aggregate
arguments, external linkage, indirect calls, varargs, or tail-call lowering.

## Consequences

MIR can allocate one frame per function and can reason about caller clobbers
without reconstructing a call graph from backend tokens. Later aggregate ABI
versions can extend the value types without weakening the scalar v3 boundary.
