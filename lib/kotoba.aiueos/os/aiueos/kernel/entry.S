.section .text.entry,"ax",@progbits
.global aiueos_kernel_entry
.type aiueos_kernel_entry,@function
.extern aiueos_kernel_main
.extern aiueos_exception_dispatch
.extern aiueos_scheduler_on_timer
.extern aiueos_syscall_dispatch
.global aiueos_syscall_from_user
.global aiueos_saved_kernel_rsp
.global aiueos_syscall_entry
.global aiueos_sysret_count
.global aiueos_sysret_validation_count

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
  pushq $0
  pushq $6
  jmp aiueos_fatal_common

/* Every CPU exception this kernel does not otherwise service ends here
   (ADR-0199).  Mechanism only: it hands the frame the CPU pushed to the C
   reporter, which renders one line and terminates the machine through
   isa-debug-exit.  The old shape -- `hlt; jmp .` -- is what made a dead guest
   indistinguishable from a QEMU flake: the process kept running and the
   harness could only time out.

   The frame this expects, built by the stubs below:
     0(%rsp) vector   8(%rsp) error code (0 when the CPU pushes none)
    16(%rsp) RIP     24(%rsp) CS        32(%rsp) RFLAGS
    40(%rsp) RSP     48(%rsp) SS
   %rsp is realigned only AFTER the reads, so the offsets stay literal. */
.global aiueos_fatal_common
.type aiueos_fatal_common,@function
aiueos_fatal_common:
  mov 0(%rsp), %rdi
  mov 8(%rsp), %rsi
  mov 16(%rsp), %rdx
  mov 40(%rsp), %rcx
  mov %cr2, %r8
  mov 32(%rsp), %r9
  and $-16, %rsp
  call aiueos_exception_dispatch
3:
  cli
  hlt
  jmp 3b

/* Two stub shapes because the CPU pushes an error code for ten of the
   thirty-two vectors and not for the rest.  Pushing a zero in the no-error
   case keeps ONE frame layout, so the common path above has no branch and
   cannot read the RIP from the wrong slot -- a mistake that would print a
   plausible address for the wrong instruction. */
.macro AIUEOS_FATAL_NOERR vector
.global aiueos_isr_fatal_\vector
.type aiueos_isr_fatal_\vector,@function
aiueos_isr_fatal_\vector:
  cli
  pushq $0
  pushq $\vector
  jmp aiueos_fatal_common
.endm

.macro AIUEOS_FATAL_ERR vector
.global aiueos_isr_fatal_\vector
.type aiueos_isr_fatal_\vector,@function
aiueos_isr_fatal_\vector:
  cli
  pushq $\vector
  jmp aiueos_fatal_common
.endm

AIUEOS_FATAL_NOERR 0
AIUEOS_FATAL_NOERR 1
AIUEOS_FATAL_NOERR 2
AIUEOS_FATAL_NOERR 3
AIUEOS_FATAL_NOERR 4
AIUEOS_FATAL_NOERR 5
AIUEOS_FATAL_NOERR 7
AIUEOS_FATAL_ERR   8
AIUEOS_FATAL_NOERR 9
AIUEOS_FATAL_ERR   10
AIUEOS_FATAL_ERR   11
AIUEOS_FATAL_ERR   12
AIUEOS_FATAL_ERR   13
AIUEOS_FATAL_NOERR 15
AIUEOS_FATAL_NOERR 16
AIUEOS_FATAL_ERR   17
AIUEOS_FATAL_NOERR 18
AIUEOS_FATAL_NOERR 19
AIUEOS_FATAL_NOERR 20
AIUEOS_FATAL_ERR   21
AIUEOS_FATAL_NOERR 22
AIUEOS_FATAL_NOERR 23
AIUEOS_FATAL_NOERR 24
AIUEOS_FATAL_NOERR 25
AIUEOS_FATAL_NOERR 26
AIUEOS_FATAL_NOERR 27
AIUEOS_FATAL_NOERR 28
AIUEOS_FATAL_ERR   29
AIUEOS_FATAL_ERR   30
AIUEOS_FATAL_NOERR 31

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

.global aiueos_isr_external_timer
.type aiueos_isr_external_timer,@function
aiueos_isr_external_timer:
  push %rax
  incq aiueos_external_timer_ticks(%rip)
  mov aiueos_apic_mmio_base(%rip), %rax
  movl $0, 0xb0(%rax)
  pop %rax
  iretq

.global aiueos_isr_virtio_rng
.type aiueos_isr_virtio_rng,@function
aiueos_isr_virtio_rng:
  push %rax
  incq aiueos_virtio_rng_irq_count(%rip)
  mov aiueos_apic_mmio_base(%rip), %rax
  movl $0, 0xb0(%rax)
  pop %rax
  iretq

.global aiueos_isr_virtio_blk
.type aiueos_isr_virtio_blk,@function
aiueos_isr_virtio_blk:
  push %rax
  incq aiueos_virtio_blk_irq_count(%rip)
  mov aiueos_apic_mmio_base(%rip), %rax
  movl $0, 0xb0(%rax)
  pop %rax
  iretq

/* CPL0 bootstrap syscall gate; user-mode isolation is not claimed yet. */
.global aiueos_isr_syscall
.type aiueos_isr_syscall,@function
aiueos_isr_syscall:
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
  mov %rsp, %r12
  mov 128(%r12), %rax
  and $3, %eax
  mov %rax, aiueos_syscall_from_user(%rip)
  mov 112(%r12), %rdi
  mov 72(%r12), %rsi
  mov 80(%r12), %rdx
  mov 88(%r12), %rcx
  and $-16, %rsp
  call aiueos_syscall_dispatch
  mov %rax, 112(%r12)
  cmpq $2, 112(%r12)
  jne 8f
  cmpq $3, aiueos_syscall_from_user(%rip)
  jne 8f
  mov aiueos_saved_kernel_rsp(%rip), %rsp
  ret
8:
  mov %r12, %rsp
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

/* Native x86-64 CPL3 syscall path. FMASK enters with interrupts and direction
 * flags cleared; the scheduler publishes the current task's kernel stack. */
.type aiueos_syscall_entry,@function
aiueos_syscall_entry:
  mov %rcx, %r10
  shl $16, %r10
  sar $16, %r10
  cmp %rcx, %r10
  jne aiueos_sysret_reject
  mov %rsp, %r10
  shl $16, %r10
  sar $16, %r10
  cmp %rsp, %r10
  jne aiueos_sysret_reject
  movabs $0x0000800000000000, %r10
  cmp %r10, %rcx
  jae aiueos_sysret_reject
  cmp %r10, %rsp
  jae aiueos_sysret_reject
  incq aiueos_sysret_validation_count(%rip)
  mov %rsp, aiueos_syscall_user_rsp(%rip)
  mov aiueos_syscall_kernel_stack_top(%rip), %rsp
  test %rsp, %rsp
  jz aiueos_sysret_reject
  push %rcx
  push %r11
  push %rdi
  push %rsi
  push %rdx
  movq $3, aiueos_syscall_from_user(%rip)
  mov %rdx, %rcx
  mov %rsi, %rdx
  mov %rdi, %rsi
  mov %rax, %rdi
  call aiueos_syscall_dispatch
  mov 0(%rsp), %rdx
  mov 8(%rsp), %rsi
  mov 16(%rsp), %rdi
  mov 24(%rsp), %r11
  mov 32(%rsp), %rcx
  movabs $0xfffffffffff88fff, %r10
  and %r10, %r11
  or $2, %r11
  mov aiueos_syscall_user_rsp(%rip), %rsp
  incq aiueos_sysret_count(%rip)
  sysretq
aiueos_sysret_reject:
  mov $0x7b, %eax
  outl %eax, $0xf4
  cli
10: hlt
  jmp 10b

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
  cmp $3, %rax
  je 9f
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
  jmp 7f
9:
  lea aiueos_cross_process_probe_resume(%rip), %rax
  mov %rax, 16(%rsp)
  mov $0x103, %rax
  mov %rax, aiueos_page_fault_stage(%rip)
7:
  pop %rax
  add $8, %rsp
  iretq
6:
  /* Not one of the three deliberate probes: a real page fault.  Restore the
     scratch register and the CPU's own frame, then take the same reporting
     path as every other fatal vector.  It used to write 0x7b and jump into
     the #UD stub's halt loop -- one number, no vector, no faulting address,
     and (before ADR-0199) reachable only after the kernel owned its IDT. */
  pop %rax
  pushq $14
  jmp aiueos_fatal_common

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

.global aiueos_probe_cross_process
.type aiueos_probe_cross_process,@function
aiueos_probe_cross_process:
  mov (%rdi), %rax
.global aiueos_cross_process_probe_resume
aiueos_cross_process_probe_resume:
  ret

.section .data.gdt,"aw",@progbits
.balign 8
.global aiueos_gdt
aiueos_gdt:
  .quad 0x0000000000000000
  .quad 0x00af9a000000ffff
  .quad 0x00cf92000000ffff
  .quad 0x00cff2000000ffff /* ring 3 data; SYSRET SS = STAR + 8 */
  .quad 0x00affa000000ffff /* ring 3 code; SYSRET CS = STAR + 16 */
.global aiueos_gdt_tss
aiueos_gdt_tss:
  .quad 0
  .quad 0
aiueos_gdt_end:
aiueos_gdt_pointer:
  .word aiueos_gdt_end - aiueos_gdt - 1
  .quad aiueos_gdt

.section .text,"ax",@progbits
.global aiueos_load_task_register
.type aiueos_load_task_register,@function
aiueos_load_task_register:
  mov $0x28, %ax
  ltr %ax
  ret

.global aiueos_enter_user
.type aiueos_enter_user,@function
aiueos_enter_user:
  mov %rsp, aiueos_saved_kernel_rsp(%rip)
  pushq $0x1b
  pushq %rsi
  pushfq
  pop %rax
  and $-513, %rax
  push %rax
  pushq $0x23
  push %rdi
  iretq

.section .bss.process,"aw",@nobits
.balign 8
aiueos_syscall_from_user: .skip 8
aiueos_saved_kernel_rsp: .skip 8
aiueos_syscall_user_rsp: .skip 8
aiueos_sysret_count: .skip 8
aiueos_sysret_validation_count: .skip 8

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
