# ADR-0030 — CPU feature detection in Kotoba, and the first `cpuid` this OS has executed

- Status: accepted
- Date: 2026-08-06
- Extends: ADR-0026 (MSR access), ADR-0029 (PIC shutdown)

## Context

The `cpuid` primitives (`kernel-cpuid-eax/-ebx/-ecx/-edx`) landed in the compiler
the previous iteration and had **never been executed**. They encoded correctly
and were admitted by frontend → KIR → verifier → codegen, and no CPU had run
one. That is the same position the MSR primitives were in before ADR-0026, and
the fix is the same: port the first callers.

Six `cpuid` sites remained in the kernel. Reading them showed they ask **three**
questions, and only two are feature tests:

| Site | Leaf | What it wants |
|---|---|---|
| `paging.c:83,86` | `0x80000001` | EDX bit 20 — NX support |
| `process.c:124,127` | `0x80000001` | EDX bit 11 — SYSCALL support |
| `pci.c:668,709` | `1` | **`(ebx >> 24) & 0xff` — the initial APIC ID** |

The third is not a feature test at all. It is a value extraction feeding the
MSI-X message destination (`0xfee00000 | (dest << 12)`), which is why it needed
different treatment from the other two.

## Decision

Three Kotoba objects, not one generic `(cpu-feature leaf bit)`:

- `cpu-feature-nx.kotoba` → `kotoba_aiueos_cpu_feature_nx`
- `cpu-feature-syscall.kotoba` → `kotoba_aiueos_cpu_feature_syscall`
- `cpu-apic-id.kotoba` → `kotoba_aiueos_cpu_apic_id`

**Knowing which leaf and which bit answers a question is the decision.** A
generic accessor would leave that as magic numbers at the C call site, which is
exactly what ADR-0015's split exists to remove. Each object bakes in its own
leaf and bit, and each repeats the max-extended-leaf guard, because a kernel
object exports one symbol and cannot call another — the duplication is the
price of that isolation, as it was for the two IPv4 checksums (ADR-0021).

## Consequences

- **`cpuid` has now executed on target**, and each object is proven by a
  consequence rather than by a marker asserting itself:
  - NX — `AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp` *and*
    `AIUEOS_PAGE_FAULT_OK no-execute vector=14`. The object returned 1, the
    `PTE_NX` bit was set, and a no-execute fault actually fired.
  - SYSCALL — `AIUEOS_SYSRET_OK star-lstar-fmask` and `AIUEOS_USER_SYSCALL_OK`.
  - APIC ID — `AIUEOS_VIRTIO_RNG_MSIX_OK vector=34` and
    `AIUEOS_VIRTIO_BLK_MSIX_OK vector=35`: MSI-X completions arrived, so the
    destination the extraction produced addressed the right CPU.

- **The signed/unsigned hazard is real here and is carried by the hardware, not
  by emitted code.** `(>= eax 0x80000001)` compiles to `cmpq`/`setge` — a
  *signed* compare — where the C compared `uint32_t`. It agrees only because
  `cpuid` writes a 32-bit register and a 32-bit write zeroes bits 63:32, so RAX
  cannot exceed `0xffffffff`. Note the `-eax` query emits **no result move at
  all** (the value is already in RAX), so unlike the `-ebx`/`-edx` paths there is
  no 32-bit `mov` doing the zero-extension — it rests entirely on the
  instruction's own semantics. Fed the sign-extended pattern
  `0xffffffff_80000001`, the object answers 0 where the C answers 1; NX would
  never be enabled and the symptom would be a page fault on the first access to
  any mapped page.

- **`cpuid` clobbers RBX, which is callee-saved, and the result move must sit
  inside the save/restore bracket.** It does:
  `push %rbx / cpuid / mov %ebx,%eax / pop %rbx`. Had the `mov` landed after the
  `pop`, the APIC ID would silently have been whatever RBX held on entry.

- **Mask-before-divide, again.** `(ebx >> 24) & 0xff` is written
  `(quot (bit-and ebx 0xff000000) 0x1000000)`. `quot` emits `cqto`/`idivq` —
  signed division truncating toward zero, which disagrees with `>>`'s floor on
  negatives. Masking first bounds the dividend to `0x00000000ff000000` so `cqto`
  writes 0 into RDX. Divide-first would also be correct *given* the
  zero-extension; mask-first costs the same and does not depend on it. For
  `0xffffffff_80000001` divide-first yields 129 against a correct 128.

- **Fuel: 1 unit per call, measured from the disassembly.** `cpuid` is emitted
  inline (`0f a2`) and charges nothing — checked rather than inferred from the
  `kernel-out-u8` precedent. All three are left out of `bounded-memory?`, so
  each has the unreplenished 512 for the whole boot. NX and SYSCALL are called
  once each; **APIC ID is called twice** in the gate configuration, because the
  PCI enumeration loop does not break after a device of each kind succeeds, so a
  second MSI-X-capable function would program again. The ceiling is 512 MSI-X
  setups per boot — a bound on device count, not on anything this object
  controls.

- **`build-multiboot.sh` links none of the three**, deliberately: it compiles
  `entry.S`, `multiboot/main.c`, `acpi.c`, `apic.c`, and none of
  `paging.c`/`process.c`/`pci.c`. That is now a comment rather than an
  omission — the same class of mistake that broke the multiboot link at
  ADR-0024 and was not caught until ADR-0027, because the UEFI gate does not
  exercise that path. Verified by building both.

- **What is still C.** Six `cpuid` sites are gone; the remaining inline asm is
  `outb`×5 / `outl`×1, `pause`×11, `cli`×9, `sti`×8, `hlt`×8 — all of which have
  primitives already — plus `lgdt`/`lidt`, which do not. The `sti; hlt` pairs
  cannot become two separate Kotoba calls: separating them opens a race where an
  interrupt arrives between enabling and halting, and the CPU sleeps through it.
  The interrupt-entry stub stays asm; a defined stack frame and `iretq` are pure
  mechanism.

- Gates: UEFI smoke with `AIUEOS_TEST_NET=1 AIUEOS_TEST_DMAR=1` green;
  multiboot 4/4 (it was ~22% flaky before ADR-0028's PIC remap to 0xE0/0xE8, so
  repeated runs remain the honest measurement); kotoba-native 72 tests /
  2640 assertions, 0 failures.
