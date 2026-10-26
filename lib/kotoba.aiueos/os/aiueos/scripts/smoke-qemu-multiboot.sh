#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
mb="$out/multiboot"
kernel="$mb/MULTIBOOT.ELF"
log="$mb/multiboot-debug.log"
serial_log="$mb/multiboot-serial.log"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
qemu_timeout=${AIUEOS_QEMU_TIMEOUT:-300}

"$aiueos/scripts/build-multiboot.sh" >/dev/null
command -v "$qemu" >/dev/null 2>&1 || {
  echo "error: qemu-system-x86_64 is required" >&2
  exit 1
}
rm -f "$log" "$serial_log"

# QEMU acts as the Multiboot loader here (its built-in Multiboot support), so
# no GRUB install or ESP is involved: the kernel is entered directly in 32-bit
# protected mode per the Multiboot spec.
set +e
timeout "$qemu_timeout" "$qemu" \
  -machine q35,accel=tcg -cpu max -m 128M -smp 2 \
  -kernel "$kernel" \
  -device isa-debugcon,iobase=0xe9,chardev=debug \
  -chardev file,id=debug,path="$log" \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -display none -serial "file:$serial_log" -monitor none -no-reboot
status=$?
set -e

if [ "$status" -eq 124 ]; then
  echo "error: Multiboot guest did not terminate within ${qemu_timeout}s (hung)" >&2
  echo "--- debug port tail ---" >&2
  test -f "$log" && tail -c 200 "$log" >&2 && echo >&2
  echo "--- serial tail ---" >&2
  test -f "$serial_log" && tail -20 "$serial_log" >&2
  exit 1
fi

# The success path writes 0x2a; isa-debug-exit maps it to (0x2a << 1) | 1 = 85.
[ "$status" -eq 85 ] || {
  echo "error: unexpected Multiboot QEMU exit status $status" >&2
  test -f "$serial_log" && sed -n '1,40p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT_MMAP_OK type1-regions bounded-walk" "$serial_log" >/dev/null || {
  echo "error: Multiboot memory-map evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT_RSDP_OK signature checksum firmware-independent" "$serial_log" >/dev/null || {
  echo "error: Multiboot RSDP discovery evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT_ACPI_OK rsdt-walk madt cpu>=2 ioapic" "$serial_log" >/dev/null || {
  echo "error: Multiboot ACPI table-walk evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT_APIC_TIMER_OK idt lapic vector=32 eoi" "$serial_log" >/dev/null || {
  echo "error: Multiboot Local APIC timer evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_MULTIBOOT_OK long-mode mmap-parsed kotoba-probe=42" "$serial_log" >/dev/null || {
  echo "error: Multiboot long-mode/Kotoba evidence was not observed" >&2
  exit 1
}
echo "AIUEOS_MULTIBOOT_SMOKE_OK qemu-multiboot-loader long-mode sse mmap rsdp acpi-rsdt idt apic-timer kotoba-probe"
