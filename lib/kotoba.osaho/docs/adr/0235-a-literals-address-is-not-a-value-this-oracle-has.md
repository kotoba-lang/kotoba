# ADR-0235: A literal's address is not a value this oracle has, but its length is

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0011 added read-only literals and two wider firmware calls. The
oracle has to say what it does with both.

## Decision

**The two wider calls refuse exactly as `kernel-uefi-call2` does.**
`kernel-uefi-call4` (six operands) and `kernel-uefi-call6` (eight) join
`kernel-uefi-operations`. Arity is the only difference and it is the backend's
business.

**The three literal ADDRESS heads refuse under their own keyword.**
`ucs2`, `guid` and `bytes-literal` trap `:rodata-address-unavailable`. There is
no image here, no load base and no pool; any number returned would be a number,
and the caller hands it to firmware as a `CHAR16 *`.

The keyword is theirs rather than `:kernel-privileged-unavailable` because it
is a different refusal. A privileged operation names an instruction this
machine is not running. A literal address names a place in an image that does
not exist. A caller deciding whether its program is wrong or the oracle simply
cannot answer needs to be able to tell those apart.

They also mark a module kernel-native, for the reason the port operations do:
without that the constant oracle folds one, the trap fires, and a program that
compiles perfectly well fails to compile.

**`bytes-literal-length` is answered, and that asymmetry is the decision.**
It is the paired half of `bytes-literal` -- this language has no multi-value
return and no `pair` on a firmware target, so the address and the length are
two heads over the same literal text. Unlike the address, the length is a
property of the TEXT rather than of the machine. Refusing something answerable
would make the oracle less useful for nothing, and would make a module that
only asks how long a literal is kernel-native for nothing.

`hex-pair-count` is deliberately not a hex decoder. The byte VALUES belong to
the backend that places them, and a second decoder here would be a second thing
that has to agree with `gmir/rodata-bytes` about what a literal is. What this
needs is the count, and whether the text is hex at all.

## Consequences

- A malformed hex literal traps `:rodata-literal-malformed` here and
  `:invalid-rodata-content` at kotoba-gmir. Two refusals for one defect, at two
  layers, is the same shape as the arity re-derivations.
- The `ucs2` and `guid` contents are NOT validated here. This layer never
  decodes them, so validating would mean transcribing the GUID grammar into a
  second place; kotoba-sema refuses the malformed shape at the source and
  kotoba-gmir refuses it at the IR.
- Found by running both runtimes: the length arm returned a plain JS number on
  ClojureScript and reached the result-type check as `:value-type-mismatch`,
  where the JVM branch had been green. An i64 is a `long` here and a BigInt
  there.
