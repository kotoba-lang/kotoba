# ADR-0039 — C-free page faults are CPU evidence, not table inspection

Date: 2026-08-12

## Status

Accepted and executable. This supersedes ADR-0038's remaining claim that the
guard/RX/NX policy has no handled hardware-fault evidence, and supersedes the
Phase-2 maturity row in ADR-0013 where it still describes broad RW+X paging.

## Context

ADR-0038 split the bootstrap map into guard, RX text, and RW+NX state, but its
negative gates deliberately stopped before CR3 activation. They proved that
Kotoba rejected malformed PTEs, not that the CPU enforced valid PTEs. A C or
assembly interrupt stub would make the demonstration easy while widening the
production TCB that this path exists to remove.

The additional handler and gate construction grew the kernel past the sealed
nine-page RX allocation by 1,271 bytes. The ELF packager refused the image
instead of overlapping the RW context. The text allocation is therefore
explicitly advanced by one page: `0x101000..0x10afff` is RX and context/state
starts at `0x10b000` as RW+NX. Every PTE assertion, ELF segment boundary,
compiler test, verifier check, and NX probe moves together.

## Decision

Expose only six x86 kernel operations through Sema, KIR, the independent
Verifier, GMIR, and both native emitters:

- current CS selector;
- the address of one sealed, non-returning page-fault evidence entry;
- bounded `lidt` plus exact `sidt` limit/base readback;
- guard-write, text-write, and NX-execute diagnostic probes.

No arbitrary interrupt handler, raw descriptor-table mutation, arbitrary
pointer store, or arbitrary indirect call is added. Kotoba builds vector 14 in
the allocator-owned sixth page. The backend entry reads CR2 and the CPU-pushed
page-fault error code and independently accepts exactly:

- `G`: CR2 `0x100000`, non-present supervisor write (`P=0,W=1`);
- `W`: CR2 `0x101000`, present supervisor write (`P=1,W=1`);
- `X`: CR2 `0x10b000`, present instruction fetch (`P=1,I=1`).

An unexpected address or error-code shape emits `F` and a distinct failure
exit. The entry never returns; this is a diagnostic evidence boundary, not yet
a recoverable exception ABI.

## Executable evidence

Exact compiler: Amu `87ed2088ffc155b83a8e8fbc65103ee8be9694ed`.

Positive artifact:

- SHA-256 `1ef962ae430582bb0f0b18c46f21a3928d64c280b9863e9141ed9c52dc816af8`;
- receipt `aiueos-kotoba-native-receipt/v4`;
- QEMU/KVM+OVMF marker `MPRCD`, isa-debug-exit status 33;
- no C source/object, CRT, linker input, import, or dynamic dependency.

Three source mutations each compile a separate artifact containing exactly one
sealed probe. Real QEMU execution produces:

| Probe | CPU-derived marker | Status |
|---|---:|---:|
| guard write | `MPRCDG` | 51 |
| RX text write under CR0.WP | `MPRCDW` | 53 |
| RW+NX state execute | `MPRCDX` | 55 |

The static suites remain green: GMIR 13/80, Sema 6/33, KIR 134/575, Verifier
48/269, kotoba-native 139/1,795, Amu 966/7,643, and aiueos 431/1,305.

## Consequences and next boundary

W^X and the guard now have both table-construction evidence and independent
CPU-fault evidence. Still not claimed: `iretq` recovery, a common exception
frame, nested faults, a double-fault IST, per-CPU IDT/TSS, user-mode faults,
dynamic unmap/access evidence, or durable crash receipts on this C-free path.

Next, factor the non-returning evidence entry into a bounded exception-frame
ABI with a dedicated fault stack and double-fault containment. Dynamic
mapping/unmapping and TLB evidence follow; scheduler/CPL3/syscall and the first
typed log provider remain separate dependency stages.

ADR-0040 closes the bounded frame, dedicated software-selected handler stack,
and one exact `iretq` recovery slice. Hardware TSS/IST switching and #DF remain
open there rather than being implied by this ADR.
