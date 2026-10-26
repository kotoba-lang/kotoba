# ADR-0037 — Native paging is real only after the CPU accepts it

Date: 2026-08-11

## Status

Accepted and executable as a bounded first-GiB activation slice.

## Context

ADR-0036 established boot-lifetime ownership for a zeroed page-table root, but
an allocated page named PML4 was not yet a page table. Likewise, bytes shaped
like entries would not establish that the CPU had accepted them. The next gate
must cover construction, activation, and continued execution without adding C,
a linker, or another foreign object.

## Decision

The native kernel admits five contiguous Conventional Memory pages. One holds
the ownership bitmap, three hold PML4/PDPT/PD, and one exercises release and
reuse. Kotoba writes little-endian entries through bounded page authorities:
PML4[0] points to PDPT, PDPT[0] points to PD, and 512 PDEs identity-map the
first GiB with 2 MiB leaves. Every entry is supervisor RW and present; PDEs also
set PS (`0x83`). The kernel validates both links and representative first,
second, and last leaves before changing CR3.

It then loads the PML4 physical address into CR3, reads CR3 back, executes
`invlpg` for a mapped address, and emits `MPRC` only after execution continues
under the new tables. The identity shape preserves the currently executing
kernel, stack, boot-info, and allocator pages.

Post-switch table-byte checks are not reused as evidence. The current bounded
authority values were derived while the firmware map was active; assuming that
the same wrapper remains a qualified authority after an address-space change
would silently cross an unproved boundary. Exact table readback is therefore a
pre-switch obligation. Post-switch evidence is CR3 readback plus continued CPU
execution and observable I/O.

## Executable evidence

The ELF verifier requires sealed fuel 8192, five published pages, the first-GiB
map claim, and concrete CR3-read, CR3-write, and `invlpg` instruction encodings.
The normal x86-64 KVM/OVMF run must emit `MPRC` and debug-exit status 33.

`smoke-qemu-kotoba-native-page-table.sh` clears Present from the PML4 link while
leaving its independent readback expectation unchanged; validation must stop at
`M`/47 before CR3 is written. `smoke-qemu-kotoba-native-cr3.sh` retains the
firmware CR3 after constructing valid tables; CR3 readback must stop at `M`/49
before `P`, `R`, or `C` is published. The ownership, overlap, and exhaustion
mutations remain independent gates.

## Consequences and next boundary

The C-free path now owns and activates its bootstrap tables rather than merely
naming an allocated page as their future root. This map is intentionally broad:
its first GiB is RW and executable. It does not claim W^X, guard pages, dynamic
unmapping, or a general physical allocator. Those are the next CPU/memory
boundary and require their own negative evidence.
