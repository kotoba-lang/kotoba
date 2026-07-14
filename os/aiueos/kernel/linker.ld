ENTRY(aiueos_kernel_entry)
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
  .bss : ALIGN(4096) { *(.bss.stack) *(.bss .bss.*) *(COMMON) }
  aiueos_kernel_end = ALIGN(4096);
  /DISCARD/ : { *(.comment) *(.eh_frame) *(.note*) }
}
