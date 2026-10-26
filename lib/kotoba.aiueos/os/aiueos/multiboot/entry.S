/* Multiboot (v1) entry: QEMU's built-in Multiboot loader enters here in
 * 32-bit protected mode with paging off, eax = 0x2BADB002, ebx = info pointer.
 * This trampoline establishes long mode over an identity-mapped first GiB and
 * hands control to the 64-bit C landing. Each major step emits a byte on the
 * 0xE9 debug port so any hang localizes immediately. */

.section .text.mbentry,"ax",@progbits
.balign 8
.global aiueos_multiboot_header
aiueos_multiboot_header:
  .long 0x1BADB002                      /* magic */
  .long 0x00000003                      /* flags: page-align modules + mem info */
  .long -(0x1BADB002 + 0x00000003)      /* checksum */

/* Multiboot2 header, so GRUB's `multiboot2` command loads this same image.
   8-byte aligned, within the first 32 KiB of the file. GRUB enters at the ELF
   entry (the trampoline below) in 32-bit protected mode with eax = the MB2
   magic 0x36D76289 and ebx = the MB2 information structure. */
.balign 8
aiueos_multiboot2_header:
  .long 0xE85250D6                      /* MB2 magic */
  .long 0                               /* architecture: i386 (32-bit) */
  .long aiueos_multiboot2_header_end - aiueos_multiboot2_header
  .long -(0xE85250D6 + 0 + (aiueos_multiboot2_header_end - aiueos_multiboot2_header))
  /* framebuffer request tag (type 5): ask GRUB to set a linear framebuffer.
     0/0/0 = let GRUB pick the mode. Kept 8-byte aligned with 4 bytes pad. */
  .balign 8
  .short 5
  .short 0
  .long 20
  .long 0                               /* width  (0 = no preference) */
  .long 0                               /* height */
  .long 0                               /* depth  */
  .long 0                               /* pad to 8-byte alignment */
  /* end tag */
  .balign 8
  .short 0
  .short 0
  .long 8
aiueos_multiboot2_header_end:

.code32
.global aiueos_multiboot_start
.type aiueos_multiboot_start,@function
aiueos_multiboot_start:
  cli
  cld
  movl %eax, aiueos_mb_magic
  movl %ebx, aiueos_mb_info
  movl $aiueos_mb_stack_top, %esp

  movb $0x31, %al                       /* '1' entered 32-bit */
  outb %al, $0xe9

  /* PML4[0] -> PDPT (4 x 1 GiB identity pages, first 4 GiB) so the LAPIC and
     IOAPIC MMIO windows (~0xFEE00000 / 0xFEC00000, just below 4 GiB) are
     mapped along with RAM. 1 GiB pages need PDPE1GB, which QEMU -cpu max has. */
  movl $aiueos_mb_pdpt, %eax
  orl  $0x3, %eax
  movl %eax, aiueos_mb_pml4
  movl $aiueos_mb_pdpt, %edi
  movl $0x83, %eax                      /* present + write + 1 GiB page, base 0 */
  movl $0, %ecx
1:
  movl %eax, (%edi)
  movl $0, 4(%edi)
  addl $0x40000000, %eax
  addl $8, %edi
  incl %ecx
  cmpl $4, %ecx
  jne 1b

  movb $0x32, %al                       /* '2' page tables built */
  outb %al, $0xe9

  movl $aiueos_mb_pml4, %eax
  movl %eax, %cr3
  movl %cr4, %eax
  orl  $0x20, %eax                       /* CR4.PAE */
  movl %eax, %cr4
  movl $0xC0000080, %ecx                 /* EFER */
  rdmsr
  orl  $0x100, %eax                      /* EFER.LME */
  wrmsr
  movl %cr0, %eax
  orl  $0x80000001, %eax                 /* CR0.PG | CR0.PE */
  movl %eax, %cr0

  movb $0x33, %al                       /* '3' long mode enabled */
  outb %al, $0xe9

  lgdt aiueos_mb_gdt_pointer
  ljmp $0x08, $2f

.code64
2:
  movw $0x10, %ax
  movw %ax, %ds
  movw %ax, %es
  movw %ax, %ss
  xorw %ax, %ax
  movw %ax, %fs
  movw %ax, %gs
  movq $aiueos_mb_stack_top, %rsp
  andq $-16, %rsp

  /* Enable SSE: the freestanding C is compiled at -O2, which may vectorize
     byte loops (an SSE instruction with SSE disabled would #UD, and with no
     IDT that triple-faults). Clear CR0.EM, set CR0.MP, set CR4.OSFXSR and
     CR4.OSXMMEXCPT. */
  movq %cr0, %rax
  andq $0xFFFFFFFFFFFFFFFB, %rax        /* clear EM (bit 2) */
  orq  $0x2, %rax                       /* set MP (bit 1) */
  movq %rax, %cr0
  movq %cr4, %rax
  orq  $0x600, %rax                     /* set OSFXSR (bit 9) | OSXMMEXCPT (bit 10) */
  movq %rax, %cr4

  movb $0x34, %al                       /* '4' 64-bit reached */
  outb %al, $0xe9

  xorq %rdi, %rdi
  movl aiueos_mb_magic(%rip), %edi
  xorq %rsi, %rsi
  movl aiueos_mb_info(%rip), %esi
  call aiueos_multiboot_main
3:
  cli
  hlt
  jmp 3b

/* Minimal APIC-timer ISR for the Multiboot path: bump the tick counter the
   shared apic.c increments elsewhere, acknowledge EOI through the LAPIC MMIO
   base apic.c published, and return. */
.global aiueos_mb_isr_timer
.type aiueos_mb_isr_timer,@function
aiueos_mb_isr_timer:
  push %rax
  incq aiueos_apic_timer_ticks(%rip)
  mov aiueos_apic_mmio_base(%rip), %rax
  movl $0, 0xb0(%rax)
  pop %rax
  iretq

/* Any unexpected vector before the timer test is a fault, and a fail-fast
   handler that says only "something happened" is why this gate sat red and
   undiagnosed. One stub per vector, so the handler knows WHICH vector: each
   stub normalizes the frame to {vector, error, rip, cs, rflags} and tail-calls
   the C reporter, which prints all of it before the deterministic exit
   (0x6d -> isa-debug-exit 219).

   Stubs are a uniform 16-byte stride so main.c can address stub N as
   aiueos_mb_isr_stubs + 16*N without a 256-entry pointer table. The ten
   vectors the CPU pushes an error code for (8, 10-14, 17, 21, 29, 30) skip
   the dummy push, so the frame layout is the same for every vector. */
.section .text.mbisr,"ax",@progbits
.balign 16
.global aiueos_mb_isr_stubs
aiueos_mb_isr_stubs:
.set vec, 0
.rept 256
  .balign 16
  .if (vec == 8) || (vec == 10) || (vec == 11) || (vec == 12) || (vec == 13) || \
      (vec == 14) || (vec == 17) || (vec == 21) || (vec == 29) || (vec == 30)
    /* the CPU already pushed an error code */
  .else
    pushq $0                            /* dummy error code */
  .endif
  pushq $vec
  jmp aiueos_mb_isr_common
  .set vec, vec + 1
.endr

aiueos_mb_isr_common:
  movq 0(%rsp), %rdi                    /* vector */
  movq 8(%rsp), %rsi                    /* error code */
  movq 16(%rsp), %rdx                   /* rip */
  movq 24(%rsp), %rcx                   /* cs */
  movq 32(%rsp), %r8                    /* rflags */
  movq %cr2, %r9                        /* faulting address (meaningful for #PF) */
  andq $-16, %rsp                       /* SysV: rsp%16==0 before the call */
  call aiueos_mb_report_unexpected_vector
5:
  cli
  hlt
  jmp 5b

.section .text.mbentry,"ax",@progbits
.global aiueos_mb_load_idt
.type aiueos_mb_load_idt,@function
aiueos_mb_load_idt:
  lidt (%rdi)
  ret

.section .data.mbgdt,"aw",@progbits
.balign 8
aiueos_mb_gdt:
  .quad 0x0000000000000000
  .quad 0x00af9a000000ffff              /* 64-bit code */
  .quad 0x00cf92000000ffff              /* data */
aiueos_mb_gdt_end:
aiueos_mb_gdt_pointer:
  .word aiueos_mb_gdt_end - aiueos_mb_gdt - 1
  .quad aiueos_mb_gdt

.section .bss.mb,"aw",@nobits
.balign 4096
aiueos_mb_pml4: .skip 4096
aiueos_mb_pdpt: .skip 4096
aiueos_mb_pd:   .skip 4096
aiueos_mb_magic: .skip 8
aiueos_mb_info:  .skip 8
.balign 16
aiueos_mb_stack_bottom: .skip 16384
aiueos_mb_stack_top:

.section .note.GNU-stack,"",@progbits
