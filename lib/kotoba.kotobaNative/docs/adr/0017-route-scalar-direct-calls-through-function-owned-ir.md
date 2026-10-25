# ADR 0017: Route scalar direct calls through function-owned IR

## Status

Accepted.

## Context

ADR 0016 held extracted calls because the machine IR represented one anonymous
instruction vector, every allocator register was caller-clobbered, and one
frame prologue/epilogue could not belong independently to caller and callee.

## Decision

Consume GMIR v3, MIR v3, and MC v3 and route checked KIR modules with exactly
one exported scalar entry through the extracted pipeline when at least one
module-local scalar direct call is present.

Each function lowers and allocates independently. A call-containing function
uses MIR's `:all-vregs` frame policy: every definition is immediately backed by
a bounded stack slot, arguments are loaded from those stable slots into the
five target ABI registers, all allocator registers may be clobbered, and the
single-word return is stored before subsequent instructions.

Final module layout owns function labels and function-local label namespaces.
x86-64 reserves CALL rel32, adds the eight-byte alignment pad required at an
internal call site, and restores the caller's frame on every return. AArch64
reserves BL imm26 and call-containing functions save/restore FP and LR around
their independent spill frame. Fuel instrumentation is part of the same final
layout, so it cannot stale call or branch displacements.

Aggregate ABI version 2 changes only scalar call admission to
`:scalar-admitted`. Record and variant boundaries stay `:held`; standalone
expression lowering still rejects call-shaped KIR because it has no module
signature or frame owner.

## Consequences

The production backends now execute scalar direct calls through canonical
GMIR/MIR/MC instead of the legacy call token path. Correctness is structural
and deterministic on both targets, while the first allocator intentionally
trades runtime traffic for a simple proof. The next optimization is
call-site liveness so only values live across a call are spilled.

This does not admit aggregate calls, indirect calls, external linkage, or
tail-call lowering, and does not establish Rust-equivalent performance.
