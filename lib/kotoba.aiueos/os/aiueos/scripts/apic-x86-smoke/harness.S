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
  movl $0xfee00000, %r8d
  leaq banner(%rip), %rsi
  call puts
  call obj_text + OBJ_INIT
  movl %eax, %edi
  leaq s_init(%rip), %rsi
  call puts
  call puthex32
  leaq s_lvt(%rip), %rsi
  call puts
  movl 0x320(%r8), %edi
  call puthex32
  leaq s_svr(%rip), %rsi
  call puts
  movl 0x0f0(%r8), %edi
  call puthex32
  leaq s_base(%rip), %rsi
  call puts
  movq obj_data + MMIO_BASE(%rip), %rdi
  call puthex64
  leaq s_ticks(%rip), %rsi
  call puts
  movq obj_data + TICKS(%rip), %rdi
  call puthex64
  call obj_text + OBJ_MASK
  leaq s_masked(%rip), %rsi
  call puts
  movl 0x320(%r8), %edi
  call puthex32
  call obj_text + OBJ_UNMASK
  leaq s_unmasked(%rip), %rsi
  call puts
  movl 0x320(%r8), %edi
  call puthex32
  leaq s_cnt1(%rip), %rsi
  call puts
  movl 0x390(%r8), %edi
  call puthex32
  movl $2000000, %ecx
3: pause
  loop 3b
  leaq s_cnt2(%rip), %rsi
  call puts
  movl 0x390(%r8), %edi
  call puthex32
  # deliver the timer: IDT vector 32 -> handler that mirrors entry.S (incq ticks; EOI via mmio_base)
  leaq irq(%rip), %rax
  leaq idt+512(%rip), %rdi
  movw %ax, (%rdi)
  movw $0x08, 2(%rdi)
  movw $0x8E00, 4(%rdi)
  shrq $16, %rax
  movw %ax, 6(%rdi)
  shrq $16, %rax
  movl %eax, 8(%rdi)
  movb $0xff, %al
  outb %al, $0x21
  outb %al, $0xa1
  lidt idtr(%rip)
  sti
  movl $400000000, %ecx
8: cmpq $3, obj_data + TICKS(%rip)
  jae 9f
  pause
  loop 8b
9: cli
  leaq s_irq(%rip), %rsi
  call puts
  xorl %edi, %edi
  cmpq $3, obj_data + TICKS(%rip)
  setae %dil
  call puthex32
  leaq s_done(%rip), %rsi
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
banner: .asciz "APIC-SMOKE\n"
s_init: .asciz "init-ret="
s_lvt: .asciz "\nlvt-after-init="
s_svr: .asciz "\nsvr-after-init="
s_base: .asciz "\nmmio_base-cell="
s_ticks: .asciz "\nticks-cell="
s_masked: .asciz "\nlvt-after-mask="
s_unmasked: .asciz "\nlvt-after-unmask="
s_cnt1: .asciz "\ncur-count-1="
s_cnt2: .asciz "\ncur-count-2="
s_irq: .asciz "\nirq-ticks-ge3="
s_done: .asciz "\nDONE\n"
.balign 16
msr_read:
  movl %edi, %ecx
  rdmsr
  shlq $32, %rdx
  orq %rdx, %rax
  ret
msr_write:
  movl %edi, %ecx
  movq %rsi, %rax
  movq %rsi, %rdx
  shrq $32, %rdx
  wrmsr
  movl $1, %eax
  ret
.balign 16
irq:
  pushq %rax
  incq obj_data + TICKS(%rip)
  movq obj_data + MMIO_BASE(%rip), %rax
  movl $0, 0xb0(%rax)
  popq %rax
  iretq
.balign 16
idtr:
  .word 4095
  .quad BASE + idt - hdr
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
  .incbin "apic.text"
.balign 16
obj_data:
  .incbin "apic.data"
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
