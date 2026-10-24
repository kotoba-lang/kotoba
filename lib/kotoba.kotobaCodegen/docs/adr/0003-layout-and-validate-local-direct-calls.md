# ADR 0003: Layout and validate local direct calls

## Status

Accepted.

## Context

MIR v3 introduces physical function modules, but call displacement cannot be
baked until every function's final encoded size is known. MC v2 also has no
place to retain per-function frame ownership.

## Decision

MC v3 mirrors the physical MIR v3 module: entry, functions, arity, bounded
frame slots, frame policy, and selected instructions. `call` is an exact
target-selected instruction whose operands are revalidated by MIR.

The shared layout contract adds `:x86-64/call-rel32` and
`:aarch64/bl-imm26`. They reserve five and four bytes respectively and use the
same final two-pass label resolution and architectural range/alignment checks
as branches. Backends still own opcode encoding.

## Consequences

Native code can lay out all functions first and resolve local calls only after
their offsets are final. MC does not guess external linkage or object
relocations; this version admits module-local direct calls only.
