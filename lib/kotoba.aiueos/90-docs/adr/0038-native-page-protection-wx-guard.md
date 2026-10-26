# ADR-0038 — Activated native paging is not protected paging

Date: 2026-08-11

## Status

Accepted and executable for the C-free bootstrap address space.

## Context

ADR-0037 proved that the CPU accepted allocator-owned page tables, but every
2 MiB identity leaf was writable and executable. Names such as `.text`, an RX
ELF program header, and “guard” do not constrain the CPU. The active PTEs and
control registers must carry those constraints.

## Decision

The allocator admits six contiguous Conventional Memory pages: ownership,
PML4, PDPT, PD, a low 4 KiB PT, and the release/reuse probe. PDE 0 points to
the low PT; PDEs 1–511 remain 2 MiB identity leaves but are RW+NX. In the low
PT, page `0x100000` is absent, `0x101000`–`0x109fff` is supervisor RX, and the
compiler-owned context at `0x10a000` plus every other admitted identity page is
RW+NX.

Before loading CR3, the kernel requires CPUID extended leaf `0x80000001` EDX
bit 20, sets EFER.NXE, sets CR0.WP, and reads both controls back. CR0 access is
a closed kernel intrinsic carried through Sema, KIR, Verifier, GMIR, Amu, and
both direct/MIR x86 emitters; it is not a general guest register interface.

The x86 kernel ELF package fixes its RW segment at `0x10a000`. The verifier
rejects text that crosses that page boundary, so future code growth cannot
silently turn state executable or leave an unmeasured RX gap.

## Executable evidence

The final kernel ELF is reproducible at SHA-256
`38a2cc28c0dccfce692fe40cd0884d2eb21553668ce252734cbc127c49a43624`.
The x86-64 KVM/OVMF positive run emits `MPRC` and exits 33.

`smoke-qemu-kotoba-native-page-table.sh` mechanically maps the guard page while
retaining the independent absent-PTE expectation. It is rejected at `M`/47
before CR3 activation. `smoke-qemu-kotoba-native-wx.sh` mechanically adds RW to
the text leaves while retaining their P-only expectation and is independently
rejected at `M`/47. The ELF verifier also requires concrete CPUID, RDMSR,
WRMSR, CR0-read, CR0-write, CR3, and `invlpg` encodings; receipts record six
pages and the exact permission split with no C source, object, CRT, linker,
import, or dynamic dependency.

## Consequences and next boundary

The bootstrap address space is now activated and protected, but the mutation
gates prove policy validation before activation. They do not yet prove that a
handled CPU page fault reports write-to-RX, execute-from-NX, or guard access.
The next memory slice is a minimal C-free IDT/page-fault path with independent
hardware-fault probes, followed by dynamic mapping/unmapping and TLB evidence.
This remains separate from scheduler, CPL3, typed syscall, and the first log
provider semantic vector.
