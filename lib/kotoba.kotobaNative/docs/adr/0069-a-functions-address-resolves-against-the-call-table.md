# ADR-0069: A function's address resolves against the same table a call does

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0013 added `:gmir/function-address`. `kernel-jump-to` has been
encoded and gated here since the UEFI boundary landed, and nothing in the
language produced its first argument.

## Decision

**Seven bytes: `lea dst,[rip+disp32]`, and they are the literal pool's bytes.**
`x86-lea-rip-code` is split out of `x86-lea-rip` so the pool's resolver and the
layout table's branch encoder share one encoding of one instruction rather than
growing two. The layout table's operands are register CODES rather than
keywords (kotoba-codegen ADR-0011), which is the whole reason for the split.

**It is resolved in `instruction-tokens`, beside the call, and not in
`encode-selected`.** That function is handed one instruction and no module,
and a function's label is a property of the module. `instruction-tokens`
already receives `callee-labels` because a call needs it, and the point of this
operation is that the two name the same place -- so it uses the same table.
The suite asserts that with a program which both calls `target` and takes its
address: the `call`'s resolved displacement and the `lea`'s must be the same
offset. Pointed at the wrong label, that assertion and the export-table one
both go red.

**`:unknown-function-address-target`, not the call's
`:unknown-call-target`.** A program that takes the address of a name it did not
define contains no call to that name, so the call's message would describe
something the source does not have. kotoba-gmir refuses that program two layers
earlier; this is the floor under it, and the only route that reaches it without
a hand-built module is `encode-mc` -- the FLAT v2 route -- which passes an
EMPTY label table. The suite reaches it that way rather than by constructing an
MC module by hand.

**The name travels on the instruction, not as an operand.** A privileged
action's arguments are virtual registers by the time this file sees them, which
is why `:isr-entry-address` takes a vector NUMBER instead of a name. This
operation cannot: an entry region is indexed by multiplication and a function
is not.

## Evidence

The address is asserted against the module's own EXPORT TABLE offset rather
than a golden number, so the test stays true when an entry prologue changes
width. Three break/restore demonstrations: the `mov` opcode in place of `lea`
reddens the region tests; pointing the `lea` at the first label rather than the
named one reddens the export-table and call-agreement tests; adding 4 to the
displacement -- the classic "measured from the field, not the end" error --
reddens the same two.

## Consequences

- AArch64 refuses at kotoba-mir with `:function-address-target-mismatch`, for
  the reason the literal pool does: `adrp`+`add` splits the address at a 4 KiB
  page the layout pass does not model.
- The non-word-typed fallback emitter does not implement it, exactly as it does
  not implement the four ADR-0291 operations or the literal heads.
