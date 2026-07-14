#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
log="$out/uefi-debug.log"
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

rm -f "$log"
set +e
"$qemu" \
  -machine q35,accel=tcg -cpu max -m 128M -smp 1 \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive format=raw,file="fat:rw:$out/esp" \
  -device isa-debugcon,iobase=0xe9,chardev=debug \
  -chardev file,id=debug,path="$log" \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -display none -serial none -monitor none -no-reboot
status=$?
set -e

# The kernel writes 0x20; isa-debug-exit maps it to (0x20 << 1) | 1 = 65.
[ "$status" -eq 65 ] || {
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
echo "AIUEOS_UEFI_SMOKE_OK"
