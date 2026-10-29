# x86_64 bare-metal smoke harness for kotoba/apic.o (JUN-556). Multiboot a.out-kludge image loaded at 0x100000.
.set BASE, 0x100000
.text
.code32
hdr:
  .long 0x1BADB002
  .long 0x00010000
  .long -(0x1BADB002 + 0x00010000)
  .long BASE
  .long BASE
  .long BASE + image_end - hdr
  .long BASE + image_end - hdr
  .long BASE + entry - hdr
entry:
  cli
  movl $(BASE + stack_top - hdr), %esp
  # PML4[0] -> PDPT, PDPT[0..3] -> PD0..3, PD entries = 2 MiB identity pages
  movl $(BASE + pdpt - hdr + 3), (BASE + pml4 - hdr)
  xorl %ecx, %ecx
1: movl %ecx, %eax
  shll $12, %eax
  addl $(BASE + pd - hdr + 3), %eax
  movl %eax, (BASE + pdpt - hdr)(,%ecx,8)
  incl %ecx
  cmpl $4, %ecx
  jb 1b
  xorl %ecx, %ecx
2: movl %ecx, %eax
  shll $21, %eax
  orl $0x83, %eax
  movl %eax, (BASE + pd - hdr)(,%ecx,8)
  incl %ecx
  cmpl $2048, %ecx
  jb 2b
  movl $(BASE + pml4 - hdr), %eax
  movl %eax, %cr3
  movl %cr4, %eax
  orl $0x20, %eax
  movl %eax, %cr4
  movl $0xC0000080, %ecx
  rdmsr
  orl $0x100, %eax
  wrmsr
  movl %cr0, %eax
  orl $0x80000001, %eax
  movl %eax, %cr0
  lgdt (BASE + gdtr - hdr)
  ljmp $0x08, $(BASE + long - hdr)
.code64
long:
  movw $0x10, %ax
  movw %ax, %ds
  movw %ax, %es
  movw %ax, %ss
  movq $(BASE + stack_top - hdr), %rsp
  leaq banner(%rip), %rsi
  call puts
  leaq vectors(%rip), %r12
  movq (%r12), %r13          # count
  addq $8, %r12
  xorl %r14d, %r14d          # index
1: cmpq %r13, %r14
  jae 9f
  # fill poll with 0xaa
  leaq pollbuf(%rip), %rdi
  movl $40, %ecx
  movb $0xaa, %al
  rep stosb
  movq (%r12), %rsi          # length
  leaq 8(%r12), %rdi         # http
  leaq pollbuf(%rip), %rdx
  movq %rsi, %r15
  call obj_text + FUNC_OFF
  movq %rax, %rbx
  leaq s_v(%rip), %rsi
  call puts
  movl %r14d, %edi
  call puthex32
  leaq s_ret(%rip), %rsi
  call puts
  movq %rbx, %rdi
  call puthex64
  leaq s_poll(%rip), %rsi
  call puts
  xorl %ebp, %ebp
2: leaq pollbuf(%rip), %rax
  movzbl (%rax,%rbp), %edi
  call puthex8
  incl %ebp
  cmpl $40, %ebp
  jb 2b
  movb $10, %al
  call putc
  # next vector: 8 + align8(length)
  leaq 15(%r15), %rax
  andq $-8, %rax
  addq %rax, %r12
  incq %r14
  jmp 1b
9: leaq s_done(%rip), %rsi
  call puts
  movw $0xf4, %dx
  xorl %eax, %eax
  outl %eax, %dx
4: hlt
  jmp 4b
putc:
  movw $0xe9, %dx
  outb %al, %dx
  ret
puts:
  lodsb
  testb %al, %al
  jz 5f
  call putc
  jmp puts
5: ret
puthex8:
  movl %edi, %eax
  shrl $4, %eax
  andl $0xf, %eax
  cmpl $10, %eax
  jb 6f
  addl $7, %eax
6: addl $0x30, %eax
  call putc
  movl %edi, %eax
  andl $0xf, %eax
  cmpl $10, %eax
  jb 7f
  addl $7, %eax
7: addl $0x30, %eax
  call putc
  ret
puthex32:
  movl $8, %ecx
6: roll $4, %edi
  movl %edi, %eax
  andl $0xf, %eax
  cmpl $10, %eax
  jb 7f
  addl $7, %eax
7: addl $0x30, %eax
  call putc
  loop 6b
  ret
puthex64:
  pushq %rdi
  shrq $32, %rdi
  call puthex32
  popq %rdi
  call puthex32
  ret
memset:
  movq %rdi, %r8
  movl %esi, %eax
  movq %rdx, %rcx
  rep stosb
  movq %r8, %rax
  ret
banner: .asciz "DWP-SMOKE\n"
s_v: .asciz "v"
s_ret: .asciz " ret="
s_poll: .asciz " poll="
s_done: .asciz "DONE\n"
.balign 16
gdt:
  .quad 0
  .quad 0x00AF9A000000FFFF
  .quad 0x00CF92000000FFFF
gdtr:
  .word 23
  .long BASE + gdt - hdr
.balign 16
obj_text:
  .incbin "objs.text"
.balign 16
obj_data:
  .incbin "objs.data"
.balign 16
vectors:
  .incbin "vectors.bin"
.balign 16
pollbuf: .fill 64, 1, 0
.balign 4096
pml4:
.fill 4096, 1, 0
pdpt:
.fill 4096, 1, 0
pd:
.fill 16384, 1, 0
idt: .fill 4096, 1, 0
.fill 8192, 1, 0
stack_top:
image_end:
