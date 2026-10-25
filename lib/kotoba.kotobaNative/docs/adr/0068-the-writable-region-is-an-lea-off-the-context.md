# ADR-0068: The writable region is an `lea` off the context, and it is UEFI-only because a kernel's context has a GDT there

- Status: accepted
- Date: 2026-09-02

## Context

kotoba-gmir ADR-0013 added `:scratch-region`, the base of the writable area an
image packager reserves inside the image's own `.data`. It exists because
every remaining UEFI boot service takes an out-pointer and a Kotoba UEFI
application had no address it was allowed to write.

## Decision

**Four bytes: `4d 8d 51 60` -- `lea r10,[r9+0x60]`.**

```
4d   REX.W + REX.R + REX.B
8d   LEA
51   ModRM mod=01 reg=010 (R10) rm=001 (R9)
60   disp8, kotoba.native.image-scratch/offset
```

`:boot-info` one arm above is `4d 8b 51 50` -- the same ModRM byte shape with
the LOAD opcode and a different displacement. That one byte is the whole
difference between *the word the firmware handed us* and *somewhere we may
write*, and the suite asserts each program contains its own instruction and
NOT the other's, in both directions.

An `lea` rather than a `mov` because nothing is read. The answer is the
ADDRESS of the reservation; there is no word stored at +0x60 to load, and a
`mov` there would return whatever the packager happened to leave in the first
quadword of the scratch area -- which under the current packager is zero, so
the mistake would look like "the region is not reserved yet" rather than like
a wrong opcode.

**The offset and the size live in `kotoba.native.image-scratch`, not here.**
That namespace is read by this encoder and by amu's PE32+ packager, which is
the same discipline `kotoba.native.interrupt-abi` established for the
interrupt entry's stride and context slot: the packager that honours a number
and the encoder that assumes it read the same var. It fails closed if the
offset ever exceeds the disp8 this four-byte encoding assumes.

## Why it is UEFI-only, and this is measured

The offset is a displacement off the hidden context register, so the same four
bytes mean something in every image that has a context. **In the JVM kernel
image they mean the global descriptor table.**
`kotoba.native.elf64/kernel-gdt-offset` is 96 -- the same 0x60 -- and the
kernel's runtime data continues past it with the GDTR at 152 and the TSS at
168. A kernel that asked for scratch at this displacement would be handed its
own segment descriptors and would write over them.

So the operation is gated to the UEFI target in amu rather than given a second
displacement for kernel images. A second displacement is a second layout, and
both ELF twins -- `elf64.clj` and `elf64.cljc` -- would have to agree on it
byte for byte, which is the property `verify-jvm-free-object-parity` exists to
protect. Neither ELF packager is touched by this change.

This is an admission of a gap for kernel images, not a claim that they do not
need scratch. A kernel image already receives a boot-info structure and a
16 KiB memory map from its loader; what it does not have is a slot this
operation could name without moving something that is already there.

## Consequences

- `.o` objects are unaffected: the object route's context is its own private
  80 bytes and the target gate refuses the operation before packaging.
- The reservation's SIZE is not enforced here. This encoder emits an address;
  the ceiling on a window over it is kotoba-sema's (ADR-0024), and the bytes
  themselves are reserved by amu's packager.
