#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
mb="$out/multiboot"
iso="$mb/aiueos-grub.iso"
log="$mb/grub-debug.log"
serial_log="$mb/grub-serial.log"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
qemu_timeout=${AIUEOS_QEMU_TIMEOUT:-300}

"$aiueos/scripts/build-grub-multiboot.sh" >/dev/null
command -v "$qemu" >/dev/null 2>&1 || { echo "error: qemu-system-x86_64 is required" >&2; exit 1; }

if [ -z "${OVMF_CODE:-}" ]; then
  for candidate in \
    /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
    /opt/homebrew/Cellar/qemu/*/share/qemu/edk2-x86_64-code.fd \
    /usr/share/OVMF/OVMF_CODE_4M.fd \
    /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/edk2/x64/OVMF_CODE.fd; do
    [ -f "$candidate" ] && { OVMF_CODE=$candidate; break; }
  done
fi
[ -f "${OVMF_CODE:-}" ] || { echo "error: OVMF firmware not found; set OVMF_CODE" >&2; exit 1; }

rm -f "$log" "$serial_log"
# OVMF firmware -> GRUB (EFI) -> the multiboot2 command loads this kernel. The
# 0xE9 debug port carries the kernel's own evidence, uncluttered by GRUB's
# serial menu output.
set +e
timeout "$qemu_timeout" "$qemu" \
  -machine q35,accel=tcg -cpu max -m 128M -smp 2 \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -cdrom "$iso" \
  -device VGA \
  -device isa-debugcon,iobase=0xe9,chardev=debug \
  -chardev file,id=debug,path="$log" \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -display none -serial "file:$serial_log" -monitor none -no-reboot
status=$?
set -e

if [ "$status" -eq 124 ]; then
  echo "error: GRUB/Multiboot2 guest did not terminate within ${qemu_timeout}s" >&2
  test -f "$serial_log" && sed 's/\x1b\[[0-9;?]*[A-Za-z]//g' "$serial_log" | tail -20 >&2
  exit 1
fi
# The success path writes 0x2a; isa-debug-exit maps it to (0x2a << 1) | 1 = 85.
[ "$status" -eq 85 ] || {
  echo "error: unexpected GRUB/Multiboot2 QEMU exit status $status" >&2
  test -f "$log" && tr -c '[:print:]\n' '.' < "$log" | tail -5 >&2
  test -f "$serial_log" && sed 's/\x1b\[[0-9;?]*[A-Za-z]//g' "$serial_log" | grep -aiE 'grub|multiboot|error' | tail -5 >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT2_ENTRY" "$log" >/dev/null || {
  echo "error: GRUB did not enter the kernel via Multiboot2" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT2_MMAP_OK" "$log" >/dev/null || {
  echo "error: Multiboot2 memory-map tag evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT2_ACPI_OK" "$log" >/dev/null || {
  echo "error: Multiboot2 ACPI tag/table evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT2_APIC_TIMER_OK" "$log" >/dev/null || {
  echo "error: Multiboot2 Local APIC timer evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT2_FRAMEBUFFER_OK" "$log" >/dev/null || {
  echo "error: Multiboot2 GRUB framebuffer evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT2_OK" "$log" >/dev/null || {
  echo "error: Multiboot2 long-mode/Kotoba evidence was not observed" >&2
  exit 1
}
echo "AIUEOS_GRUB_MULTIBOOT2_SMOKE_OK grub-efi multiboot2 long-mode mmap-tag acpi apic-timer framebuffer kotoba-probe"
