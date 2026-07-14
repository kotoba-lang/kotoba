.section .text.entry,"ax",@progbits
.global aiueos_kernel_entry
.type aiueos_kernel_entry,@function
.extern aiueos_kernel_main
.extern aiueos_exception_dispatch

aiueos_kernel_entry:
  cli
  lea aiueos_kernel_stack_top(%rip), %rsp
  and $-16, %rsp
  xor %rbp, %rbp
  call aiueos_kernel_main
1:
  cli
  hlt
  jmp 1b

.global aiueos_load_gdt
.type aiueos_load_gdt,@function
aiueos_load_gdt:
  lgdt aiueos_gdt_pointer(%rip)
  pushq $0x08
  lea 2f(%rip), %rax
  pushq %rax
  lretq
2:
  mov $0x10, %ax
  mov %ax, %ds
  mov %ax, %es
  mov %ax, %ss
  xor %eax, %eax
  mov %ax, %fs
  mov %ax, %gs
  ret

.global aiueos_load_idt
.type aiueos_load_idt,@function
aiueos_load_idt:
  lidt (%rdi)
  ret

.global aiueos_isr_invalid_opcode
.type aiueos_isr_invalid_opcode,@function
aiueos_isr_invalid_opcode:
  cli
  mov $6, %edi
  and $-16, %rsp
  call aiueos_exception_dispatch
3:
  hlt
  jmp 3b

.section .rodata.gdt,"a",@progbits
.balign 8
aiueos_gdt:
  .quad 0x0000000000000000
  .quad 0x00af9a000000ffff
  .quad 0x00cf92000000ffff
aiueos_gdt_end:
aiueos_gdt_pointer:
  .word aiueos_gdt_end - aiueos_gdt - 1
  .quad aiueos_gdt

.section .bss.stack,"aw",@nobits
.balign 4096
.global aiueos_kernel_stack_bottom
aiueos_kernel_stack_bottom:
  .skip 65536
.global aiueos_kernel_stack_top
aiueos_kernel_stack_top:

.section .note.GNU-stack,"",@progbits
