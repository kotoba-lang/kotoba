.section .text.entry,"ax",@progbits
.global aiueos_kernel_entry
.type aiueos_kernel_entry,@function
.extern aiueos_kernel_main
.extern aiueos_exception_dispatch
.extern aiueos_scheduler_on_timer

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

.global aiueos_isr_apic_timer
.type aiueos_isr_apic_timer,@function
aiueos_isr_apic_timer:
  push %rax
  push %rbx
  push %rcx
  push %rdx
  push %rsi
  push %rdi
  push %rbp
  push %r8
  push %r9
  push %r10
  push %r11
  push %r12
  push %r13
  push %r14
  push %r15
  incq aiueos_apic_timer_ticks(%rip)
  mov aiueos_apic_mmio_base(%rip), %rax
  movl $0, 0xb0(%rax)
  mov %rsp, %rdi
  and $-16, %rsp
  call aiueos_scheduler_on_timer
  mov %rax, %rsp
  pop %r15
  pop %r14
  pop %r13
  pop %r12
  pop %r11
  pop %r10
  pop %r9
  pop %r8
  pop %rbp
  pop %rdi
  pop %rsi
  pop %rdx
  pop %rcx
  pop %rbx
  pop %rax
  iretq

.global aiueos_page_fault_stage
.global aiueos_page_fault_error
.global aiueos_isr_page_fault
.type aiueos_isr_page_fault,@function
aiueos_isr_page_fault:
  cli
  push %rax
  mov 8(%rsp), %rax
  mov %rax, aiueos_page_fault_error(%rip)
  mov aiueos_page_fault_stage(%rip), %rax
  cmp $1, %rax
  je 4f
  cmp $2, %rax
  je 5f
  mov $0xffff, %rax
  mov %rax, aiueos_page_fault_stage(%rip)
  jmp 6f
4:
  lea aiueos_wp_probe_resume(%rip), %rax
  mov %rax, 16(%rsp)
  mov $0x101, %rax
  mov %rax, aiueos_page_fault_stage(%rip)
  jmp 7f
5:
  lea aiueos_nx_probe_resume(%rip), %rax
  mov %rax, 16(%rsp)
  mov $0x102, %rax
  mov %rax, aiueos_page_fault_stage(%rip)
7:
  pop %rax
  add $8, %rsp
  iretq
6:
  pop %rax
  mov $0x7b, %eax
  outl %eax, $0xf4
  jmp 3b

.global aiueos_probe_write_protect
.type aiueos_probe_write_protect,@function
aiueos_probe_write_protect:
  movb $0, aiueos_text_start(%rip)
.global aiueos_wp_probe_resume
aiueos_wp_probe_resume:
  ret

.global aiueos_probe_no_execute
.type aiueos_probe_no_execute,@function
aiueos_probe_no_execute:
  lea aiueos_nx_probe_target(%rip), %rax
  jmp *%rax
.global aiueos_nx_probe_resume
aiueos_nx_probe_resume:
  ret

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

.section .rodata.nx-probe,"a",@progbits
.global aiueos_nx_probe_target
aiueos_nx_probe_target:
  .byte 0xc3

.section .bss.stack,"aw",@nobits
.balign 4096
.global aiueos_kernel_stack_bottom
aiueos_kernel_stack_bottom:
  .skip 65536
.global aiueos_kernel_stack_top
aiueos_kernel_stack_top:

.section .note.GNU-stack,"",@progbits
