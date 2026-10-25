# ADR-0007: Consume shared final layout from kotoba-codegen

- Status: accepted
- Date: 2026-08-09

## Context

ADR-0005 established a closed, deterministic layout contract and migrated both
production emitters to it. The contract now has independent release value: it
is shared by x86-64, AArch64, and the explicit machine-IR path, and depends on
neither backend policy nor instruction encoders.

## Decision

Move the layout authority to `kotoba.codegen.layout` and pin the merged
`kotoba-codegen` contract. Remove the former `kotoba.native.layout` source
rather than retaining a second implementation or compatibility-only facade.

Keep instruction selection, branch opcode encoding, ABI/runtime policy, and
the bounded KIR-to-GMIR producer in this repository.

## Consequences

All three production consumers resolve labels and displacements through one
cross-backend authority. Native integration tests retain their real x86-64 and
AArch64 emission assertions, while `kotoba-codegen` tests the closed layout
contract independently.
