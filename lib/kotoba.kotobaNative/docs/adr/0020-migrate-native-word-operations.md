# ADR 0020: migrate native word operations through machine IR

## Context

The production machine-IR route already owned i64 arithmetic, bitwise binary
operations, comparisons, control flow, phi values, and scalar direct calls.
`bit-not`, the signed and unsigned shift families, and the i32 wrapping family
still selected the established recursive target emitters. That left portable
word semantics on a second production lowering path.

x86-64 variable shifts require the count in `CL`, while AArch64 accepts any
general register. Treating that x86 constraint as a KIR concern would leak a
target register into GMIR.

## Decision

GMIR owns three target-independent binary operations: left shift, signed right
shift, and unsigned right shift. MIR selects and allocates them like the other
binary word operations, and MC owns their target-specific encoding names.

The native KIR producer composes the remaining operations:

- `bit-not` is xor with `-1`;
- `bool-not` is equality with zero;
- signed i32 normalization is left shift by 32 followed by signed right shift
  by 32;
- unsigned i32 normalization is bit-and with `0xffffffff`;
- i32 arithmetic and shifts normalize around the corresponding word operation.

The x86-64 MC encoder uses private `r11`, saves and restores `rcx`, loads the
count into `CL`, performs the shift, and moves the result to the allocated
destination. AArch64 emits LSLV, ASRV, or LSRV directly. Neither encoder
clobbers a live MIR value that is not the destination.

## Consequences

All currently admitted i64/i32 word operations now satisfy the production
pilot and no longer use the established recursive emitter. The shared contract
remains independent of frontend-only i32 names. Byte-contract tests cover both
ISAs, and the compiler's real loader suite executes the word-operation rows on
both AArch64 and x86-64.

Heap handles, strings, capabilities, floating point, and escaping aggregates
remain separate migration stages because they require explicit value, effect,
and runtime-call contracts rather than more word arithmetic.
