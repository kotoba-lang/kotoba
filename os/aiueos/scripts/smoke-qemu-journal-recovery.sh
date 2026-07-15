#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}

"$aiueos/scripts/smoke-qemu-uefi.sh"
# Model a reset after the sequence-1 journal commit but with a missing/torn
# object materialization. The next boot must redo the committed payload before
# it is allowed to append sequence 2.
python3 - "$out/virtio-blk-smoke.img" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
d = bytearray(p.read_bytes())
d[3*512:4*512] = bytes(512)
p.write_bytes(d)
PY
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
grep -F "AIUEOS_JOURNAL_RECOVERY_OK highest-valid selected alternate-slot-append" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: committed journal head was not selected on the second boot" >&2
  exit 1
}
grep -F "AIUEOS_OBJECT_TXN_REPLAY_OK committed-redo idempotent-before-append" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: committed object transaction was not replayed before append" >&2
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
    assert magic == b'AIUJRN2\0' and version == 2 and state == 2 and length == 32
    assert fnv(r[:28]) == header_sum and fnv(r[32:32+length]) == payload_sum
    return sequence
assert [record(1), record(2)] == [1, 2]
o = d[3*512:4*512]
magic, version, sequence, length, checksum = struct.unpack_from('<8s4I', o)
assert (magic, version, sequence, length) == (b'AIUOBJ1\0', 1, 2, 16)
assert o[24:40] == b'KOTOBASE-OBJ-002' and fnv(o[24:40]) == checksum
PY
echo "AIUEOS_OBJECT_STORE_TRANSACTION_OK journal=2 object=2 payload=KOTOBASE-OBJ-002"

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
python3 - "$out/virtio-blk-smoke.img" <<'PY'
from pathlib import Path
import struct, sys
d = Path(sys.argv[1]).read_bytes()
o = d[3*512:4*512]
magic, version, sequence, length, checksum = struct.unpack_from('<8s4I', o)
def fnv(b):
    h = 2166136261
    for v in b: h = ((h ^ v) * 16777619) & 0xffffffff
    return h
assert (magic, version, sequence, length) == (b'AIUOBJ1\0', 1, 2, 16)
assert o[24:40] == b'KOTOBASE-OBJ-002' and fnv(o[24:40]) == checksum
PY
echo "AIUEOS_OBJECT_STORE_ROLLBACK_REDO_OK fallback=1 object=2"
