# AIUEOS kernel C/asm: what is left and which intrinsics are missing (JUN-597)

This reads the generated inventory, [`kernel-c-inventory.md`](kernel-c-inventory.md), with its
receipt [`kernel-c-inventory.json`](kernel-c-inventory.json), and maps it onto the migration
steps JUN-598 (PCI / MMIO), JUN-599 (GDT / IDT / entry) and JUN-600 (paging / page ownership).
Everything here is from source text at kotoba `ee39c21bd` and Amu `c0fa6b59a`. Nothing was
built, run in QEMU or measured on hardware for this inventory.

Regenerate it with:

```sh
python3 lib/kotoba.aiueos/tools/kernel_c_inventory.py \
  --kernel lib/kotoba.aiueos/os/aiueos/kernel \
  --amu /path/to/kotoba-lang/amu --amu-rev c0fa6b59a57732c537360c58f32b6ee849e5a0ec \
  --out lib/kotoba.aiueos/docs/kernel-c-inventory
```

## Size of what is left

The 18 files hold 20,238 lines: 680 C functions and 39 asm global symbols. Classified from the
text (a heuristic: a function in two categories is put in the first that applies, in the order
below):

| class | count | meaning |
|---|---|---|
| `unresolved-instruction` | 8 | inline asm with an instruction Amu has no intrinsic for |
| `needs-intrinsic` | 57 | inline asm whose every instruction already has an Amu intrinsic |
| `kotoba-glue` | 108 | calls a Kotoba-emitted object (`kotoba_aiueos_*`) and has no asm of its own |
| `privileged-via-helper` | 50 | no asm, but calls a C helper that has asm (`in8`, `read_cr3`, ...) |
| `c-logic` | 457 | plain C |
| `asm-entry` | 39 | `.S` code: entry stubs, the AP trampoline, qualification entry |

`main.c` and `pci.c` are 74% of the lines. `aiueos_kernel_main` alone is lines 4004-7987 of
`main.c`, so its class says little; it has to be split before it can move.

## Instructions that already have an intrinsic

Port I/O (`in`/`out` at 8, 16 and 32 bits), MSR read/write, CR0/CR2/CR3/CR4, `invlpg`, `lidt`,
`cli`/`sti`/`hlt`/`pause`, `rdtsc`/`rdrand`/`rdseed`, `cpuid`, `xgetbv`/`xsetbv` and reading CS
all exist in Amu's kernel target. The 57 `needs-intrinsic` functions use only these. Most are
small helpers (`in8`, `out16`, `read_cr3`, `lock`), and the 50 `privileged-via-helper`
functions reach privileged instructions only through them. Moving a helper's callers to Kotoba
needs no new compiler work for the instruction itself; width, extent and ABI still have to be
checked per use (JUN-598 / JUN-600).

Volatile MMIO in C maps to the existing `kernel-load-uN` / `kernel-store-uN` (8, 16, 32, 64
bits, with 16 KiB-tier variants) and `kernel-pci-mmio`. The inventory marks functions with
volatile access but does not prove each access fits a tier.

## Instructions with no intrinsic

| instruction | where | step |
|---|---|---|
| `lgdt`, `ltr`, `ljmpl`, `lretq` | `entry.S:aiueos_load_gdt`, `aiueos_load_task_register`, `ap_trampoline.S` | JUN-599: descriptor-table load and the far jump / far return that reload CS |
| `iretq`, `sysretq`, `pushfq` | `entry.S` ISR stubs, `aiueos_syscall_entry`, `aiueos_enter_user` | JUN-599: the return-to-user and interrupt-return paths, which are whole entry ABIs, not single intrinsics |
| `cld`, `ud2` | `ap_trampoline.S`; `main.c:aiueos_kernel_main` (a deliberate invalid-opcode probe) | JUN-599 / qualification probes |
| `mfence` | `vtd.c:aiueos_vtd_initialize`, `aiueos_vtd_program_msix` | JUN-598 / JUN-600: an ordering barrier for IOMMU programming |
| `lfence`, `rdtscp` | `main.c:aiueos_read_tsc`; `pci.c:rtl8125_direct_tsc`, `aiueos_rtl8125_direct_https_qualification` | timing reads; `rdtsc` exists, its serialising forms do not |
| `syscall`, `int` | `process.c:call`, `syscall.c:invoke` | user-side probes that enter the kernel; they need a user-mode target, not a kernel intrinsic |

None of these is added by this issue. JUN-552 asks that no instruction be added without a need.
For the entry paths, the open design question is whether Amu emits whole entry stubs (save
frame, call Kotoba, `iretq`/`sysretq`) as codegen, rather than exposing each instruction to
Kotoba code.

## Asm that is not a single-instruction gap

`ap_trampoline.S` starts an application processor in 16-bit real mode and walks it through
32-bit protected mode to long mode. Amu has no 16- or 32-bit code generation, so this file needs
either that, or to stay as a bounded asm boundary with a documented removal condition. That is a
hardware-specific item that JUN-599 must decide. `qualification_entry.S` (5 symbols) carries the
qualification key load/save paths around CR3 changes.

## What this does not claim

- That any listed function is safe to move as is, or that the class is right for every function:
  the class is a text heuristic, and `aiueos_kernel_main` mixes everything.
- That an existing intrinsic has the width, extent, ABI or verifier rule a particular use needs.
- Anything about QEMU, real hardware, CI or release state.
