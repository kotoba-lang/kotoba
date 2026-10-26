.section .text.qualification,"ax",@progbits
.extern qualification_firmware_cr3
.extern aiueos_qualification_progress_firmware
.extern aiueos_qualification_finalize_firmware
.extern aiueos_qualification_reboot_firmware
.extern aiueos_device_p256_key_load_firmware
.extern aiueos_device_p256_key_save_firmware

/* The physical K16 v10 result reached code 416: both candidate CR3 loads and
 * readbacks completed, but the first ordinary C progress call under the final
 * split-W^X root did not persist code 448.  Switch back to the firmware root
 * at the first assembly instruction, before a C prologue, global access, or
 * additional kernel-stack use.  The caller's return address is the only stack
 * write performed under the candidate root.
 *
 * SysV x86-64 enters with RSP % 16 == 8.  Saving the original CR3 aligns RSP
 * to 16 before the helper call.  R11 is caller-saved, and the saved value is
 * recovered from the firmware-mapped kernel stack after the helper returns. */
.global aiueos_qualification_progress
.type aiueos_qualification_progress,@function
aiueos_qualification_progress:
  mov qualification_firmware_cr3(%rip), %rax
  test %rax, %rax
  jz .Lprogress_unavailable
  mov %cr3, %r11
  cli
  mov %rax, %cr3
  push %r11
  call aiueos_qualification_progress_firmware
  pop %r11
  mov %r11, %cr3
  ret
.Lprogress_unavailable:
  xor %eax, %eax
  ret
.size aiueos_qualification_progress, .-aiueos_qualification_progress

.global aiueos_qualification_finalize
.type aiueos_qualification_finalize,@function
aiueos_qualification_finalize:
  mov qualification_firmware_cr3(%rip), %rax
  test %rax, %rax
  jz .Lfinalize_unavailable
  mov %cr3, %r11
  cli
  mov %rax, %cr3
  push %r11
  call aiueos_qualification_finalize_firmware
  pop %r11
  mov %r11, %cr3
  ret
.Lfinalize_unavailable:
  xor %eax, %eax
  ret
.size aiueos_qualification_finalize, .-aiueos_qualification_finalize

.global aiueos_qualification_reboot
.type aiueos_qualification_reboot,@function
aiueos_qualification_reboot:
  mov qualification_firmware_cr3(%rip), %rax
  test %rax, %rax
  jz .Lreboot_unavailable
  mov %cr3, %r11
  cli
  mov %rax, %cr3
  push %r11
  call aiueos_qualification_reboot_firmware
  pop %r11
  mov %r11, %cr3
  ret
.Lreboot_unavailable:
  xor %eax, %eax
  ret
.size aiueos_qualification_reboot, .-aiueos_qualification_reboot

.global aiueos_device_p256_key_load
.type aiueos_device_p256_key_load,@function
aiueos_device_p256_key_load:
  mov qualification_firmware_cr3(%rip), %rax
  test %rax, %rax
  jz .Ldevice_key_load_unavailable
  mov %cr3, %r11
  cli
  mov %rax, %cr3
  push %r11
  call aiueos_device_p256_key_load_firmware
  pop %r11
  mov %r11, %cr3
  ret
.Ldevice_key_load_unavailable:
  xor %eax, %eax
  ret
.size aiueos_device_p256_key_load, .-aiueos_device_p256_key_load

.global aiueos_device_p256_key_save
.type aiueos_device_p256_key_save,@function
aiueos_device_p256_key_save:
  mov qualification_firmware_cr3(%rip), %rax
  test %rax, %rax
  jz .Ldevice_key_save_unavailable
  mov %cr3, %r11
  cli
  mov %rax, %cr3
  push %r11
  call aiueos_device_p256_key_save_firmware
  pop %r11
  mov %r11, %cr3
  ret
.Ldevice_key_save_unavailable:
  xor %eax, %eax
  ret
.size aiueos_device_p256_key_save, .-aiueos_device_p256_key_save

.section .note.GNU-stack,"",@progbits
