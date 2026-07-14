.section .text.entry,"ax",@progbits
.global aiueos_kernel_entry
.type aiueos_kernel_entry,@function
.extern aiueos_kernel_main

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

.section .bss.stack,"aw",@nobits
.balign 4096
.global aiueos_kernel_stack_bottom
aiueos_kernel_stack_bottom:
  .skip 65536
.global aiueos_kernel_stack_top
aiueos_kernel_stack_top:

.section .note.GNU-stack,"",@progbits

