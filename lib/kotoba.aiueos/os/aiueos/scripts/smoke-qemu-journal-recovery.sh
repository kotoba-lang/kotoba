#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}

# Since 54ac566 (S4, JUN-144) a normal boot ends in the persistent desktop
# loop instead of exiting the machine (aiueos#436). This gate's evidence is
# complete at AIUEOS_DESKTOP_LOOP_OK, so every boot below opts in to being
# ended and scored there; boots that exit earlier (corruption, crash, fault)
# are unaffected because they never reach the loop.
export AIUEOS_LOOP_EXIT_OK=1
# And the smoke-profile kernel re-arms the end-of-boot #UD probe (aiueos#436)
# so the terminal evidence -- AIUEOS_EXCEPTION_OK vector=6 invalid-opcode and
# the isa-debug-exit status 97 the harness asserts -- is produced exactly as
# before 54ac566. With this profile the probe ends the boot before the loop,
# so the loop-exit scoring above stays as the fallback for default-profile
# boots; both mechanisms are inert unless their marker appears.
export AIUEOS_SMOKE_FINAL_PROBE=1

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
grep -F "AIUEOS_PERSISTENT_SERVICE_BOOTSTRAP_OK registry=replayed kotoba-spawn=2 generation=2,1" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: replayed service registry did not drive scheduler bootstrap" >&2
  exit 1
}
grep -F "AIUEOS_KOTOBA_OBJECT_REPLAY_OK domains=4,5 journals=44-47 objects=42,43" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: domain-owned object journals were not replayed" >&2
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
registry = b'SRV1\x01\x02\x00\x00\x01\x02\x01\x02\x01\x00\x00\x00'
assert (magic, version, sequence, length) == (b'AIUOBJ1\0', 2, 2, 16)
assert o[24:40] == registry and fnv(o[24:40]) == checksum
for first, target, domain in ((44, 42, 4), (46, 43, 5)):
    assert [record(first), record(first + 1)] == [1, 2]
    u = d[target*512:(target+1)*512]
    magic, version, sequence, length, checksum = struct.unpack_from('<8s4I', u)
    payload = u[24:40]
    assert (magic, version, sequence, length) == (b'AIUOBJ1\0', 3, 2, 16)
    assert payload[:6] == b'USR1\x01' + bytes([domain])
    assert struct.unpack_from('<I', payload, 8)[0] == 42
    assert fnv(payload) == checksum
PY
echo "AIUEOS_SERVICE_REGISTRY_REPLAY_OK journal=2 object=2 generation=2,1"
echo "AIUEOS_KOTOBA_OBJECT_REPLAY_OK journals=44-47 objects=42,43 sequence=2 value=42"

# Corrupt the latest slot (sector 2, sequence 2). Boot must reject it, select
# sector 1 sequence 1, and recreate sequence 2 in the alternate slot.
python3 - "$out/virtio-blk-smoke.img" <<'PY'
from pathlib import Path
import sys
p = Path(sys.argv[1])
d = bytearray(p.read_bytes())
d[1024 + 12] ^= 0x80
# Corrupt domain 4's latest journal payload checksum as an independent
# fixed-stack Kotoba validator rejection gate.
d[45*512 + 24] ^= 0x40
p.write_bytes(d)
PY
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
if ! grep -F "AIUEOS_JOURNAL_RECOVERY_OK highest-valid selected alternate-slot-append" \
  "$out/kernel-serial.log" >/dev/null; then
  echo "error: prior committed slot was not selected after latest-slot corruption" >&2
  exit 1
fi
grep -F "AIUEOS_PERSISTENT_SERVICE_BOOTSTRAP_OK registry=replayed kotoba-spawn=2 generation=2,1" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: fallback registry did not drive scheduler bootstrap" >&2
  exit 1
}
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
registry = b'SRV1\x01\x02\x00\x00\x01\x02\x01\x02\x01\x00\x00\x00'
assert (magic, version, sequence, length) == (b'AIUOBJ1\0', 2, 2, 16)
assert o[24:40] == registry and fnv(o[24:40]) == checksum
u = d[42*512:43*512]
magic, version, sequence, length, checksum = struct.unpack_from('<8s4I', u)
assert (magic, version, sequence, length) == (b'AIUOBJ1\0', 3, 2, 16)
assert struct.unpack_from('<I', u, 32)[0] == 42 and fnv(u[24:40]) == checksum
PY
echo "AIUEOS_SERVICE_REGISTRY_ROLLBACK_REDO_OK fallback=1 object=2"
echo "AIUEOS_KOTOBA_USER_JOURNAL_REJECTION_OK domain=4 fallback=1 rewritten=2"

# Rebuild a clean signed fixture for each independent admission mutation.
# A changed payload or signature must be detected and restored from the
# initramfs recovery materials; a changed catalog stays fail-closed.
AIUEOS_CORRUPT_KOTOBA_APP=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
AIUEOS_CORRUPT_KOTOBA_SIGNATURE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
AIUEOS_CORRUPT_KOTOBA_CATALOG=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
echo "AIUEOS_KOTOBA_APP_CORRUPTION_GATES_OK digest=restored signature=restored catalog=rejected"

# Crash receipt: a kernel with the test-only synthetic panic persists a
# durable, checksummed crash record (write + readback) and terminates. The
# next boot, built without the trigger, must consume that record, report it,
# and still pass the complete evidence gate.
AIUEOS_CRASH_RECEIPT_SMOKE=1 AIUEOS_EXPECT_CRASH=1 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
grep -F "AIUEOS_CRASH_RECEIPT_OK reason=42 journal-context consumed readback" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: pending crash receipt was not consumed and reported on reboot" >&2
  exit 1
}
echo "AIUEOS_CRASH_RECEIPT_SMOKE_OK panic-boot receipt-consumed full-evidence"

# Fault-context crash capture: an unexpected exception before the end-of-boot
# probe must write the crash receipt over the polled, try-lock transport and
# terminate; the next boot must consume and report the fault reason while
# still passing the complete evidence gate.
AIUEOS_FAULT_RECEIPT_SMOKE=1 AIUEOS_EXPECT_FAULT=1 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
AIUEOS_PRESERVE_BLK_IMAGE=1 "$aiueos/scripts/smoke-qemu-uefi.sh"
grep -F "AIUEOS_CRASH_RECEIPT_OK reason=6 fault-context consumed readback" \
  "$out/kernel-serial.log" >/dev/null || {
  echo "error: pending fault receipt was not consumed and reported on reboot" >&2
  exit 1
}
echo "AIUEOS_FAULT_RECEIPT_SMOKE_OK fault-boot polled-receipt-consumed full-evidence"
