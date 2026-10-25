# ADR-0003: Four spellings for the UEFI firmware boundary

- Status: accepted
- Date: 2026-09-02

## Context

`kernel-privileged-operations` could name every x86 instruction a kernel needs
and nothing a UEFI application needs. AIUEOS's BOOTX64.EFI is C for exactly
that reason.

## Decision

Four heads join the map, at the arities kotoba-gmir ADR-0008 fixes:

```clojure
kernel-system-table 0   kernel-load-ptr 2
kernel-uefi-call2   4   kernel-jump-to  2
```

`kernel-load-ptr` is UNCHECKED, unlike every `kernel-load-*` beside it, and
that is the decision rather than an omission. The checked family takes a window
LENGTH from the guest; a guest has no length for `EFI_SYSTEM_TABLE` or for a
protocol structure hanging off it, because the firmware owns both. A declared
length would be invented, and a bounds check against an invented length is
WORSE than no check, because it reads as a guarantee. `kernel-load-ptr` reads
the boundary the way `kernel-in-u8` reads a device; everything past the
boundary uses the checked family.

`kernel-uefi-call2` carries exactly two UEFI arguments because the register
allocator hands a privileged operation the scratch tier and that tier is four
registers wide (kotoba-mir, 2026-09-02). Two is what a bootloader's first calls
need. `GetMemoryMap` (five) and `OpenProtocol` (six) need an argument channel
that does not fit in registers at all.

## Consequences

- This frontend admits all four target-independently, exactly as it already
  admits `kernel-write-cr3` for `x86_64-linux-kotoba-v1`. The target gate lives
  in amu, which is the only layer that sees a target keyword next to a KIR
  module. `kotoba.compiler.uefi-boundary-test` says so in its own docstring so
  a reader does not mistake admission here for permission.
- `kernel-jump-to` declares an i64 result because every operation in this map
  does. Nothing reads it; control does not come back.
