#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-hw-probe"}
image="$out/aiueos-x86_64-gpt.img"
log="$out/hw-probe-debug.log"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}

"$aiueos/scripts/build-hw-probe.sh" >/dev/null
command -v "$qemu" >/dev/null 2>&1 || { echo "error: qemu-system-x86_64 is required" >&2; exit 1; }
if [ -z "${OVMF_CODE:-}" ]; then
  for candidate in /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
    /opt/homebrew/Cellar/qemu/*/share/qemu/edk2-x86_64-code.fd \
    /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd \
    /usr/share/edk2/x64/OVMF_CODE.fd; do
    [ -f "$candidate" ] && { OVMF_CODE=$candidate; break; }
  done
fi
[ -f "${OVMF_CODE:-}" ] || { echo "error: OVMF firmware not found; set OVMF_CODE" >&2; exit 1; }
rm -f "$log"
"$qemu" -machine q35,accel=tcg -cpu max -m 128M \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive if=none,id=probe,format=raw,snapshot=on,file="$image" \
  -device qemu-xhci,id=xhci -device usb-storage,bus=xhci.0,drive=probe,removable=on \
  -device virtio-vga \
  -display none -serial "file:$log" -monitor none -no-reboot >/dev/null 2>&1 &
pid=$!
trap 'kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true' EXIT HUP INT TERM
i=0
while [ "$i" -lt 200 ]; do
  if [ -f "$log" ] && grep -F "AIUEOS_HW_PROBE_DONE exit_boot_services=no internal_disk_writes=none" "$log" >/dev/null; then break; fi
  sleep 0.1
  i=$((i+1))
done
if [ ! -f "$log" ] || ! grep -F "AIUEOS_HW_PROBE_DONE exit_boot_services=no internal_disk_writes=none" "$log" >/dev/null; then
  echo "error: hardware probe did not complete" >&2
  [ -f "$log" ] && tail -80 "$log" >&2
  exit 1
fi
for marker in AIUEOS_HW_PROBE_START AIUEOS_HW_PROBE_FIRMWARE \
  "AIUEOS_HW_PROBE_GOP capability=present" "AIUEOS_HW_PROBE_MEMORY capability=present" \
  "AIUEOS_HW_PROBE_ACPI rsdp=present" "AIUEOS_HW_PROBE_PCI capability=present"; do
  grep -F "$marker" "$log" >/dev/null || { echo "error: missing marker: $marker" >&2; exit 1; }
done
echo "AIUEOS_HW_PROBE_QEMU_OK transport=usb"
