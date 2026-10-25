# ADR 0028: Encode terminal tail calls

## Decision

Tail-position local calls lower to GMIR `tail-call`, pass unchanged through MIR
and MC, release the current function frame, and resolve as a non-linking branch
to the callee label. x86-64 uses `jmp rel32`; AArch64 uses `b imm26` after its
frame and saved link register are restored.

The branch targets the function label, so the callee's fuel prefix and prologue
run on every transfer. Non-tail calls remain linking `call` / `bl` operations.

## Consequence

Tail recursion and mutual tail calls consume no native stack per iteration on
either ISA. The retired x86-only emitter optimization is no longer part of the
production route.
