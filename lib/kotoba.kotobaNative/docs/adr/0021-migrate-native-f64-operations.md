# ADR 0021: migrate native f64 operations through machine IR

## Context

The legacy recursive emitters already implemented the complete admitted f64
family on x86-64 and AArch64, but the production machine-IR route stopped at
integer and word operations. This kept floating-point expressions on a second
lowering and allocation path even though their values have the same one-word
calling convention.

## Decision

GMIR and MIR represent an f64 value by its 64-bit IEEE-754 bit pattern in an
ordinary virtual or physical general register. They admit target-independent
arithmetic, min/max, ordered comparisons, unordered comparison, and sqrt.
MC selects the corresponding target encoding while retaining the allocated GPR
operands.

The native encoders use private FP scratch registers only while encoding a
selected operation:

- x86-64 moves operands to `xmm0`/`xmm1`, executes scalar SSE2, and moves the
  result back to the allocated GPR;
- AArch64 moves operands to `d0`/`d1`, executes scalar FP, and moves the result
  back to the allocated GPR;
- comparison results are materialized as canonical integer booleans;
- equality explicitly excludes unordered operands, preserving the established
  NaN semantics.

`f64-from-bits` and `f64-to-bits` are identities. `f64-abs` and `f64-neg` lower
to portable sign-bit masks, while `f64-sqrt` remains a unary FP operation.

## Consequences

Every admitted scalar f64 operation now reaches GMIR, MIR allocation, the MC
contract, and the target encoder. FP scratch state never becomes part of the
calling convention or allocator profile, and no non-destination allocated GPR
is clobbered. Byte-contract tests cover both targets; the compiler's real
loader qualification remains the execution gate before the dependency pin is
promoted.
