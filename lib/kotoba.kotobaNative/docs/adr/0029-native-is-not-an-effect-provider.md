# ADR-0029 — Native is not an effect provider

- **Status:** Accepted
- **Date:** 2026-08-11
- **Owner:** `kotoba-lang/kotoba-native`
- **Related:** Amu ADR-0240; aiueos ADR-0013; root ADR-2608110400

## Context

“Native” was being used for three different claims: machine-code emission, a
qualified compiler backend, and an OS effect implementation. A working opcode
or an aiueos-named target policy in this repository was therefore easy to read
as evidence that a provider existed in production.

## Decision

`kotoba-native` ends at checked machine semantics: instruction selection,
encoding, layout, freestanding entry ABI, and target admission. Amu consumes
that boundary to emit and qualify artifacts. Aiueos consumes exact-pinned Amu
artifacts and owns firmware handoff, memory authority, paging, isolation,
syscalls, capabilities, effect providers, and machine evidence.

```text
Kotoba semantics
  -> kotoba-native ABI and instruction meaning
  -> Amu generation and qualification
  -> aiueos production provider and machine gate
```

The arrows do not reverse. In particular, aiueos policy cannot silently become
backend semantics, and a backend test cannot stand in for a provider QEMU gate.

## Evidence rule

An effect is production-native only when one exact-pinned chain produces the
C-free boot artifact, its receipt names no C source, foreign object, import, or
dynamic dependency, and aiueos supplies positive and fail-closed machine
execution. Hosted VM/HVT paths and the reference C kernel do not satisfy that
rule.

## Consequences

- `aiueos` in a backend namespace denotes target admission, not OS ownership.
- This repository reports emission/ABI maturity only.
- Provider maturity is reported by aiueos ADR-0013; compiler qualification by
  Amu ADR-0240.
