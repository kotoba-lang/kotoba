# ADR-0010: A rodata address carries its encoding

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0011 added `:mir/rodata-address`, whose shape is
`:mir/dst`, `:mir/content` and `:mir/rodata-encoding`. Without a row in
`selected-keysets` the MC contract refuses it as
`:non-canonical-selected-instruction`, and no backend can emit it.

## Decision

`:rodata-address` joins `selected-keysets` with all three keys.

The encoding key is what distinguishes this from `:data-address`, and it is not
decoration. `:data-address` is always UTF-8 and the backend resolves it against
a runtime base; this one is UCS-2, a GUID or raw bytes, and the backend resolves
it against the program counter. **The same string is a different sixteen bytes
as a GUID than it is as hex**, so an instruction that lost the key would place
the wrong bytes and still validate.

## Consequences

- The keyset is exact, so a `:data-address` that grew an encoding is refused
  too. Both directions are asserted.
- This namespace owns the SHAPE and not the placement: where the pool goes,
  how it is aligned and which instruction reaches it are the backend's, and
  kotoba-native ADR-0046 carries them.
