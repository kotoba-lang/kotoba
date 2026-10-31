# The #UD guard (see guard.h). guarded_call saves the callee-saved registers and the stack pointer, then calls FN with
# up to five arguments; isr_ud rewrites the trap frame to resume at `recover` on the saved stack, and recover returns 0.
.text
.globl guarded_call
guarded_call:
  pushq %rbx; pushq %rbp; pushq %r12; pushq %r13; pushq %r14; pushq %r15
  subq $8, %rsp
  movq %rsp, guard_rsp(%rip)
  movq $0, guard_trapped(%rip)
  movq %rdi, %rax
  movq %rsi, %rdi; movq %rdx, %rsi; movq %rcx, %rdx; movq %r8, %rcx; movq %r9, %r8
  call *%rax
resume:
  addq $8, %rsp
  popq %r15; popq %r14; popq %r13; popq %r12; popq %rbp; popq %rbx
  ret
recover:
  movq guard_rsp(%rip), %rsp
  movq $1, guard_trapped(%rip)
  xorl %eax, %eax
  jmp resume
.globl isr_ud
isr_ud:
  leaq recover(%rip), %rax
  movq %rax, (%rsp)            # rip
  movq guard_rsp(%rip), %rax
  movq %rax, 24(%rsp)          # rsp
  iretq
.globl guard_init
guard_init:
  leaq isr_ud(%rip), %rax
  leaq guard_idt+96(%rip), %rcx  # vector 6
  movw %ax, (%rcx)
  movw $0x08, 2(%rcx)
  movw $0x8e00, 4(%rcx)
  shrq $16, %rax
  movw %ax, 6(%rcx)
  shrq $16, %rax
  movl %eax, 8(%rcx)
  movl $0, 12(%rcx)
  leaq guard_idt(%rip), %rax
  movq %rax, guard_idtr+2(%rip)
  lidt guard_idtr(%rip)
  ret
.data
.balign 16
guard_idtr: .word 32 * 16 - 1
  .quad 0
.globl guard_trapped
.balign 8
guard_trapped: .quad 0
guard_rsp: .quad 0
.bss
.balign 16
guard_idt: .skip 32 * 16
