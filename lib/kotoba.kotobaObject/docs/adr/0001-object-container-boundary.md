# ADR-0001: Keep object-container encoding target-neutral

- Status: accepted
- Date: 2026-08-09

## Context

The initial ELF64 writer lived in `kotoba-native` beside instruction selection,
ABI entry shims, aiueos memory maps, fuel policy, and capability setup. Its
low-level ELF records are reusable, while those policies are not.

## Decision

`kotoba-object` owns validated object-container record encoding. The contracts
cover ELF64 little-endian headers, segments, sections, symbols, and RELA
entries; PE32+ records and images; and Mach-O 64-bit relocatable objects with
sections, symbols, and platform build-version metadata.

Backends continue to own section layout, addresses, machine bytes, relocation
selection, entry shims, and runtime policy. This repository never infers those
decisions from a compiler artifact.

## Consequences

- ELF binary structure has one independently tested implementation.
- `kotoba-native` remains responsible for aiueos and target ABI semantics.
- Mach-O and PE are sibling contracts that do not import compiler policy into
  this repository.
- Mach-O relocation records remain excluded until their target-specific request
  semantics have a typed boundary.
