/* Boot-info ABI handed from the AArch64 UEFI loader to the AArch64 kernel.
 *
 * Deliberately field-for-field identical to the x86_64 `struct
 * aiueos_boot_info` in os/aiueos/kernel/framebuffer.c. The handoff ABI is one
 * of the genuinely arch-neutral pieces of the port: only the mechanism that
 * fills it in differs between x86_64 and AArch64, not its shape. Keeping it
 * identical is what lets the Kotoba decision objects that consume boot-info
 * stay arch-neutral (ADR-2608080300 track a3).
 */
#ifndef AIUEOS_BOOTINFO_H
#define AIUEOS_BOOTINFO_H

#include <stdint.h>

/* "AIUEOSBI" little-endian. */
#define AIUEOS_BOOT_INFO_MAGIC 0x49424F5345554941ULL
#define AIUEOS_BOOT_INFO_VERSION 1ULL

struct aiueos_boot_info {
  uint64_t magic, version;
  void *memory_map;
  uint64_t memory_map_size, descriptor_size, descriptor_version;
  void *acpi_rsdp;
  uint64_t framebuffer_base, framebuffer_size;
  uint32_t framebuffer_width, framebuffer_height, framebuffer_stride, framebuffer_format;
};

/* Where the loader places the kernel. AArch64 QEMU `virt` puts RAM at
   0x40000000; 32 MiB in is clear of both firmware and the loader itself. The
   kernel is linked at this address and loaded with AllocateAddress, so a
   collision is a loud failure rather than a silent relocation. */
#define AIUEOS_KERNEL_LOAD_BASE 0x42000000ULL

/* QEMU `virt` PL011. AArch64 has no port I/O, so this MMIO window is the
   x86_64 COM1 (0x3f8) equivalent for every evidence marker. */
#define PL011_BASE 0x09000000ULL

#endif
