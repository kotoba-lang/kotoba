#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
log="$out/uefi-debug.log"
serial_log="$out/kernel-serial.log"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}

"$aiueos/scripts/build-uefi.sh" >/dev/null
command -v "$qemu" >/dev/null 2>&1 || {
  echo "error: qemu-system-x86_64 is required" >&2
  exit 1
}

if [ -z "${OVMF_CODE:-}" ]; then
  for candidate in \
    /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
    /opt/homebrew/Cellar/qemu/*/share/qemu/edk2-x86_64-code.fd \
    /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/edk2/x64/OVMF_CODE.fd; do
    if [ -f "$candidate" ]; then OVMF_CODE=$candidate; break; fi
  done
fi
[ -f "${OVMF_CODE:-}" ] || {
  echo "error: OVMF firmware not found; set OVMF_CODE" >&2
  exit 1
}

rm -f "$log" "$serial_log"
if [ -n "${AIUEOS_DISK_IMAGE:-}" ]; then
  [ -f "$AIUEOS_DISK_IMAGE" ] || {
    echo "error: AIUEOS_DISK_IMAGE does not exist: $AIUEOS_DISK_IMAGE" >&2
    exit 1
  }
  # OVMF may open the boot medium writable; snapshot keeps the release artifact immutable.
  boot_drive="format=raw,snapshot=on,file=$AIUEOS_DISK_IMAGE"
else
  boot_drive="format=raw,file=fat:rw:$out/esp"
fi
set +e
"$qemu" \
  -machine q35,accel=tcg -cpu max -m 128M -smp 2 \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive "$boot_drive" \
  -device isa-debugcon,iobase=0xe9,chardev=debug \
  -chardev file,id=debug,path="$log" \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -device virtio-rng-pci \
  -display none -serial "file:$serial_log" -monitor none -no-reboot
status=$?
set -e

# The #UD handler writes 0x30; isa-debug-exit maps it to (0x30 << 1) | 1 = 97.
[ "$status" -eq 97 ] || {
  echo "error: unexpected QEMU exit status $status" >&2
  test -f "$log" && sed -n '1,80p' "$log" >&2
  exit 1
}
grep -F "AIUEOS_LOADER_OK" "$log" >/dev/null || {
  echo "error: loader identity was not observed" >&2
  exit 1
}
grep -F "AIUEOS_KERNEL_OK memory-map-v1" "$log" >/dev/null || {
  echo "error: kernel handoff was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SERIAL_OK stack-v1 memory-map-v1" "$serial_log" >/dev/null || {
  echo "error: kernel COM1 evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,80p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_DESCRIPTOR_TABLES_OK gdt-v1 idt-v1" "$serial_log" >/dev/null || {
  echo "error: kernel descriptor-table evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp" "$serial_log" >/dev/null || {
  echo "error: kernel-owned paging evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PHYSICAL_ALLOCATOR_OK pages=2 zeroed" "$serial_log" >/dev/null || {
  echo "error: physical page allocator evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_ACPI_OK rsdp-xsdt-madt cpu>=2" "$serial_log" >/dev/null || {
  echo "error: validated ACPI CPU discovery evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_APIC_TIMER_OK vector=32 eoi-v1" "$serial_log" >/dev/null || {
  echo "error: Local APIC timer interrupt evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SMP_OK cpus=2 init-sipi-v1 per-cpu-stack" "$serial_log" >/dev/null || {
  echo "error: BSP-to-AP INIT/SIPI evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PCI_OK bounded-scan virtio-vendor=1af4" "$serial_log" >/dev/null || {
  echo "error: bounded PCI/virtio discovery evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_VIRTIO_RNG_OK modern-pci caps-bounded dma=4pages completion=32" "$serial_log" >/dev/null || {
  echo "error: modern virtio-rng DMA completion evidence was not observed" >&2
  test -f "$serial_log" && sed -n '1,120p' "$serial_log" >&2
  exit 1
}
grep -F "AIUEOS_SCHEDULER_OK tasks=2 policy=round-robin preemption=apic-timer" "$serial_log" >/dev/null || {
  echo "error: preemptive round-robin scheduler evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_IOAPIC_OK pit-gsi vector=33 eoi-v1" "$serial_log" >/dev/null || {
  echo "error: IOAPIC external timer IRQ evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_SYSCALL_OK int80-cpl0 abi-v1" "$serial_log" >/dev/null || {
  echo "error: CPL0 syscall evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_CAPABILITY_OK handle-v1 invalid-handle-denied" "$serial_log" >/dev/null || {
  echo "error: capability negative evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_COPYIN_OK noncanonical-and-unmapped-denied" "$serial_log" >/dev/null || {
  echo "error: invalid-pointer evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PAGE_FAULT_OK write-protect vector=14" "$serial_log" >/dev/null || {
  echo "error: write-protect page-fault evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_PAGE_FAULT_OK no-execute vector=14" "$serial_log" >/dev/null || {
  echo "error: no-execute page-fault evidence was not observed" >&2
  exit 1
}
grep -F "AIUEOS_EXCEPTION_OK vector=6 invalid-opcode" "$serial_log" >/dev/null || {
  echo "error: kernel exception dispatch evidence was not observed" >&2
  exit 1
}
echo "AIUEOS_UEFI_SMOKE_OK"
