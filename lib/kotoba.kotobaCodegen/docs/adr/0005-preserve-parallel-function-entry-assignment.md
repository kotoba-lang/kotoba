# ADR 0005: Preserve parallel function-entry assignment

## Status

Accepted.

## Decision

MC v3 preserves MIR's exact ABI input markers and the target-selected `move`
sequence produced by MIR's parallel-copy scheduler. It does not reinterpret
argument markers as allocator destinations or reorder the following moves.

The MC-to-MIR validation projection therefore independently checks that each
physical function has one ABI-register marker per declared parameter. A
non-ABI marker fails closed before reaching an encoder.

## Consequences

On x86-64, a four-live-parameter callee can preserve `rcx` into `r8` before
assigning the second input into `rcx`; on AArch64 the matching registers require
no moves. Under MIR ADR 0008, an excess live entry input remains represented by
its ABI marker, a bounded direct frame store, and a lazy load while retaining
the allocator frame policy. Codegen does not claim ownership of allocation or
ABI design.
