# ADR-0030: The allocation is the producer of the address

- Status: accepted
- Date: 2026-09-03

## Context

ADR-0013 gave a UEFI image an address it may write -- 16 KiB the packager
reserves inside the image's own `.data`. That is enough for an OUT-POINTER, so
`AllocatePages` became callable and its answer became readable. It is not
enough to USE the answer.

The page `AllocatePages` returns is at an address the firmware chose. It
reaches the program through a load out of the out-word, and kotoba-sema's
region-provenance rule refuses a base that came from a load -- in the caller as
well as in the callee, because the taint propagates by fixpoint. So a Kotoba
UEFI application could allocate a page and could not write it, which is
everything a bootloader does after it decides where the kernel goes.

## Decision

**`:uefi-alloc-region`, six operands: `(base, slot, allocate-type,
memory-type, page-count, address-hint)`. It answers with the base of the pages
the firmware just allocated, or with ZERO.**

The alternative that was NOT taken is to admit a loaded word as a base --
either directly, or through an `adopt(address, length)` head that says "trust
me". That deletes the provenance rule rather than extending it. The rule is
what makes every bounded access mean something: a window is meaningful only if
its base is an address some layer of this toolchain can account for.

So the extension is on the other side. **The instruction that obtains the
address is the instruction that produces it**, and the length it is paired
with is the length that same instruction asked the firmware for. There is no
step between the allocation and the region in which a different number could
be substituted, because there is no intermediate value the program can name.

**The out-word lives in this action's own outgoing frame.** The program never
supplies it and never sees it. That is the load-bearing half of the decision:
if the caller passed a pointer, the caller could pass a pointer to a word it
had written itself, and the "address the firmware returned" would be an
address the program chose. Owning the out-word is what makes the provenance
claim true rather than merely asserted.

**Zero on failure, and the EFI_STATUS is not reported.** Kotoba has no
multi-value return and no pair on a firmware target, so an action answering
with an address cannot also answer with a status. Zero is the right second
answer because a null base is the one thing every bounded memory operation
already refuses (kotoba-mir's emitted order puts the null-base clause second,
right after the window ceiling) -- a caller that forgets to test the result
traps at its first access rather than writing wherever the out-word happened
to point. A caller that wants to branch can compare against zero.

The price is real and is recorded here rather than in a footnote: a program
cannot tell `EFI_OUT_OF_RESOURCES` from `EFI_NOT_FOUND` from
`EFI_INVALID_PARAMETER`. A loader that wants the distinction must call
`AllocatePages` through `:uefi-call4` for the status and accept that the page
it gets that way is not a region. Both spellings remain available and they
answer different questions.

**Six operands, not five.** `address-hint` is the word the out-pointer is
pre-loaded with, and it is what makes `AllocateMaxAddress` and
`AllocateAddress` expressible -- for those two the parameter is IN OUT, and a
UEFI loader placing a kernel needs both. `AllocateAnyPages` ignores it. All
three allocate exactly `page-count` 4 KiB pages on success, which is why the
length of the answer is known at the call site under every one of them, and
why the allocate type does not have to be a literal.

**The page count is not constrained here.** By the time this table sees the
action every operand is an ordinary value; the requirement that the page count
be a compile-time literal, and the window ceiling of `page-count * 4096` that
it implies, are kotoba-sema's, because that is the layer that still has the
source form. Splitting it the other way would put a rule here that this layer
cannot state.

## Consequences

- Six is not the widest entry in `x86-privileged-action-arities` -- ADR-0011's
  `:uefi-call6` is eight -- so `kotoba.mir/privileged-argument-registers` is
  unchanged and neither kotoba-mir nor kotoba-codegen needs a row for this.
- The action both calls the firmware and returns an address, which no other
  entry in this table does. `:uefi-call2/4/6` return the callee's RAX;
  `:scratch-region`, `:boot-info` and the handler-address family return an
  address without calling anything.
- Nothing here frees pages. `FreePages` takes an address and a count and
  answers a status, which is exactly `:uefi-call2`'s shape -- it needs no
  action of its own, and giving it one would suggest this table tracks
  ownership. It does not.
