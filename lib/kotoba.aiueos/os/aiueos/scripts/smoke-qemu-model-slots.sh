#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
timeout_cmd=$(command -v timeout || command -v gtimeout || true)
[ -n "$timeout_cmd" ] || { echo "error: timeout or gtimeout is required" >&2; exit 1; }
command -v "$qemu" >/dev/null 2>&1 || { echo "error: qemu-system-x86_64 is required" >&2; exit 1; }

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
[ -f "${OVMF_VARS:-}" ] || { echo "error: OVMF vars not found" >&2; exit 1; }

work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-model-slots-qemu.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir -p "$work/esp/EFI/BOOT" "$work/esp/EFI/AIUEOS"
python3 "$aiueos/scripts/model-slot-disk.py" create \
  --output "$work/nvme.raw" --disk-bytes 134217728 --slot-bytes 33554432 >/dev/null

make_parts() {
  revision=$1
  python3 - "$work/esp/EFI/AIUEOS" "$revision" <<'PY'
from pathlib import Path
import sys
root, revision = Path(sys.argv[1]), sys.argv[2].encode()
(root / "Q38P0.BIN").write_bytes(b"GGUF\x03\0\0\0" + revision + b"-metadata")
(root / "Q38P1.BIN").write_bytes(revision + b"-weights-" + bytes(range(251)))
(root / "Q38P2.BIN").write_bytes(revision + b"-tokenizer")
PY
}

build_importer() {
  label=$1
  part0=$(wc -c < "$work/esp/EFI/AIUEOS/Q38P0.BIN" | tr -d ' ')
  part1=$(wc -c < "$work/esp/EFI/AIUEOS/Q38P1.BIN" | tr -d ' ')
  part2=$(wc -c < "$work/esp/EFI/AIUEOS/Q38P2.BIN" | tr -d ' ')
  total=$((part0 + part1 + part2))
  digest=$(cat "$work/esp/EFI/AIUEOS/Q38P0.BIN" \
               "$work/esp/EFI/AIUEOS/Q38P1.BIN" \
               "$work/esp/EFI/AIUEOS/Q38P2.BIN" | shasum -a 256 | awk '{print $1}')
  AIUEOS_OUT="$work/build-$label" AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD=1 \
  AIUEOS_MODEL_NVME_SLOTS=1 AIUEOS_MODEL_SLOT_IMPORT_EXIT=1 \
  AIUEOS_MODEL_TEST_FIXTURE=1 AIUEOS_MODEL_TOTAL_BYTES="$total" \
  AIUEOS_MODEL_PART0_BYTES="$part0" AIUEOS_MODEL_PART1_BYTES="$part1" \
  AIUEOS_MODEL_PART2_BYTES="$part2" AIUEOS_MODEL_SHA256="$digest" \
  AIUEOS_PERSISTENT_BOOT=1 SOURCE_DATE_EPOCH=0 \
    "$aiueos/scripts/build-physical-qualification-pxe.sh" >/dev/null
  cp "$work/build-$label/aiueos-k16-native-pxe.efi" "$work/esp/EFI/BOOT/BOOTX64.EFI"
}

run_importer() {
  label=$1
  cp "$OVMF_VARS" "$work/vars-$label.fd"
  set +e
  "$timeout_cmd" 30 "$qemu" -machine q35,accel=tcg -cpu max -m 1536M -smp 2 \
    -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
    -drive "if=pflash,format=raw,file=$work/vars-$label.fd" \
    -drive "format=raw,file=fat:rw:$work/esp" \
    -drive "if=none,id=nvme0,format=raw,file=$work/nvme.raw" \
    -device "nvme,drive=nvme0,serial=AIUEOSMODEL01" \
    -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
    -display none -serial "file:$work/$label.serial" \
    -debugcon "file:$work/$label.debug" -global isa-debugcon.iobase=0xe9 \
    -monitor none -no-reboot >/dev/null 2>&1
  rc=$?
  set -e
  [ "$rc" -ne 124 ] || {
    echo "error: $label importer timed out" >&2
    tail -100 "$work/$label.debug" >&2 || true
    exit 1
  }
}

run_without_target() {
  label=$1
  cp "$OVMF_VARS" "$work/vars-$label.fd"
  set +e
  "$timeout_cmd" 30 "$qemu" -machine q35,accel=tcg -cpu max -m 1536M -smp 2 \
    -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
    -drive "if=pflash,format=raw,file=$work/vars-$label.fd" \
    -drive "format=raw,file=fat:rw:$work/esp" \
    -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
    -display none -serial "file:$work/$label.serial" \
    -debugcon "file:$work/$label.debug" -global isa-debugcon.iobase=0xe9 \
    -monitor none -no-reboot >/dev/null 2>&1
  rc=$?
  set -e
  [ "$rc" -ne 124 ] || {
    echo "error: $label importer timed out" >&2
    tail -100 "$work/$label.debug" >&2 || true
    exit 1
  }
}

make_parts old
build_importer old
run_importer old
grep -F "AIUEOS_MODEL_SLOT_OK source=usb target=nvme layout=ab readback=sha256 activation=atomic" \
  "$work/old.debug" >/dev/null || { tail -100 "$work/old.debug" >&2; exit 1; }
python3 "$aiueos/scripts/model-slot-disk.py" inspect --image "$work/nvme.raw" > "$work/old.json"
python3 - "$work/old.json" <<'PY'
import json, sys
value=json.load(open(sys.argv[1]))
assert value["active"]["slot"] == 0 and value["active"]["generation"] == 1
PY
old_sector_sha=$(dd if="$work/nvme.raw" bs=512 skip=$((2048 + 2048)) count=1 2>/dev/null | shasum -a 256 | awk '{print $1}')

make_parts new
build_importer new
run_importer new
python3 "$aiueos/scripts/model-slot-disk.py" inspect --image "$work/nvme.raw" > "$work/new.json"
python3 - "$work/new.json" <<'PY'
import json, sys
value=json.load(open(sys.argv[1]))
assert value["active"]["slot"] == 1 and value["active"]["generation"] == 2
PY
[ "$old_sector_sha" = "$(dd if="$work/nvme.raw" bs=512 skip=$((2048 + 2048)) count=1 2>/dev/null | shasum -a 256 | awk '{print $1}')" ] || {
  echo "error: slot A changed while activating slot B" >&2; exit 1;
}

make_parts corrupt
build_importer corrupt
python3 - "$work/esp/EFI/AIUEOS/Q38P1.BIN" <<'PY'
from pathlib import Path
import sys
path=Path(sys.argv[1]); data=bytearray(path.read_bytes()); data[-1] ^= 1; path.write_bytes(data)
PY
run_importer corrupt
grep -F "AIUEOS_LOADER_FAIL model-nvme-slot-import code=122" "$work/corrupt.debug" >/dev/null || {
  tail -100 "$work/corrupt.debug" >&2; exit 1;
}
python3 "$aiueos/scripts/model-slot-disk.py" inspect --image "$work/nvme.raw" > "$work/after-corrupt.json"
python3 - "$work/after-corrupt.json" <<'PY'
import json, sys
value=json.load(open(sys.argv[1]))
assert value["active"]["slot"] == 1 and value["active"]["generation"] == 2
PY

part0=$(wc -c < "$work/esp/EFI/AIUEOS/Q38P0.BIN" | tr -d ' ')
part1=$(wc -c < "$work/esp/EFI/AIUEOS/Q38P1.BIN" | tr -d ' ')
part2=$(wc -c < "$work/esp/EFI/AIUEOS/Q38P2.BIN" | tr -d ' ')
total=$((part0 + part1 + part2))
digest=$(cat "$work/esp/EFI/AIUEOS/Q38P0.BIN" \
             "$work/esp/EFI/AIUEOS/Q38P1.BIN" \
             "$work/esp/EFI/AIUEOS/Q38P2.BIN" | shasum -a 256 | awk '{print $1}')
AIUEOS_OUT="$work/build-deferred" AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD=1 \
AIUEOS_MODEL_NVME_SLOTS=1 AIUEOS_MODEL_NVME_TARGET_OPTIONAL=1 \
AIUEOS_MODEL_SLOT_IMPORT_EXIT=1 AIUEOS_MODEL_TEST_FIXTURE=1 \
AIUEOS_MODEL_TOTAL_BYTES="$total" AIUEOS_MODEL_PART0_BYTES="$part0" \
AIUEOS_MODEL_PART1_BYTES="$part1" AIUEOS_MODEL_PART2_BYTES="$part2" \
AIUEOS_MODEL_SHA256="$digest" AIUEOS_PERSISTENT_BOOT=1 SOURCE_DATE_EPOCH=0 \
  "$aiueos/scripts/build-physical-qualification-pxe.sh" >/dev/null
cp "$work/build-deferred/aiueos-k16-native-pxe.efi" "$work/esp/EFI/BOOT/BOOTX64.EFI"
run_without_target deferred
grep -F "AIUEOS_MODEL_SLOT_DEFERRED target=dedicated-nvme-partition reason=absent internal-disk-write=none" \
  "$work/deferred.debug" >/dev/null || { tail -100 "$work/deferred.debug" >&2; exit 1; }
grep -F "AIUEOS_MODEL_SLOT_IMPORT_TEST_EXIT" "$work/deferred.debug" >/dev/null || {
  tail -100 "$work/deferred.debug" >&2; exit 1;
}

echo "AIUEOS_MODEL_SLOTS_QEMU_OK transport=usb target=nvme layout=ab generations=1,2 corrupt-update=last-known-good target-absent=deferred"
