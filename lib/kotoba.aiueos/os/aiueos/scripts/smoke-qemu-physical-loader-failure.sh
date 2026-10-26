#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-loader-failure"}
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
timeout_cmd=$(command -v timeout || command -v gtimeout || true)
[ -n "$timeout_cmd" ] || { echo "error: timeout or gtimeout is required" >&2; exit 1; }

if [ -z "${OVMF_CODE:-}" ]; then
  for candidate in /opt/homebrew/share/qemu/edk2-x86_64-code.fd \
    /usr/share/OVMF/OVMF_CODE_4M.fd /usr/share/OVMF/OVMF_CODE.fd; do
    [ -f "$candidate" ] && { OVMF_CODE=$candidate; break; }
  done
fi
if [ -z "${OVMF_VARS:-}" ]; then
  for candidate in /opt/homebrew/share/qemu/edk2-i386-vars.fd \
    /usr/share/OVMF/OVMF_VARS_4M.fd /usr/share/OVMF/OVMF_VARS.fd; do
    [ -f "$candidate" ] && { OVMF_VARS=$candidate; break; }
  done
fi
[ -f "${OVMF_CODE:-}" ] || { echo "error: OVMF code not found" >&2; exit 1; }
[ -f "${OVMF_VARS:-}" ] || { echo "error: OVMF vars template not found" >&2; exit 1; }

AIUEOS_HW_PROBE_DELAY_US=0 \
AIUEOS_QUALIFICATION_FORCE_LOADER_FAILURE_CODE=190 \
SOURCE_DATE_EPOCH=0 \
  "$aiueos/scripts/build-physical-qualification-usb.sh" >/dev/null

pristine="$out/aiueos-k16-physical-qualification.img"
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-k16-loader-failure.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
cp "$pristine" "$work/qualification.img"
cp "$OVMF_VARS" "$work/vars.fd"

set +e
"$timeout_cmd" 30 "$qemu" -machine q35,accel=tcg -cpu max -m 256M -smp 2 \
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
  -drive "if=pflash,format=raw,file=$work/vars.fd" \
  -drive "if=none,id=qual,format=raw,file=$work/qualification.img" \
  -device qemu-xhci,id=xhci \
  -device usb-storage,bus=xhci.0,drive=qual,removable=on,bootindex=0 \
  -device virtio-vga -display none -serial "file:$work/serial.log" \
  -debugcon "file:$work/debug.log" -global isa-debugcon.iobase=0xe9 \
  -monitor none -no-reboot >/dev/null 2>&1
qemu_rc=$?
set -e
[ "$qemu_rc" -eq 124 ] || {
  echo "error: failure collector did not remain at its terminal screen (rc=$qemu_rc)" >&2
  exit 1
}
grep -F "AIUEOS_LOADER_FAIL forced-test code=190" "$work/debug.log" >/dev/null || {
  echo "error: forced loader failure marker is absent" >&2; exit 1;
}
grep -F "AIUEOS_LOADER_FAILURE_RESULT_PERSISTED" "$work/debug.log" >/dev/null || {
  echo "error: loader failure was not persisted" >&2; exit 1;
}
grep -F "RESULT SAVED. REMOVE USB AND CONNECT IT TO THE MAC." \
  "$work/serial.log" >/dev/null || {
  echo "error: parent probe did not collect the loader failure" >&2; exit 1;
}

mkdir -p "$work/result-volume"
python3 - "$aiueos/scripts/make-physical-qualification-usb.py" "$pristine" \
  "$work/qualification.img" "$work/result-volume" <<'PY'
from pathlib import Path
import importlib.util
import sys

script, pristine_path, result_path, output_path = sys.argv[1:]
spec = importlib.util.spec_from_file_location("qualification", script)
qualification = importlib.util.module_from_spec(spec)
spec.loader.exec_module(qualification)
before = Path(pristine_path).read_bytes()
after = Path(result_path).read_bytes()
start = qualification.RESULT_FIRST * qualification.release.SECTOR
end = (qualification.RESULT_LAST + 1) * qualification.release.SECTOR
if before[:start] != after[:start] or before[end:] != after[end:]:
    raise SystemExit("write escaped the result partition")
volume = after[start:end]
output = Path(output_path)
for name in ("AIUEOS.ID", "PROBE.LOG", "RESULT.LOG"):
    output.joinpath(name).write_bytes(qualification.fat16_read(volume, (name,)))
PY

set +e
decision=$("$aiueos/scripts/check-physical-qualification-result.sh" \
  "$work/result-volume" 2>&1)
decision_rc=$?
set -e
[ "$decision_rc" -eq 4 ] || {
  echo "error: checker did not classify loader failure (rc=$decision_rc)" >&2
  printf '%s\n' "$decision" >&2
  exit 1
}
printf '%s\n' "$decision" | grep -F \
  "AIUEOS_K16_PHYSICAL_RESULT_FAIL state=failure code=190 internal-ssd-writes=none" \
  >/dev/null || { echo "error: checker lost loader failure code" >&2; exit 1; }

printf '%s\n' \
  "AIUEOS_K16_LOADER_FAILURE_RESULT_OK code=190 transport=uefi-variable usb-scope=result-partition-only internal-ssd-writes=none"
