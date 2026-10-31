# Multiboot (a.out kludge) entry for a flat image linked at 0x100000 by link.ld; long mode, then test_main().
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
pd: .skip 16384
.balign 16
.skip 262144
stack_top:
