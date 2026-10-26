# ADR-0040 — Recoverable C-free #PF frames run on an allocator-owned stack

Date: 2026-08-12

## Status

Accepted and executable. This advances ADR-0039's non-returning page-fault
evidence into one bounded recovery path. It does not claim general exception
recovery or double-fault containment.

## Decision

The boot allocator publishes eight contiguous, zeroed pages. The first six
retain their ADR-0039 roles; page seven is a 4 KiB exception receipt frame and
page eight is a dedicated 4 KiB handler stack. Both remain supervisor RW+NX.

The compiler exposes three additional sealed operations: the fixed recoverable
#PF entry address, configuration of one distinct aligned frame/stack pair, and
one fixed guard-page store whose faulting instruction length is compiler-owned.
No arbitrary handler, stack switch, pointer store, RIP rewrite, or `iretq` is
available to guest Kotoba.

The handler independently accepts only CR2 `0x100000` and error bits
`P=0,W=1`. It records CR2, error code, original RIP, and the dedicated stack
top. The CPU frame's RIP points at the faulting store, not at the start of the
whole probe, so the handler advances it by the exact four-byte store encoding.
Receipt work runs on the dedicated stack; the handler restores the interrupted
stack and every general register it touches before `iretq`. Kotoba then reads
and independently validates the allocator-owned frame.

Invalid configuration returns zero fail-closed. Aliasing the frame and stack
pages therefore exits before installing the recovery probe.

## Executable evidence

- exact Amu/compiler closure: `1de9dafe71c12b68233fb815d5cd36208a9b22a4`;
- positive ELF SHA-256:
  `9ae5180a92f0fffe9e153a1440f8eda507c0f0c4d35f16c633ac3a609e5bbbd7`
  (49,520 bytes);
- normal boot: `MPRCD`, isa-debug-exit status 33;
- recoverable guard fault: `MPRCDRE`, status 33 (`R` from the handler, `E`
  from Kotoba frame validation after `iretq`);
- frame/stack alias mutation: `M`, status 49;
- existing non-returning evidence remains independent: `G`/51, `W`/53,
  `X`/55;
- receipt v5: no C source/object, CRT, linker input, import, or dynamic
  dependency; fuel 32,768; allocator pages 8; RX/RW-NX boundary rederived.
- static suites: kotoba-native 139 tests / 1,807 assertions, Amu 970 / 7,658,
  aiueos 442 / 1,396; GMIR 13 / 80, Sema 7 / 35, KIR 134 / 575, and
  independent Verifier 48 / 269.

The QEMU gate found two real ABI errors before landing: an inline configuration
template incorrectly contained `retq`, and the first recovery attempt advanced
saved RIP by the whole probe rather than the four-byte faulting instruction.
Static admission did not catch either error.

## Remaining boundary

This is one same-privilege, known-instruction recovery vector. Still open are
#DF with TSS/IST, common exception frames, nesting/reentrancy, per-CPU state,
CPL3 returns, dynamic map/unmap, and APIC/SMP TLB invalidation.

Next, install a minimal TSS and #DF IST gate whose only successful outcome is
a distinct fail-closed receipt. This manually selected #PF stack is not
evidence that hardware stack switching already exists.
