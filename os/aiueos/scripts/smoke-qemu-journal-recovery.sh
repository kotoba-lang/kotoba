#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}

"$aiueos/scripts/smoke-qemu-uefi.sh"
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
grep -F "AIUEOS_JOURNAL_RECOVERY_OK highest-valid selected alternate-slot-append" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: committed journal head was not selected on the second boot" >&2
  exit 1
}
python3 - "$out/virtio-blk-smoke.img" <<'PY'
from pathlib import Path
import struct, sys
d = Path(sys.argv[1]).read_bytes()
def fnv(b):
    h = 2166136261
    for v in b: h = ((h ^ v) * 16777619) & 0xffffffff
    return h
def record(sector):
    r = d[sector*512:(sector+1)*512]
    magic, version, sequence, state, length, payload_sum, header_sum = struct.unpack_from('<8s6I', r)
    assert magic == b'AIUJRN1\0' and version == 1 and state == 2 and length == 16
    assert fnv(r[:28]) == header_sum and fnv(r[32:32+length]) == payload_sum
    return sequence
assert [record(1), record(2)] == [1, 2]
PY
echo "AIUEOS_JOURNAL_DUAL_SLOT_APPEND_OK sequences=1,2"

# Corrupt the latest slot (sector 2, sequence 2). Boot must reject it, select
# sector 1 sequence 1, and recreate sequence 2 in the alternate slot.
python3 - "$out/virtio-blk-smoke.img" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
d = bytearray(p.read_bytes())
d[1024 + 12] ^= 0x80
p.write_bytes(d)
PY
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
if ! grep -F "AIUEOS_JOURNAL_RECOVERY_OK highest-valid selected alternate-slot-append" \
  "$out/kernel-serial.log" >/dev/null; then
  echo "error: prior committed slot was not selected after latest-slot corruption" >&2
  exit 1
fi
echo "AIUEOS_JOURNAL_LATEST_SLOT_FALLBACK_OK recovered=1 rewritten=2"
