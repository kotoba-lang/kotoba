#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-rt.sh /path/to/amu}
payload=${AIUEOS_PLC_RT_BUNDLE:-}
out=${AIUEOS_KOTOBA_RT_OUT:-"$repo/build/aiueos-kotoba-rt"}
boot="$out/boot"
efi="$boot/esp/EFI/BOOT/BOOTX64.EFI"
second="$boot/BOOTX64.reproduced.EFI"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
qemu_timeout=${AIUEOS_QEMU_TIMEOUT:-60}
"$aiueos/scripts/build-kotoba-rt-kernel.sh" "$compiler" >/dev/null
mkdir -p "$(dirname -- "$efi")"
if [ -n "$payload" ]; then
  "$compiler/bin/kotoba-compiler" package-aiueos-boot "$out/KERNEL.ELF" --payload "$payload" --output "$efi"
  "$compiler/bin/kotoba-compiler" package-aiueos-boot "$out/KERNEL.ELF" --payload "$payload" --output "$second"
  expected_marker=BHSDGVIPMDAKRTS
else
  "$compiler/bin/kotoba-compiler" package-aiueos-boot "$out/KERNEL.ELF" --output "$efi"
  "$compiler/bin/kotoba-compiler" package-aiueos-boot "$out/KERNEL.ELF" --output "$second"
  expected_marker=IPMDAKRTS
fi
cmp "$efi" "$second"
rm -f "$second"
if [ -z "${OVMF_CODE:-}" ]; then
  for candidate in /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
    /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd; do
    if [ -f "$candidate" ]; then OVMF_CODE=$candidate; break; fi
  done
fi
[ -f "${OVMF_CODE:-}" ] || { echo "error: OVMF firmware not found" >&2; exit 1; }
log="$boot/debug.log"
rm -f "$log"
set +e
timeout "$qemu_timeout" "$qemu" \
  -machine q35,accel="${AIUEOS_QEMU_ACCEL:-tcg}" -cpu "${AIUEOS_QEMU_CPU:-max}" \
  -m 128M -smp 1 \
  -drive if=pflash,format=raw,readonly=on,file="$OVMF_CODE" \
  -drive "format=raw,file=fat:rw:$boot/esp" \
  -device isa-debugcon,iobase=0xe9,chardev=debug \
  -chardev file,id=debug,path="$log" \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -display none -serial none -no-reboot
status=$?
set -e
[ "$status" = 33 ] || {
  echo "error: Kotoba RT QEMU exit was $status, expected 33" >&2; exit 1;
}
python3 - "$log" "$out/KERNEL.ELF" "$efi" "$out/qemu-receipt.json" "$expected_marker" <<'PY'
import hashlib
import json
from pathlib import Path
import sys
actual = Path(sys.argv[1]).read_bytes()
expected = sys.argv[5].encode("ascii")
if actual != expected:
    raise SystemExit(f"error: Kotoba RT marker was {actual!r}, expected {expected!r}")
kernel = Path(sys.argv[2]).read_bytes()
efi = Path(sys.argv[3]).read_bytes()
Path(sys.argv[4]).write_text(json.dumps({
    "format": "aiueos-kotoba-native-rt-qemu-receipt/v1",
    "marker": sys.argv[5],
    "signed_external_plc_elf": sys.argv[5].startswith("BHSDGV"),
    "plc_device_profile_registry": True,
    "qemu_exit_status": 33,
    "kernel_sha256": hashlib.sha256(kernel).hexdigest(),
    "uefi_sha256": hashlib.sha256(efi).hexdigest(),
    "plc_scans": 100,
    "timing_profile": "logical-qemu-unqualified",
    "rtos_qualified": False,
}, sort_keys=True, separators=(",", ":")) + "\n", encoding="ascii")
PY
foreign=$(find "$out" -type f \( -name '*.c' -o -name '*.o' -o -name '*.obj' \
  -o -name '*.a' -o -name '*.so' \) -print -quit)
[ -z "$foreign" ] || {
  echo "error: C/foreign artifact entered Kotoba RT boot output: $foreign" >&2; exit 1;
}
echo "AIUEOS_KOTOBA_RT_QEMU_OK marker=$expected_marker no-c no-linux no-jvm plc-profiles=9 apic-preemption fixed-priority priority-ceiling transactional-io plc-scans=100 timing=logical-unqualified"
