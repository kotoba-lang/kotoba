# ADR-0018: A function's address is a value with a name, and the scratch region needs nothing here

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0013 added two operations. One of them needs work at this
layer and the other needs none, and saying which is which is most of this
decision.

## Decision

**`:scratch-region` needs nothing here.** It is a zero-arity privileged
action, so it arrives through the channel `:cli` and `:boot-info` already use,
`privileged-argument-registers` slices zero registers out of a nine-wide
vector, and `mir/saved-registers` finds nothing to save. The suite asserts the
absence of a frame save rather than only asserting the arity, for the reason
ADR-0016 gave: a vector that allocates correctly can still add a save/restore
pair to every kernel that names the action.

**`:mir/function-address` selects and expands like `:mir/data-address`** --
one destination, no sources -- and joins the value-producing set so the
call-frame policy backs it. Two things it does not share with that operation:

- **The name travels through untouched, and its SHAPE is re-derived here**
  through `gmir/function-id?`. Selection copies `:gmir/function` across
  without looking at it, so a hand-built MIR program that never passed
  `gmir/validate!` would otherwise reach the backend's label table holding
  something that is not a name. This is the same re-derivation the
  kernel-memory arities and `:mir/rodata-address`'s content check exist for.
  WHICH names resolve is not re-derived: that is a property of the module's
  function list, and this layer is handed one function at a time.
- **It is x86-only, under its OWN keyword**,
  `:function-address-target-mismatch`. `lea dst,[rip+disp32]` has no AArch64
  translation the layout pass models -- `adrp`+`add` splits the address at a
  4 KiB page boundary -- which is exactly why `:mir/rodata-address` is x86-only
  too. A second keyword rather than reusing `:rodata-address-target-mismatch`
  because the two refusals name different operations, and a caller reading the
  report should not have to work out which of the two it wrote. This is an
  admission of a gap, not a decision about AArch64: when the layout pass models
  the page split, both refusals go together.

## Consequences

- `isa-parity` now pins FOUR refusal reasons rather than three.
- The register tiers are untouched. Eight operands is still the widest
  privileged arity, and the widest thing this change adds is zero.
