# ADR-0080: The out-pointer belongs to the instruction, not to the program

- Status: accepted
- Date: 2026-09-03

## Context

kotoba-gmir ADR-0030 adds `:uefi-alloc-region`, which calls
`BS->AllocatePages` and answers with the base of the pages rather than with a
status. kotoba-sema ADR-0030 makes those pages a region-provenance root. This
is the encoder those two decisions rest on.

## Decision

**It is `x86-uefi-call-wide`'s frame with one slot repurposed as the
out-word.**

```
+0x00..0x18  shadow space / staging for arguments 1-4
+0x20        THE OUT WORD, and the address passed as argument 4
+0x28        original RSP
+0x30..0x50  RAX, RCX, RDX, R8, R9
```

0x60 is a multiple of 16, so RSP is still 16-aligned at the `call` after `and
rsp,-16`. `+0x20` is the fifth-argument slot of a Microsoft x64 frame: a
four-parameter callee owns `[rsp..rsp+0x18]` and its own frame lies BELOW RSP,
so the word survives the call it is an argument to.

**The out-word is the whole point, and it is here rather than in the source
for one reason.** If the program supplied the pointer, the program could
supply a pointer to a word it had written itself -- and "the address the
firmware returned" would be an address the program chose. Every claim
kotoba-sema makes about the region would then be a claim the author made about
their own arithmetic. Owning the word is what makes the provenance real rather
than asserted, and it costs one repurposed stack slot.

**The answer is zeroed on failure, branchlessly:**

```
mov r10,[rsp+0x20]     the word the firmware wrote
xor r11,r11            SETS FLAGS, so it comes BEFORE the test
test rax,rax           EFI_STATUS, still in RAX from the call
cmovne r10,r11         status != 0 -> 0
```

The ordering is not cosmetic. `xor` writes ZF, so placing it after the `test`
would make the `cmov` read the xor's own flags and take the branch every time.
And `cmove` is one bit from `cmovne` and inverts the whole operation --
answering with the out-word on FAILURE and with zero on SUCCESS -- with
nothing faulting to say so. Both are pinned by the suite as byte goldens, the
second as an explicit `not`.

Zero rather than a status because Kotoba has no multi-value return on a
firmware target, and because a null base is the one answer every bounded
memory operation already refuses.

**Every byte was read back from `llvm-mc -triple x86_64 -show-encoding`**,
which is this repository's rule for a new encoding and is what the two
`[rsp+0x20]` ModRM/SIB forms most need: a wrong one still assembles, still
runs, and puts the out-word somewhere the callee owns.

## Consequences

- `x86-uefi-call2` and `x86-uefi-call-wide` are untouched. Their bytes are the
  ones that booted, and this action's frame differs from both (the original
  RSP moves from +0x30 to +0x28 to make room for the out-word), so it gets its
  own encoder rather than a parameter on theirs.
- The five registers Microsoft x64 does not preserve -- RAX, RCX, RDX, R8 and
  R9, which are kotoba-mir's scratch tier plus the guest's hidden context --
  are saved and restored here, as they are for every other firmware call, and
  every operand is read out of its allocated register BEFORE any argument
  register is written.
- Nothing changes in kotoba-mir or kotoba-codegen. Six operands fit the
  privileged tier that already carries `:uefi-call6`'s eight, and
  `:x86-privileged` is one MC keyset whatever the action.
- There is no AArch64 arm. The action is gated to the aiueos UEFI target in
  amu, and that target is x86-64.
