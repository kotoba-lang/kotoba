# ADR 0013: Consume parallel phi-copy schedules

## Status

Accepted.

## Context

MIR now schedules complete multi-phi predecessor edges as parallel copies.
Acyclic schedules contain physical `move` instructions; cycles additionally
use the existing bounded spill store/load pair around one reusable temporary
slot. Reconstructing this decision in a target backend would split ownership
and risk target-specific control-flow behavior.

## Decision

`kotoba-native` consumes the allocated MC sequence exactly as selected by MIR
and validated by `kotoba-codegen`:

- `move` retains the existing x86-64 and AArch64 64-bit register encodings;
- cycle temporaries retain the existing frame-slot load/store encodings;
- backend layout derives its frame size only from `:mc/frame-slots`;
- no backend recognizes phi, reorders copies, or invents a scratch register.

The dependency pins advance together so that MC validates the same MIR contract
that native encodes. Structural tests cover acyclic dual-phi output for both
targets; real-process execution remains the Amu consumer gate.

## Consequences

An acyclic dual-phi join has no phi spill traffic and no frame allocation. A
cycle costs one bounded temporary slot rather than one persistent slot per phi.
Both ISAs retain one target-independent scheduling decision and the same
fail-closed MC boundary.
