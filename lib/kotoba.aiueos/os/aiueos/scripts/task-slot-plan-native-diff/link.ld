SECTIONS {
  . = 0x100000;
  .text : { *(.text.entry) *(.text*) }
  .rodata : { *(.rodata*) }
  .data : { *(.data*) }
  _edata = .;
  .bss (NOLOAD) : { *(.bss*) *(COMMON) }
  .high_bss (NOLOAD) : { *(.high_bss) }
  _end = .;
  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame) }
}
