/* AArch64 kernel entry + exception vectors.
 *
 * The x86_64 counterpart is os/aiueos/kernel/entry.S, which switches to a
 * private stack before entering C and installs a GDT/IDT. AArch64 needs no
 * GDT and no segment model at all; the equivalent work is a private stack, a
 * 2 KiB-aligned VBAR_EL1 vector table, and (in C) TTBR0_EL1 + MAIR + TCR.
 *
 * Each vector slot is exactly 0x80 bytes (32 instructions), so the slots hold
 * only a branch — the register save lives once in aiueos_exception_entry.
 * Inlining the save into every slot overflows the slot.
 */

  .section .text.entry, "ax"
  .global _start
  .type _start, %function
_start:
  /* UEFI hands the boot-info pointer in x0; preserve it across setup. */
  mov   x19, x0

  /* Private 64 KiB stack, matching the x86_64 loader's private-stack step. */
  adrp  x1, __stack_top
  add   x1, x1, :lo12:__stack_top
  mov   sp, x1

  /* Zero .bss before any C runs. */
  adrp  x1, __bss_start
  add   x1, x1, :lo12:__bss_start
  adrp  x2, __bss_end
  add   x2, x2, :lo12:__bss_end
1:
  cmp   x1, x2
  b.hs  2f
  str   xzr, [x1], #8
  b     1b
2:

  /* Install the exception vector table. */
  adrp  x1, aiueos_vectors
  add   x1, x1, :lo12:aiueos_vectors
  msr   vbar_el1, x1
  isb

  mov   x0, x19
  bl    kernel_main

3:
  wfi
  b     3b
  .size _start, . - _start

/* ---------------------------------------------------------------------------
 * Shared exception entry: save the caller-clobberable GPRs, call into C, and
 * eret. The C handler adjusts ELR_EL1 to the probe's recovery label, so a
 * deliberate W^X violation resumes instead of looping on the faulting
 * instruction.
 */
  .section .text, "ax"
  .global aiueos_exception_entry
  .type aiueos_exception_entry, %function
aiueos_exception_entry:
  sub   sp, sp, #(20 * 16)
  stp   x0,  x1,  [sp, #(0 * 16)]
  stp   x2,  x3,  [sp, #(1 * 16)]
  stp   x4,  x5,  [sp, #(2 * 16)]
  stp   x6,  x7,  [sp, #(3 * 16)]
  stp   x8,  x9,  [sp, #(4 * 16)]
  stp   x10, x11, [sp, #(5 * 16)]
  stp   x12, x13, [sp, #(6 * 16)]
  stp   x14, x15, [sp, #(7 * 16)]
  stp   x16, x17, [sp, #(8 * 16)]
  stp   x18, x30, [sp, #(9 * 16)]
  bl    aiueos_exception
  ldp   x0,  x1,  [sp, #(0 * 16)]
  ldp   x2,  x3,  [sp, #(1 * 16)]
  ldp   x4,  x5,  [sp, #(2 * 16)]
  ldp   x6,  x7,  [sp, #(3 * 16)]
  ldp   x8,  x9,  [sp, #(4 * 16)]
  ldp   x10, x11, [sp, #(5 * 16)]
  ldp   x12, x13, [sp, #(6 * 16)]
  ldp   x14, x15, [sp, #(7 * 16)]
  ldp   x16, x17, [sp, #(8 * 16)]
  ldp   x18, x30, [sp, #(9 * 16)]
  add   sp, sp, #(20 * 16)
  eret
  .size aiueos_exception_entry, . - aiueos_exception_entry

/* 16 entries x 0x80 bytes, table 2 KiB aligned. We execute at EL1 on SP_EL1,
 * so synchronous faults land in the "Current EL with SPx" quadrant (0x200). */
  .align 11
  .global aiueos_vectors
aiueos_vectors:
  /* Current EL with SP0 */
  .align 7
  b aiueos_exception_entry      /* sync  */
  .align 7
  b aiueos_exception_entry      /* irq   */
  .align 7
  b aiueos_exception_entry      /* fiq   */
  .align 7
  b aiueos_exception_entry      /* serr  */

  /* Current EL with SPx — the quadrant our faults use. */
  .align 7
  b aiueos_exception_entry      /* sync  */
  .align 7
  b aiueos_exception_entry      /* irq   */
  .align 7
  b aiueos_exception_entry      /* fiq   */
  .align 7
  b aiueos_exception_entry      /* serr  */

  /* Lower EL, AArch64 */
  .align 7
  b aiueos_exception_entry
  .align 7
  b aiueos_exception_entry
  .align 7
  b aiueos_exception_entry
  .align 7
  b aiueos_exception_entry

  /* Lower EL, AArch32 */
  .align 7
  b aiueos_exception_entry
  .align 7
  b aiueos_exception_entry
  .align 7
  b aiueos_exception_entry
  .align 7
  b aiueos_exception_entry
