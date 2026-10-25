# ADR-0046: A literal pool at the end of `.text`, and a call wider than the tier

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0011 added `:gmir/rodata-address` and two wider firmware
calls. Both need bytes here.

## Decision

**A literal's address is `lea dst,[rip+disp32]`, seven bytes.** Not
`mov reg, imm64`, which is what `:x86-64/data-address` resolves to: that
instruction holds an OFFSET from the start of the emitted buffer, and something
else adds the base. Under firmware there is no something else -- the image is
loaded wherever the loader chose and there are no relocations to fix up. The
same property makes this work in a relocatable kernel object: a displacement
inside one section needs no relocation at all, so the aiueos object's "exactly
one R_X86_64_PC32" rule is untouched.

ModRM mod=00 rm=101 is the RIP-relative form in 64-bit mode and "disp32, no
base" in 32-bit mode; the displacement is measured from the END of the
instruction. Both were checked by disassembling the emitted bytes with
`llvm-mc`, not by assembling the intent.

**The pool sits after the code and after the UTF-8 string pool**, so no
existing offset moves and no golden changes. Every entry starts on an 8-byte
boundary (`gmir/rodata-alignment`): UCS-2 needs 2 and `EFI_GUID` needs 4, and
edk2 compares a GUID as two `UINT64`s. The pool's own start is aligned too, so
an entry's alignment is a property of the image rather than of what happens to
precede it.

**Padding is conditional.** Aligning the pool start unconditionally appends
alignment bytes to every program, including the ones with no literals at all;
that moved the tail of the string pool and reddened
`immutable-utf8-data-is-laid-out-after-machine-code` on both ISAs. Caught by
running the whole suite rather than the new file.

**Entries are keyed on [encoding content].** The same sixteen hex digits are
eight bytes as `:hex-bytes` and would not parse at all as a GUID, so content
alone is not an identity.

**`:uefi-call4` and `:uefi-call6` share one encoder and one frame, and
`:uefi-call2` keeps its own.** The ordering problem the narrow encoder solved
by staging one argument through R10 does not scale past two arguments -- there
is one R10 -- so the wide encoder solves it structurally: EVERY argument is
written to the outgoing frame before ANY argument register is loaded. Reads all
happen while the sources are intact; writes all happen afterwards. The staging
area for arguments 1-4 is the callee's own shadow space, which is exactly what
shadow space is.

```
+0x00..0x18  shadow space / staging for arguments 1-4
+0x20        argument 5      +0x28  argument 6
+0x30        original RSP
+0x38..0x58  RAX, RCX, RDX, R8, R9
```

0x60 is a multiple of 16, so RSP is still 16-aligned at the `call`. A
four-argument call allocates the same frame and does not write +0x20/+0x28 --
sizing the frame by the argument count would save sixteen bytes of stack and
add a second layout to verify. `:uefi-call2`'s frame is 0x50, and those bytes
are the ones that booted (amu ADR-0291), so it was left alone.

## Consequences

- ~~The literals are x86-only and `kotoba.mir` says so with its own keyword,
  `:rodata-address-target-mismatch`.~~ **Superseded 2026-09-09.** They emit on
  both ISAs. The refusal claimed the blocker was ADRP+ADD's 4 KiB page split;
  the blocker was the wrong instruction. `adr Xd, label` reaches ±1 MiB in one
  instruction with no page arithmetic, and the pool this ADR places sits at the
  end of the same emitted buffer as the code — so the distance is bounded by
  the size of one program, which is the fact a *linker* cannot know and this
  backend can. `a64-adr` refuses with `:rodata-literal-out-of-range` rather
  than truncating if a program ever exceeds it. The refusal keyword is gone
  rather than narrowed (`targets` holds exactly two), and `isa-parity` is back
  to TWO refusal reasons, with `a64-rodata-literals-emit-the-adr-encoding`
  replacing the three rows that left `x86-only`.
- `bytes-literal-length` never reaches the pool: it lowers to a
  `:gmir/constant`, derived from the same text the address is derived from.
- The non-word-typed fallback emitter does not implement the literal heads,
  exactly as it does not implement the four ADR-0291 operations.
