# aiueos AArch64 UEFI boot spike — track (a) landed

Home of the AArch64 bare-metal boot path (ADR-2608080600 tracks a1/a2, "landed"):
a UEFI loader, a freestanding kernel with a self-built `TTBR0_EL1` and enforced
W^X, and the evidence gate that proves it. This material was staged in the
`com-junkawasaki/root` superproject at `70-tools/aiueos-aarch64-spike/` until a
session with `kotoba-lang` access could land it; track (a) of the ADR is the
migration that completed here.

Decision record: `90-docs/adr/2608080600-*.edn` (in the superproject)
Measured evidence: `90-docs/evidence/260808-aiueos-aarch64-uefi-boot-v1.edn` (in the superproject)

## What it is

**`boot.c`** — an AArch64 UEFI loader mirroring the shape of the x86_64
`os/aiueos/uefi/main.c`. Walks boot services, locates GOP, reads
`\EFI\AIUEOS\KERNEL.ELF` off the ESP, admits only bounded `ET_EXEC` AArch64
`PT_LOAD` segments into a reserved 2 MiB window, captures the UEFI memory map,
calls `ExitBootServices`, and hands a boot-info struct to the kernel.

**`kernel.c` / `kentry.S` / `kernel.ld`** — the freestanding AArch64 kernel.
Validates the boot-info handoff, walks the UEFI memory map to admit usable
physical memory, allocates pages from it, builds its own stage-1 EL1 translation
tables **out of those pages** (4 KiB granule, `T0SZ=25`), replaces the
firmware's mapping via `TTBR0_EL1`, and then **proves W^X is enforced** by
violating it in both directions.

**`bootinfo.h`** — the handoff ABI, field-for-field identical to the x86_64
`struct aiueos_boot_info`. The ABI is one of the genuinely arch-neutral pieces
of the port; only the mechanism that fills it differs.

**`smoke-qemu-aarch64-uefi.cljs`** — the evidence gate. nbb, not shell, per the
2026-07-14 owner rule.

This is the AArch64 counterpart of the x86_64 Phase-1/2 evidence: *"the kernel
replaces the firmware CR3 with its own four-level identity map, enables
write-protect and NX, and maps text RX, rodata R+NX, and writable state RW+NX.
The smoke test writes to text and attempts to execute a byte in rodata; both
must raise vector 14."* The mechanism differs completely — `TTBR0`/`TCR`/`MAIR`/
`SCTLR` instead of `CR3`/`CR0`/`EFER`, `ESR_EL1` instead of an error code, no
port I/O — while the decision the evidence encodes is identical.

## Running it

```bash
kbb --backend sci smoke-qemu-aarch64-uefi.cljk                   # boot evidence gate
kbb --backend sci smoke-qemu-aarch64-uefi.cljk --display-matrix   # GOP probe across devices
kbb --backend sci smoke-qemu-aarch64-uefi.cljk --expect-fail      # both negative controls
```

Needs `clang`, `lld-link`, `ld.lld`, `qemu-system-aarch64`, `mkfs.vfat`,
`mcopy`, `mmd`, and AAVMF firmware at `/usr/share/AAVMF/`. On Debian/Ubuntu:
`qemu-system-arm qemu-efi-aarch64 ipxe-qemu seabios dosfstools mtools`.

## The gate judges substance, not markers

It parses `SCTLR_EL1` to confirm bit 0 is actually set, and requires each W^X
probe to report the exact ESR exception class (`0x25` data abort / `0x21`
instruction abort at the current EL) with a level-3 permission fault.

It also requires the translation tables to have come from the page allocator
(`from=allocator`), so an allocator that exists but is never used fails.

`--expect-fail` runs three controls, all watched being rejected:

| control | what it breaks | why it is refused |
|---|---|---|
| `no-loader` | ESP with no `BOOTAA64.EFI` | nothing boots; 23 unmet |
| `wx-not-enforced` | `-DAIUEOS_BREAK_WX`: every page writable *and* executable | boots fully, prints `MMU_OK` **and** `KERNEL_OK`; refused on the 2 W^X checks alone |
| `pmm-admission-trusts-map` | `-DAIUEOS_BREAK_PMM`: admission drops the type filter and reserved-range exclusion | halts at `PMM_RESERVED_VIOLATED`; 10 unmet |

### One of these controls was vacuous at first — worth knowing why

The `pmm` control originally disabled *only* the reserved-range exclusion. It
produced **byte-identical output to a correct build**: `AIUEOS_PMM_RESERVED_OK`
still passed, so it proved nothing.

The reason is that under AAVMF every reserved range (kernel window, boot-info
page, memory map) is `EfiLoaderData`, never `EfiConventionalMemory` — the type
filter alone already excluded them, making the reserved-range trimming dead
code. The control only became real once it dropped the type filter too.

So: **the reserved-range exclusion is defence-in-depth today, not the
load-bearing check.** It becomes load-bearing when the kernel starts reclaiming
`EfiBootServicesCode`/`Data` after `ExitBootServices`, or if firmware
misreports. Reading the break switch's diff would not have revealed this —
only running it and comparing transcripts did.

## Three findings worth reading before continuing the port

1. **`virtio-vga` does not exist on aarch64.** It is x86-only because it bundles
   VGA compatibility — and it is exactly the device the x86_64 smoke gate uses.
2. **`virtio-gpu-pci` gives Blt-only GOP with no linear aperture**
   (`base=0x0`, `size=0`, `format=3`). The x86_64 desktop-surface bootstrap maps
   a linear aperture, so it does not port to the idiomatic aarch64 device. Only
   `ramfb` exposed a real aperture in the probe.
3. **UEFI is AAPCS64 here, not `ms_abi`.** `EFIAPI` is empty on aarch64; that
   attribute difference touches every protocol function pointer in the loader.

Two smaller ones that cost time: an AArch64 vector slot is exactly 0x80 bytes
(32 instructions), so a register-save sequence inlined into each slot overflows
it — the slots hold a branch and the save lives once. And the page tables are
built under the firmware's mapping but walked under ours, so they are cleaned by
VA (`dc cvac`) before the switch.

## Why the memory-admission judgement is still in C

ADR-2607241100 D6 says C owns mechanism and every judgement is a
compiler-emitted Kotoba object. `page_range_admissible()` **is** a judgement and
belongs in Kotoba. It is not there because it cannot be, on aarch64:

`kotoba.native.elf64/package-kernel-object` emits *"a linkable x86-64 ET_REL
object"* and hard-rejects any target but `:x86_64-aiueos-kernel-v1`. The aarch64
path reaches only `package-kernel-aarch64`, which emits a whole standalone
`ET_EXEC` image, and the compiler assoc's `:binary` for that target with no
`:object`. **There is no aarch64 linkable-object emitter**, so the x86_64
arrangement — a C-mechanism kernel linking `kotoba/kernel-probe.o` — cannot be
reproduced. aarch64 today must pick all-Kotoba-standalone or all-C.

Mitigation: `page_range_admissible()` is written as a pure function of
`(descriptor, reserved ranges) -> admitted sub-range`, touching no global state
and doing no I/O, so it is a mechanical swap once the emitter exists. Keep it
that way — the moment it reads a global or allocates, the swap stops being
mechanical.

(From source inspection of compiler `4c9650ee` and `kotoba-native`, not from
running the compiler: its closure is ~10 kotoba-lang git repos plus maven, and
there is no clojure CLI here.)

## Deliberately not done

No dynamic paging beyond the initial static identity map (the allocator backs
the tables, but nothing maps or unmaps at runtime yet), no GIC, no generic
timer, no scheduler, no ring 3, no userspace. No compositor, no input path, no
virtio-gpu 2D resource path; `ramfb` is probed but not driven. Nothing measured
on macOS or on real Apple Silicon — the entire HVF track is unmeasured. See
`:not-demonstrated` in the evidence EDN.
