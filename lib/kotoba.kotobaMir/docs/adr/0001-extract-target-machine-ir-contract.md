# ADR 0001: Extract target Machine IR and allocation

**Status:** accepted

## Decision

`kotoba-mir` owns MIR v1, target selection from GMIR v1, and the first closed
deterministic register allocator. MIR records whether registers are virtual or
physical; consumers cannot infer allocation state from keyword spelling.

The v1 target set is x86-64 and AArch64. The allocator intentionally exposes a
small ordered scratch profile and rejects spilling rather than inventing an
implicit stack ABI. Unknown targets, malformed instructions, use before
definition, multiple definition, foreign physical registers, and register
exhaustion fail closed.

Machine-byte encoders and MC/layout tokens remain in `kotoba-native`. They can
be extracted later as `kotoba-codegen` and `kotoba-object` after their ABI and
object contracts have independent consumers.
