#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
timeout_cmd=$(command -v timeout || command -v gtimeout || true)
network_builder=${AIUEOS_PHYSICAL_NETWORK_BUILDER:-"$aiueos/scripts/build-physical-network-pxe.sh"}
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
[ -f "${OVMF_CODE:-}" ] && [ -f "${OVMF_VARS:-}" ] || {
  echo "error: OVMF firmware not found" >&2; exit 1;
}

work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-rtl8125-qemu.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir -p "$work/esp/EFI/BOOT"
AIUEOS_OUT="$work/network" \
AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD=${AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD:-0} \
SOURCE_DATE_EPOCH=0 "$network_builder" >/dev/null
AIUEOS_OUT="$work/control" "$aiueos/scripts/build-dbc-probe.sh" >/dev/null
cp "$work/network/aiueos-k16-native-pxe.efi" "$work/esp/EFI/BOOT/BOOTX64.EFI"
cp "$OVMF_VARS" "$work/vars.fd"

set +e
"$timeout_cmd" 45 "$qemu" -machine q35,accel=tcg -cpu max -m 256M -smp 2 \
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
  -drive "if=pflash,format=raw,file=$work/vars.fd" \
  -drive "format=raw,file=fat:rw:$work/esp" \
  -display none -serial "file:$work/network.serial" \
  -debugcon "file:$work/network.debug" -global isa-debugcon.iobase=0xe9 \
  -monitor none -no-reboot >/dev/null 2>&1
network_rc=$?
set -e
[ "$network_rc" -eq 0 ] || {
  echo "error: network qualification did not reset cleanly (rc=$network_rc)" >&2
  exit 1
}
grep -F "AIUEOS_PHYSICAL_NETWORK_FAIL rtl8125" "$work/network.debug" >/dev/null || {
  echo "error: no bounded missing-RTL8125 result" >&2; exit 1;
}

cp "$work/control/esp/EFI/BOOT/BOOTX64.EFI" "$work/esp/EFI/BOOT/BOOTX64.EFI"
set +e
"$timeout_cmd" 12 "$qemu" -machine q35,accel=tcg -cpu max -m 256M -smp 2 \
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
  -drive "if=pflash,format=raw,file=$work/vars.fd" \
  -drive "format=raw,file=fat:rw:$work/esp" \
  -display none -serial "file:$work/control.serial" \
  -monitor none -no-reboot >/dev/null 2>&1
control_rc=$?
set -e
[ "$control_rc" -eq 124 ] || {
  echo "error: control EFI did not remain ready (rc=$control_rc)" >&2; exit 1;
}
grep -F \
  "AIUEOS_QUALIFICATION_RESULT state=failure code=8201 source=uefi-nvram internal-ssd-writes=none retained=yes" \
  "$work/control.serial" >/dev/null || {
  echo "error: bounded RTL8125 failure did not return through NVRAM" >&2; exit 1;
}

echo "AIUEOS_RTL8125_QEMU_NEGATIVE_OK no-device=code-8201 nvram-return=yes physical-k16=unverified"
