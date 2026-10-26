/* Multiboot kernel image. Loaded by a Multiboot loader at 1 MiB; the multiboot
 * header must appear within the first 8 KiB of the file, so .text.mbentry is
 * placed first. */
ENTRY(aiueos_multiboot_start)
SECTIONS {
  . = 0x100000;
  .text : ALIGN(4096) { *(.text.mbentry) *(.text .text.*) }
  .rodata : ALIGN(4096) { *(.rodata .rodata.*) }
  .data : ALIGN(4096) { *(.data .data.*) }
  .bss : ALIGN(4096) { *(.bss.mb) *(.bss .bss.*) *(COMMON) }
  /DISCARD/ : { *(.comment) *(.eh_frame) *(.note*) }
}
