# aiueos bare-metal integration

This directory contains the Linux-independent aiueos boot path owned by the
Kotoba product integration repository.

The current Phase 1 slice builds a PE32+ `BOOTX64.EFI` and a separate ELF64
`KERNEL.ELF`. OVMF starts the loader, which validates and places bounded ELF
segments, captures the firmware memory map, exits UEFI boot services, and
hands control to the kernel. The kernel validates the handoff and terminates
QEMU through the test-only debug-exit device. Its assembly entry switches to a
private 64 KiB stack before entering C, and its first hardware driver
initializes COM1 at 115200 baud. The kernel then installs its own GDT and IDT;
the smoke gate executes `ud2` and requires the vector 6 handler to terminate
QEMU. Before that test the kernel replaces the firmware CR3 with its own
four-level identity map, enables write-protect and NX, and maps text RX,
rodata R+NX, and writable state RW+NX. It does not use Linux, a JVM, GRUB, or a
host initramfs in the guest. The smoke test writes to text and attempts to
execute a byte in rodata; both must raise vector 14 with the expected x86 page
fault error-code bits before execution can continue.

The loader also selects the ACPI 2.0 configuration-table GUID. The kernel
validates both RSDP checksums, the XSDT and MADT checksums and lengths, and every
MADT subtable boundary. The QEMU gate starts two vCPUs and requires both to be
reported as enabled by MADT. The BSP then copies a real-mode trampoline below
1 MiB, sends INIT plus two SIPIs to the second MADT APIC ID, and requires the AP
to enter long mode on its own 64 KiB stack before the boot smoke may pass.

The BSP enables its Local APIC, maps the MMIO page cache-disabled, installs a
periodic timer on vector 32, enters `sti; hlt`, and requires the interrupt stub
to acknowledge EOI before the smoke test can continue.

The timer stub also preserves the complete x86-64 integer interrupt frame and
passes its stack pointer to a minimal round-robin scheduler. Two kernel tasks
run on separate 16 KiB stacks alongside the boot task. The QEMU gate proceeds
only after all three contexts have been preempted and both worker tasks have
resumed at least twice, producing `AIUEOS_SCHEDULER_OK`. This is kernel-task
context-switch groundwork; user address spaces and ring 3 isolation remain a
later phase.

The Phase 3 bootstrap installs an `int 0x80` syscall gate that preserves the
same integer context and returns through `iretq`. A tagged, generation-bearing
capability handle is required by the log-write admission path. The QEMU gate
proves that a stale generation, a non-canonical pointer, and a range crossing
the bootstrap mapping are denied before dereference. The process foundation reserves distinct U/S pages
for RX user text and RW+NX user data, leaves an unmapped guard page, and builds
a loaded 64-bit TSS descriptor with a dedicated kernel-entry stack. A one-shot
CPL3 task enters through `iretq`, exercises valid and rejected `int 0x80`
requests, and exits back to the kernel through the TSS `rsp0` path. Per-process
CR3 ownership, actual copy-in, and the `syscall`/`sysret` transport remain later
work.

The PCI path performs a bounded configuration-space scan and validates modern
virtio vendor capabilities, including a cycle-limited capability chain, BAR
kind and width, and overflow-safe capability ranges. PCI MMIO is identity
mapped UC/NX only after validation, including QEMU's 64-bit MMIO window above
512 GiB. The virtio-rng smoke path negotiates `VIRTIO_F_VERSION_1`, allocates
separate zeroed pages for the descriptor, available ring, used ring, and data
buffer, submits one writable 32-byte request, and requires the device's used
ring completion. The same bounded capability parser also drives a modern-only
virtio-blk device. It reads the generation-stable capacity, rejects an empty or
overflowing device, submits a three-descriptor `VIRTIO_BLK_T_IN` chain, and
requires a 513-byte used completion, success status, and deterministic sector-0
identity. The smoke disk is a separate read-only 1 MiB fixture, so neither the
ESP nor a release image can be modified by this gate. These are polling
split-virtqueue vertical slices; MSI-X,
IOMMU isolation, indirect descriptors, and a reusable multi-request transport
remain later Phase 4 work.

```sh
./os/aiueos/scripts/build-uefi.sh
./os/aiueos/scripts/smoke-qemu-uefi.sh
./os/aiueos/scripts/build-release-image.sh
./os/aiueos/scripts/smoke-qemu-release-image.sh
```

The release-image command creates a deterministic 64 MiB GPT raw disk image
with a protective MBR and a FAT32 EFI System Partition. The ESP contains
`EFI/BOOT/BOOTX64.EFI` and `EFI/AIUEOS/KERNEL.ELF`. It also emits a canonical
JSON build receipt with the SHA-256 digest and byte size of the disk and both
boot artifacts. Set `SOURCE_DATE_EPOCH` to record a release timestamp without
making the disk image host-time-dependent. The image builder uses only Python's
standard library; validation checks both GPT CRCs, the ESP layout, FAT chains,
boot-image magic, and byte-for-byte embedded artifact contents.

Requirements are Zig 0.14 or newer and `qemu-system-x86_64` with an edk2/OVMF
firmware image. Override firmware discovery with `OVMF_CODE=/path/to/code.fd`.

The EFI application is deliberately a small native bootstrap substrate. Kotoba
programs use the freestanding target contract in `kotoba-lang/compiler`; moving
the remaining bootstrap into compiler-emitted PE/COFF is tracked by the ADR.
