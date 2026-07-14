#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}

"$aiueos/scripts/smoke-qemu-uefi.sh"
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
grep -F "AIUEOS_JOURNAL_RECOVERY_OK sequence=1 committed no-overwrite" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: committed journal was not recovered on the second boot" >&2
  exit 1
}
echo "AIUEOS_JOURNAL_TWO_BOOT_RECOVERY_OK"
