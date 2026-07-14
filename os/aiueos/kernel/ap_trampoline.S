.section .rodata.ap-trampoline,"a",@progbits
.code16
.global aiueos_ap_trampoline_start
.global aiueos_ap_trampoline_end
.global aiueos_ap_trampoline_cr3
.global aiueos_ap_trampoline_entry
.global aiueos_ap_trampoline_stack
.set TRAMPOLINE_BASE, 0x8000
aiueos_ap_trampoline_start:
  cli
  cld
  mov %cs, %ax
  mov %ax, %ds
  lgdt aiueos_ap_trampoline_gdtr-aiueos_ap_trampoline_start
  mov %cr0, %eax
  or $1, %eax
  mov %eax, %cr0
  ljmpl $0x08, $(TRAMPOLINE_BASE + aiueos_ap_trampoline_pm-aiueos_ap_trampoline_start)

.code32
aiueos_ap_trampoline_pm:
  mov $0x10, %ax
  mov %ax, %ds
  mov %ax, %ss
  mov aiueos_ap_trampoline_cr3-aiueos_ap_trampoline_start+TRAMPOLINE_BASE, %eax
  mov %eax, %cr3
  mov %cr4, %eax
  or $(1 << 5), %eax
  mov %eax, %cr4
  mov $0xc0000080, %ecx
  rdmsr
  or $((1 << 8) | (1 << 11)), %eax
  wrmsr
  mov %cr0, %eax
  or $0x80000000, %eax
  mov %eax, %cr0
  ljmpl $0x18, $(TRAMPOLINE_BASE + aiueos_ap_trampoline_lm-aiueos_ap_trampoline_start)

.code64
aiueos_ap_trampoline_lm:
  mov aiueos_ap_trampoline_stack(%rip), %rsp
  and $-16, %rsp
  xor %rbp, %rbp
  mov aiueos_ap_trampoline_entry(%rip), %rax
  jmp *%rax

.balign 8
aiueos_ap_trampoline_cr3: .quad 0
aiueos_ap_trampoline_entry: .quad 0
aiueos_ap_trampoline_stack: .quad 0
.balign 8
aiueos_ap_trampoline_gdt:
  .quad 0
  .quad 0x00cf9a000000ffff
  .quad 0x00cf92000000ffff
  .quad 0x00af9a000000ffff
aiueos_ap_trampoline_gdt_end:
aiueos_ap_trampoline_gdtr:
  .word aiueos_ap_trampoline_gdt_end-aiueos_ap_trampoline_gdt-1
  .long TRAMPOLINE_BASE + aiueos_ap_trampoline_gdt-aiueos_ap_trampoline_start
aiueos_ap_trampoline_end:
.section .note.GNU-stack,"",@progbits
