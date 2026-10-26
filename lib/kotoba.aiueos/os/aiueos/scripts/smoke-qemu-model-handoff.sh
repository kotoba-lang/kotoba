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

work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-model-handoff-smoke.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir -p "$work/esp/EFI/BOOT" "$work/esp/EFI/AIUEOS"
# AIUEOS_MODEL_PROFILE=bonsai2 boots the two-part B2P0..1 split (ADR-0222
# step 5); the default is the three-part qwen38 Q38P0..2 split (ADR-0117).
profile=${AIUEOS_MODEL_PROFILE:-qwen38}
case "$profile" in
  qwen38) name=qwen38-27b prefix=Q38P parts=3 ;;
  bonsai2) name=bonsai2-27b prefix=B2P parts=2 ;;
  *) echo "error: AIUEOS_MODEL_PROFILE must be qwen38 or bonsai2" >&2; exit 1 ;;
esac
python3 - "$work/esp/EFI/AIUEOS" "$prefix" "$parts" <<'PY'
from pathlib import Path
import sys
root, prefix, parts = Path(sys.argv[1]), sys.argv[2], int(sys.argv[3])
bodies = [b"GGUF\x03\x00\x00\x00fixture", b"weights", b"tokens-v1"][:parts]
for i, body in enumerate(bodies):
    (root / f"{prefix}{i}.BIN").write_bytes(body)
PY
part0=$(wc -c < "$work/esp/EFI/AIUEOS/${prefix}0.BIN" | tr -d ' ')
part1=$(wc -c < "$work/esp/EFI/AIUEOS/${prefix}1.BIN" | tr -d ' ')
part2=0
[ "$parts" = 2 ] || part2=$(wc -c < "$work/esp/EFI/AIUEOS/${prefix}2.BIN" | tr -d ' ')
total=$((part0 + part1 + part2))
fixture_sha=$(cat "$work/esp/EFI/AIUEOS/${prefix}"?.BIN | shasum -a 256 | awk '{print $1}')

AIUEOS_OUT="$work/release" \
AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD=1 \
AIUEOS_QWEN38_MODEL_HANDOFF=1 \
AIUEOS_MODEL_TEST_FIXTURE=1 \
AIUEOS_MODEL_PROFILE="$profile" \
AIUEOS_MODEL_TOTAL_BYTES="$total" \
AIUEOS_MODEL_PART0_BYTES="$part0" \
AIUEOS_MODEL_PART1_BYTES="$part1" \
AIUEOS_MODEL_PART2_BYTES="$part2" \
AIUEOS_MODEL_SHA256="$fixture_sha" \
AIUEOS_MODEL_MIN_ADDRESS=1073741824 \
AIUEOS_MODEL_MAX_ADDRESS=2147483647 \
AIUEOS_PERSISTENT_BOOT=1 SOURCE_DATE_EPOCH=0 \
  "$aiueos/scripts/build-physical-qualification-pxe.sh" >/dev/null
cp "$work/release/aiueos-k16-native-pxe.efi" "$work/esp/EFI/BOOT/BOOTX64.EFI"
cp "$OVMF_VARS" "$work/vars.fd"
if [ "${AIUEOS_MODEL_CORRUPT:-0}" = 1 ]; then
  python3 - "$work/esp/EFI/AIUEOS/${prefix}1.BIN" <<'PY'
from pathlib import Path
import sys
path = Path(sys.argv[1])
data = bytearray(path.read_bytes())
data[-1] ^= 1
path.write_bytes(data)
PY
fi

set +e
"$timeout_cmd" 60 "$qemu" -machine q35,accel=tcg -cpu max -m 1536M -smp 2 \
  -drive "if=pflash,format=raw,readonly=on,file=$OVMF_CODE" \
  -drive "if=pflash,format=raw,file=$work/vars.fd" \
  -drive "format=raw,file=fat:rw:$work/esp" \
  -display none -serial "file:$work/native.serial" \
  -debugcon "file:$work/native.debug" -global isa-debugcon.iobase=0xe9 \
  -monitor none -no-reboot >/dev/null 2>&1
rc=$?
set -e
if [ "${AIUEOS_MODEL_CORRUPT:-0}" = 1 ]; then
  grep -F "AIUEOS_LOADER_FAIL qwen38-model-admission code=121" \
    "$work/native.debug" >/dev/null || {
    echo "error: corrupt split model was not refused by the UEFI loader" >&2
    tail -80 "$work/native.debug" >&2 || true
    exit 1
  }
  if grep -F "AIUEOS_MODEL_HANDOFF_OK" "$work/native.debug" >/dev/null; then
    echo "error: corrupt split model reached the native kernel" >&2; exit 1
  fi
  printf '%s\n' \
    "AIUEOS_QWEN38_MODEL_HANDOFF_QEMU_REFUSAL_OK profile=$profile reason=sha256-mismatch kernel-entry=none"
  exit 0
fi
[ "$rc" -eq 124 ] || { echo "error: model handoff guest did not remain running (rc=$rc)" >&2; exit 1; }
for marker in \
  "AIUEOS_LOADER_MODEL_OK $name gguf-v3 parts=$parts sha256=verified" \
  "AIUEOS_MODEL_HANDOFF_OK format=gguf-v3 parts=$parts sha256=verified mapping=read-only-nx metrics=N/A" \
  "AIUEOS_PHYSICAL_MODEL_HANDOFF_OK $name runtime=not-yet-present internal-disk-writes=none"; do
  grep -F "$marker" "$work/native.debug" >/dev/null || {
    echo "error: model handoff evidence is absent: $marker" >&2
    tail -80 "$work/native.debug" >&2 || true
    exit 1
  }
done
if grep -F "AIUEOS_MODEL_HANDOFF_FAIL" "$work/native.debug" >/dev/null; then
  echo "error: kernel refused the admitted model" >&2; exit 1
fi
printf '%s\n' \
  "AIUEOS_QWEN38_MODEL_HANDOFF_QEMU_OK profile=$profile parts=$parts source=split-fat32 mapping=read-only-nx generation=not-yet-present physical-k16=unverified"
