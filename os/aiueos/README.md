# aiueos bare-metal integration

This directory contains the Linux-independent aiueos boot path owned by the
Kotoba product integration repository.

The current Phase 1 slice builds a PE32+ `BOOTX64.EFI` and a separate ELF64
`KERNEL.ELF`. OVMF starts the loader, which validates and places bounded ELF
segments, captures the firmware memory map, exits UEFI boot services, and
hands control to the kernel. The kernel validates the handoff and terminates
QEMU through the test-only debug-exit device. It does not use Linux, a JVM,
GRUB, or a host initramfs in the guest.

```sh
./os/aiueos/scripts/build-uefi.sh
./os/aiueos/scripts/smoke-qemu-uefi.sh
```

Requirements are Zig 0.14 or newer and `qemu-system-x86_64` with an edk2/OVMF
firmware image. Override firmware discovery with `OVMF_CODE=/path/to/code.fd`.

The EFI application is deliberately a small native bootstrap substrate. Kotoba
programs use the freestanding target contract in `kotoba-lang/compiler`; moving
the remaining bootstrap into compiler-emitted PE/COFF is tracked by the ADR.
