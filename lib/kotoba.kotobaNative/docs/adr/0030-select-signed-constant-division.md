# ADR 0030: Select signed constant division

## Decision

GMIR retains the normative signed `quotient` operation. During MIR v3 target
selection, a quotient whose right SSA value is a constant becomes the closed
`quotient-constant` operation while retaining the original right vreg for
conservative liveness. MC carries the exact divisor.

For every divisor other than zero and plus/minus one, both native encoders
independently derive the Hacker's Delight signed reciprocal multiplier and
post-shift. x86-64 emits signed multiply-high through `RDX:RAX`; AArch64 emits
`SMULH`. Both apply the numerator and truncation-toward-zero corrections.
Zero and plus/minus one retain the established guarded hardware division path,
including division-by-zero and `MIN/-1` traps.

## Safety boundary

The optimization does not alter KIR or GMIR semantics and introduces no
unchecked source fact. MIR and MC admit exact keysets, the divisor must be an
i64 constant, allocator scratch registers remain outside the allocated
profile, and the verifier re-derives the selected bytes from the sealed KIR.
Boundary tests compare the reciprocal construction with normative signed
division across positive and negative divisors and both i64 extremes.

## Consequence

Hot integer code no longer pays hardware divide latency for invariant literal
divisors. Dynamic divisors and the exceptional constant cases retain their
previous code and traps. Constant-definition elimination is intentionally a
later effect-aware optimization; the original SSA source remains present in
this change.
