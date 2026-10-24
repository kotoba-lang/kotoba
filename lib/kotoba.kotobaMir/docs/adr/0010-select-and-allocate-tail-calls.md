# ADR 0010: Select and allocate tail calls

## Decision

MIR v3 preserves GMIR `tail-call` as a terminal operation. Allocation loads all
arguments in parallel into the target call ABI registers. The operation has no
return register and no live-across-call values because execution cannot resume
in the current function.

Tail-call functions use a frame-owning policy so the byte encoder can release
the current spill frame before branching to the callee. Both x86-64 and AArch64
use the same closed MIR contract.
