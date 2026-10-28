ENTRY(aiueos_kernel_entry)
/* The three KEEPs below are no-ops for every build that does not pass
 * `--gc-sections`, which is every build except the physical-qualification one
 * and the Qwen parity profiles.  They are here because the ring-3 payload and
 * the boot stack are reached through LINKER-SCRIPT symbols and a section
 * attribute, never through a relocation, so the collector takes them and the
 * image still links: measured 2026-09-03, an image built with `--gc-sections`
 * booted as far as `AIUEOS_RING3_FAIL tss-or-mapping`. */
SECTIONS {
  . = 0x100000;
  aiueos_text_start = .;
  .text : ALIGN(4096) { *(.text.entry) *(.text .text.*) }
  aiueos_text_end = ALIGN(4096);
  . = aiueos_text_end;
  aiueos_rodata_start = .;
  .rodata : ALIGN(4096) { *(.rodata .rodata.*) }
  aiueos_rodata_end = ALIGN(4096);
  . = aiueos_rodata_end;
  aiueos_data_start = .;
  .data : ALIGN(4096) { *(.data .data.*) }
  .bss : ALIGN(4096) { *(.bss .bss.*) *(COMMON) }
  aiueos_kernel_bss_end = .;
  /* The kernel image must end below the per-process user image window.  A
   * loaded user ELF is mapped over 0x1e1000.. (text pages 481/482, data page
   * 482 or 496) in its own address space, replacing whatever kernel page sat
   * there; the IDT, TSS, syscall state and kernel stack are reached from ring 3
   * under that CR3.  Measured 2026-10-28: with the 64 KiB stack in .bss the
   * image ran to 0x1ef000, the IDT (0x1e13a0) sat under the ELF data page, the
   * #UD exit of the first ELF process read a zero IDT entry and triple-faulted
   * (smoke never reached AIUEOS_UEFI_SMOKE_OK).  The stack therefore lives in
   * .high_bss and the ring-3 payload is pinned at its historical 0x1f0000. */
  ASSERT(aiueos_kernel_bss_end <= 0x1e1000,
         "kernel data overlaps the per-process user image window")
  . = 0x1f0000;
  aiueos_user_text_start = .;
  .user_text : ALIGN(4096) { KEEP(*(.user.text)) }
  aiueos_user_text_end = ALIGN(4096);
  . = ALIGN(4096);
  aiueos_user_data_start = .;
  .user_data : ALIGN(4096) { KEEP(*(.user.data)) }
  aiueos_user_data_end = ALIGN(4096);
  . += 4096; /* deliberately unmapped guard page */
  aiueos_low_end = ALIGN(4096);
  ASSERT(aiueos_low_end <= 0x1f4000,
         "low kernel/user layout overlaps process-private aperture")

  /* Large kernel-only scratch that need not consume the low 4 KiB W^X map.
   * page_directory[2] maps this 4..6 MiB window writable and NX. */
  . = 0x400000;
  aiueos_high_data_start = .;
  .high_bss (NOLOAD) : ALIGN(4096) { *(.high_bss.stack) *(.high_bss) }
  aiueos_high_data_end = ALIGN(4096);
  . = aiueos_high_data_end;
  aiueos_kernel_end = ALIGN(4096);
  ASSERT(aiueos_kernel_end <= 0x600000,
         "high kernel scratch exceeds its writable-NX huge page")
  /DISCARD/ : { *(.comment) *(.eh_frame) *(.note*) }
}
