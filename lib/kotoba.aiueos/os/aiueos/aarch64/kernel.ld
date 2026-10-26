/* AArch64 kernel link map.
 *
 * Sections are 4 KiB aligned so the page tables can give each one distinct
 * permissions — that separation is what makes the W^X proof meaningful. The
 * x86_64 kernel does the same thing (text RX, rodata R+NX, writable RW+NX).
 */
ENTRY(_start)

SECTIONS
{
  . = 0x42000000;

  __text_start = .;
  .text : {
    *(.text.entry)
    *(.text*)
  }
  . = ALIGN(4096);
  __text_end = .;

  __rodata_start = .;
  .rodata : { *(.rodata*) }
  . = ALIGN(4096);
  __rodata_end = .;

  __data_start = .;
  .data : { *(.data*) }
  . = ALIGN(4096);

  __bss_start = .;
  .bss : {
    *(.bss*)
    *(COMMON)
    . = ALIGN(16);
    __stack_bottom = .;
    . += 0x10000;          /* 64 KiB private stack */
    __stack_top = .;
  }
  . = ALIGN(4096);
  __bss_end = .;

  __end = .;

  /DISCARD/ : { *(.comment) *(.note*) *(.eh_frame*) }
}
