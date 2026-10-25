# ADR 0005: Own per-function frames across scalar calls

## Status

Accepted.

## Context

The four allocator registers on both native targets are caller-clobbered. A
direct call inserted into the v2 flat program would destroy live values and
would share one ambiguous frame prologue/epilogue across caller and callee.
Argument register assignment can also contain register cycles.

## Decision

MIR v3 mirrors the GMIR v3 module and allocates each function independently.
A physical function records its own bounded frame slot count and one of two
closed policies: `:allocator` for call-free functions or `:all-vregs` for a
function containing a call.

The first scalar call allocator deliberately places every vreg in a stable
function-local slot. Immediately before a call it loads all arguments from
those slots into the target ABI argument registers. Because every source is in
memory, this is a parallel assignment without register-cycle destruction.
Every allocator register may then be clobbered. The single-word return register
is stored into the destination's slot before later instructions execute.

This is a correctness-first allocation policy for call-containing functions,
not the final performance policy. It is bounded by the existing 4,095-slot MIR
frame limit and remains deterministic on x86-64 and AArch64.

## Consequences

Calls now have explicit function-frame ownership and preserve every live value
without target-specific inference. A later liveness pass may reduce stores to
only values live across each call while retaining the same MIR v3 contract.
