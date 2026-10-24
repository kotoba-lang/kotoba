# ADR-0008: Four privileged actions for the UEFI firmware boundary

- Status: accepted
- Date: 2026-09-02

## Context

AIUEOS's BOOTX64.EFI is C (`os/aiueos/uefi/main.c`). To write it in Kotoba the
privileged family has to be able to name three things it could not:

- the `EFI_SYSTEM_TABLE*` UEFI hands an image entry point;
- a 64-bit read of a firmware-owned structure;
- a call through a Microsoft x64 function pointer stored in one.

and one more the loader needs at the end: entering a kernel and not returning.

## Decision

Four actions join `x86-privileged-action-arities`.

| action | arity | meaning |
|---|---|---|
| `:system-table` | 0 | the `EFI_SYSTEM_TABLE*` the entry shim parked in the context |
| `:load-ptr` | 2 | `(base, byte-offset)` -> the 64-bit word there |
| `:uefi-call2` | 4 | `(base, slot-offset, a, b)` -> call `[base+slot-offset]` MS-x64 with `a`, `b`; returns its status |
| `:jump-to` | 2 | `(address, boot-info)` -> enter `address` with the SysV first argument set; does not return |

`:load-ptr` is unchecked on purpose. The checked `kernel-load-*` family takes a
window LENGTH from the guest, and a guest does not have one for
`EFI_SYSTEM_TABLE` or for a protocol structure hanging off it -- the firmware
owns both, so any length the guest declared would be invented. This reads the
boundary the way `:in-u8` reads a device: privileged, never oracled, and only
at the boundary. Everything past it uses the checked family.

`:uefi-call2` takes exactly four operands rather than a variadic list because
`kotoba.mir`'s conservative expansion hands a privileged action the scratch
tier, and that tier is four registers wide on x86-64. Two UEFI arguments cover
a bootloader's first calls -- the ConOut methods and `ExitBootServices`.
`GetMemoryMap` (five) and `OpenProtocol` (six) need an argument channel that
does not fit in registers at all; that is a separate decision, not a wider
version of this one.

## Consequences

- These are x86-only by construction: `kotoba.mir` admits the privileged
  channel for `:x86-64` and no other target. AArch64 firmware has no
  counterpart to model here.
- GMIR states the shape and the arity. It does not state WHICH compile target
  may use them -- amu gates `:uefi-call2`, `:load-ptr` and `:jump-to` to
  `:x86_64-aiueos-uefi-v1`, since GMIR does not see a target keyword.
- `:jump-to` produces a `:gmir/dst` like every other action and never writes
  it. That is the family's shape, not a claim that control returns.
