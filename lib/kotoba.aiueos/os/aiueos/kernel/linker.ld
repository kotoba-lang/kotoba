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
  .bss : ALIGN(4096) { KEEP(*(.bss.stack)) *(.bss .bss.*) *(COMMON) }
  . = ALIGN(4096);
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
  .high_bss (NOLOAD) : ALIGN(4096) { *(.high_bss) }
  aiueos_high_data_end = ALIGN(4096);
  . = aiueos_high_data_end;
  aiueos_kernel_end = ALIGN(4096);
  ASSERT(aiueos_kernel_end <= 0x600000,
         "high kernel scratch exceeds its writable-NX huge page")
  /DISCARD/ : { *(.comment) *(.eh_frame) *(.note*) }
}
