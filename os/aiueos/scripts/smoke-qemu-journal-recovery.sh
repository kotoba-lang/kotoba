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

# Simulate a torn/corrupt committed header. Boot must reject it and create a
# fresh verified record rather than reporting recovery.
python3 - "$out/virtio-blk-smoke.img" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
d = bytearray(p.read_bytes())
d[512 + 12] ^= 0x80
p.write_bytes(d)
PY
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
if grep -F "AIUEOS_JOURNAL_RECOVERY_OK" "$out/kernel-serial.log" >/dev/null; then
  echo "error: corrupt journal header was accepted" >&2
  exit 1
fi
echo "AIUEOS_JOURNAL_TORN_RECORD_REJECTION_OK"
