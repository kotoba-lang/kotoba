ENTRY(aiueos_kernel_entry)
SECTIONS {
  . = 0x100000;
  .text : ALIGN(4096) { *(.text.entry) *(.text .text.*) }
  .rodata : ALIGN(4096) { *(.rodata .rodata.*) }
  .data : ALIGN(4096) { *(.data .data.*) }
  .bss : ALIGN(4096) { *(.bss.stack) *(.bss .bss.*) *(COMMON) }
  /DISCARD/ : { *(.comment) *(.eh_frame) *(.note*) }
}
