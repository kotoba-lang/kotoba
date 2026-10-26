#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
timeout_cmd=$(command -v timeout || command -v gtimeout || true)
[ -n "$timeout_cmd" ] || {
  echo "error: timeout or gtimeout is required" >&2
  exit 1
}
command -v "$qemu" >/dev/null 2>&1 || {
  echo "error: qemu-system-x86_64 is required" >&2
  exit 1
}

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

work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-pxe-smoke.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir -p "$work/esp/EFI/BOOT"

# Two independent builds must produce the same admitted single-EFI payload.
AIUEOS_OUT="$work/release-a" \
AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD=${AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD:-0} \
SOURCE_DATE_EPOCH=0 \
  "$aiueos/scripts/build-physical-qualification-pxe.sh" >/dev/null
AIUEOS_OUT="$work/release-b" \
AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD=${AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD:-0} \
SOURCE_DATE_EPOCH=0 \
  "$aiueos/scripts/build-physical-qualification-pxe.sh" >/dev/null
payload_a="$work/release-a/aiueos-k16-native-pxe.efi"
payload_b="$work/release-b/aiueos-k16-native-pxe.efi"
cmp "$payload_a" "$payload_b" >/dev/null || {
  echo "error: repeated native PXE builds differ" >&2
  exit 1
}
cp "$payload_a" "$work/esp/EFI/BOOT/BOOTX64.EFI"

# The first boot has exactly one file available.  No filesystem kernel or
# initramfs can accidentally satisfy the embedded-payload admission path.
[ "$(find "$work/esp" -type f | wc -l | tr -d ' ')" = 1 ] || {
  echo "error: PXE smoke ESP contains an external payload" >&2
  exit 1
}

AIUEOS_OUT="$work/control" AIUEOS_PXE_ONLY_CONTROL=1 \
  "$aiueos/scripts/build-dbc-probe.sh" >/dev/null
cp "$OVMF_VARS" "$work/vars.fd"

set +e
"$timeout_cmd" 45 "$qemu" -machine q35,accel=tcg -cpu max -m 256M -smp 2 \
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
  -drive "if=pflash,format=raw,file=$work/vars.fd" \
  -drive "format=raw,file=fat:rw:$work/esp" \
  -display none -serial "file:$work/native.serial" \
  -debugcon "file:$work/native.debug" -global isa-debugcon.iobase=0xe9 \
  -monitor none -no-reboot >/dev/null 2>&1
native_rc=$?
set -e
[ "$native_rc" -eq 0 ] || {
  echo "error: native PXE payload did not reset cleanly (rc=$native_rc)" >&2
  exit 1
}
for marker in \
  "AIUEOS_NETBOOT_RETURN_ARMED bootnext=current result=pending" \
  "AIUEOS_NETBOOT_EMBEDDED_OK kernel+initramfs sha256-v1" \
  "AIUEOS_PAGING_OK cr3-owned wx-v1 nx-wp" \
  "AIUEOS_PHYSICAL_QUALIFICATION_OK native-core-v2 internal-disk-writes=none"; do
  grep -F "$marker" "$work/native.debug" >/dev/null || {
    echo "error: native PXE evidence is absent: $marker" >&2
    exit 1
  }
done

# Model the physical PXE server's one-shot fallback by replacing only the file
# behind the same boot option, while preserving the UEFI variable store.
cp "$work/control/esp/EFI/BOOT/BOOTX64.EFI" \
  "$work/esp/EFI/BOOT/BOOTX64.EFI"
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
  echo "error: control EFI did not remain available (rc=$control_rc)" >&2
  exit 1
}
grep -F \
  "AIUEOS_QUALIFICATION_RESULT state=success code=0 source=uefi-nvram internal-ssd-writes=none retained=yes" \
  "$work/control.serial" >/dev/null || {
  echo "error: control EFI did not recover the native result" >&2
  exit 1
}
grep -F "AIUEOS_CONTROL_READY nonce=" "$work/control.serial" >/dev/null || {
  echo "error: control EFI did not become ready after result recovery" >&2
  exit 1
}
grep -F "AIUEOS_PXE_ACPI_RSDP state=ready" "$work/control.serial" >/dev/null || {
  echo "error: control EFI did not report the firmware ACPI RSDP" >&2
  exit 1
}
grep -F "AIUEOS_PXE_ACPI_ROOT state=ready" "$work/control.serial" >/dev/null || {
  echo "error: control EFI did not report the firmware ACPI root" >&2
  exit 1
}
grep -F "AIUEOS_PXE_ACPI_MADT cpus=" "$work/control.serial" >/dev/null || {
  echo "error: control EFI did not summarize the firmware MADT" >&2
  exit 1
}

printf '%s\n' \
  "AIUEOS_NATIVE_PXE_QEMU_OK embedded=kernel+initramfs result=uefi-nvram fallback=control-efi deterministic=yes internal-ssd-writes=none physical-k16=unverified"
