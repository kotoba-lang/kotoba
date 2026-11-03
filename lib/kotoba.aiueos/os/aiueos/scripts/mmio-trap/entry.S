# Multiboot (a.out kludge) entry for a flat image linked at 0x100000 by link.ld; long mode, then test_main(). The MMIO
# trap harness (JUN-598): as acpi-madt-diff's entry, with the page directory global (trap.c puts a 4 KiB page table under
# the device window) and the two fault stubs trap.c's IDT points at.
.section .text.entry, "ax"
.code32
.globl hdr
hdr:
  .long 0x1BADB002
  .long 0x00010000
  .long -(0x1BADB002 + 0x00010000)
  .long hdr
  .long hdr
  .long _edata
  .long _end
  .long entry
entry:
  cli
  movl $stack_top, %esp
  movl $(pdpt + 3), pml4
  xorl %ecx, %ecx
1: movl %ecx, %eax
  shll $12, %eax
  addl $(pd + 3), %eax
  movl %eax, pdpt(,%ecx,8)
  incl %ecx
  cmpl $4, %ecx
  jb 1b
  xorl %ecx, %ecx
2: movl %ecx, %eax
  shll $21, %eax
  orl $0x83, %eax
  movl %eax, pd(,%ecx,8)
  incl %ecx
  cmpl $2048, %ecx
  jb 2b
  movl $pml4, %eax
  movl %eax, %cr3
  movl %cr4, %eax
  orl $0x620, %eax          # PAE, OSFXSR, OSXMMEXCPT
  movl %eax, %cr4
  movl $0xC0000080, %ecx
  rdmsr
  orl $0x100, %eax
  wrmsr
  movl %cr0, %eax
  andl $0xFFFFFFFB, %eax    # clear EM
  orl $0x80000003, %eax     # PG, PE, MP
  movl %eax, %cr0
  lgdt gdtr
  ljmp $0x08, $long
.code64
long:
  movw $0x10, %ax
  movw %ax, %ds
  movw %ax, %es
  movw %ax, %ss
  movq $stack_top, %rsp
  call test_main
  movw $0xf4, %dx
  xorl %eax, %eax
  outl %eax, %dx
3: hlt
  jmp 3b

# #DB (vector 1) and #PF (vector 14): save the general registers, hand trap.c the frame, restore. #PF's error code is
# dropped before iretq. The frame trap.c sees: r15 .. rax (15 words), [error code], rip, cs, rflags, rsp, ss.
.macro PUSHALL
  pushq %rax; pushq %rbx; pushq %rcx; pushq %rdx; pushq %rsi; pushq %rdi; pushq %rbp
  pushq %r8; pushq %r9; pushq %r10; pushq %r11; pushq %r12; pushq %r13; pushq %r14; pushq %r15
.endm
.macro POPALL
  popq %r15; popq %r14; popq %r13; popq %r12; popq %r11; popq %r10; popq %r9; popq %r8
  popq %rbp; popq %rdi; popq %rsi; popq %rdx; popq %rcx; popq %rbx; popq %rax
.endm
.globl isr_db
isr_db:
  PUSHALL
  movq %rsp, %rdi
  cld
  call trap_db
  POPALL
  iretq
.globl isr_pf
isr_pf:
  PUSHALL
  movq %rsp, %rdi
  cld
  call trap_pf
  POPALL
  addq $8, %rsp
  iretq
.balign 16
gdt:
  .quad 0
  .quad 0x00AF9A000000FFFF
  .quad 0x00CF92000000FFFF
gdtr:
  .word 23
  .long gdt
.section .bss.boot, "aw", @nobits
.balign 4096
pml4: .skip 4096
pdpt: .skip 4096
.globl pd
pd: .skip 16384
.balign 16
.skip 262144
stack_top:
