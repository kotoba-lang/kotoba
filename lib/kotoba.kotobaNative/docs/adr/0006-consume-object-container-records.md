# ADR-0006: Consume object-container records from kotoba-object

- Status: accepted
- Date: 2026-08-09

## Context

`kotoba.native.elf64` combined two responsibilities: aiueos/target policy and
the byte encoding of standard ELF64 records. The latter is target-neutral and
would otherwise be copied by each backend or object format consumer.

## Decision

Pin `kotoba-object` and use `kotoba.object.elf64` for ELF headers, program and
section headers, symbols, RELA entries, little-endian integers, and bounded
padding.

Keep all target decisions here: image addresses, section placement, entry
shims, fuel budgets, capability contexts, exported symbols, and requested
relocation kinds.

## Verification

- `kotoba-object`: 4 tests, 18 assertions
- `kotoba-native`: 79 tests, 972 assertions
- compiler aiueos target suite with this checkout as `:local/root`: 44 tests,
  240 assertions

## Consequences

The object repository is a real dependency with a production consumer, while
the native backend remains the sole owner of ABI and runtime policy. Adding
Mach-O or PE records will not require moving compiler semantics into the object
container layer.
