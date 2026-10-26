#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-qualification"}
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}

command -v "$qemu" >/dev/null 2>&1 || {
  echo "error: qemu-system-x86_64 is required" >&2
  exit 1
}
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

AIUEOS_HW_PROBE_DELAY_US=0 SOURCE_DATE_EPOCH=0 \
  "$aiueos/scripts/build-physical-qualification-usb.sh" >/dev/null
pristine="$out/aiueos-k16-physical-qualification.img"
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-k16-v4-qemu.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
cp "$pristine" "$work/qualification.img"
cp "$OVMF_VARS" "$work/vars.fd"

run_qemu() {
  seconds=$1
  serial=$2
  "$timeout_cmd" "$seconds" "$qemu" -machine q35,accel=tcg -cpu max -m 256M -smp 2 \
    -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
    -drive "if=pflash,format=raw,file=$work/vars.fd" \
    -drive "if=none,id=qual,format=raw,file=$work/qualification.img" \
    -device qemu-xhci,id=xhci \
    -device usb-storage,bus=xhci.0,drive=qual,removable=on,bootindex=0 \
    -device virtio-vga -display none -serial "file:$serial" -monitor none -no-reboot
}

run_qemu 120 "$work/first.serial" >/dev/null 2>&1 || {
  echo "error: qualification native-core boot did not reset cleanly" >&2
  tail -80 "$work/first.serial" >&2 || true
  exit 1
}
grep -F "AIUEOS_HW_PROBE_XHCI_DBC_SUMMARY" "$work/first.serial" >/dev/null || {
  echo "error: xHCI DbC inventory is absent" >&2
  exit 1
}
grep -F "AIUEOS_PHYSICAL_QUALIFICATION_OK" "$work/first.serial" >/dev/null || {
  echo "error: native qualification terminal marker is absent" >&2
  exit 1
}

set +e
run_qemu 20 "$work/second.serial" >/dev/null 2>&1
second_rc=$?
set -e
[ "$second_rc" -eq 124 ] || {
  echo "error: result collector did not remain at its terminal screen" >&2
  exit 1
}
grep -F "RESULT SAVED. REMOVE USB AND CONNECT IT TO THE MAC." \
  "$work/second.serial" >/dev/null || {
  echo "error: result collector did not save the result" >&2
  exit 1
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
if before[start:end] == after[start:end]:
    raise SystemExit("result partition did not change")
volume = after[start:end]
output = Path(output_path)
for name in ("AIUEOS.ID", "PROBE.LOG", "RESULT.LOG"):
    output.joinpath(name).write_bytes(qualification.fat16_read(volume, (name,)))
PY

"$aiueos/scripts/check-physical-qualification-result.sh" "$work/result-volume" >/dev/null
printf '%s\n' "AIUEOS_K16_V4_QEMU_PASSWORDLESS_ROUNDTRIP_OK "\
"transport=usb outside-result=byte-identical dbc=inventory-only internal-ssd-writes=none"
