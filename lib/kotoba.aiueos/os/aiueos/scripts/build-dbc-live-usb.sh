#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-dbc-live"}
probe_out="$out/probe"
core_out="$out/core"
image="$out/aiueos-k16-dbc-live-v1.img"
receipt="$out/aiueos-k16-dbc-live-v1-receipt.json"

source_commit=$(git -C "$repo" rev-parse HEAD)
if [ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ] &&
   [ "${AIUEOS_ALLOW_DIRTY_DBC_BUILD:-0}" != 1 ]; then
  echo "error: DbC live image must be built from a clean tracked tree" >&2
  exit 1
fi

mkdir -p "$out"
AIUEOS_OUT="$core_out" SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} \
  "$aiueos/scripts/build-uefi.sh" >/dev/null
AIUEOS_OUT="$probe_out" SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} \
  "$aiueos/scripts/build-dbc-probe.sh" >/dev/null
AIUEOS_SOURCE_COMMIT="$source_commit" SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} \
  python3 "$aiueos/scripts/make-physical-qualification-usb.py" build \
    --mode dbc-live \
    --probe "$probe_out/esp/EFI/BOOT/BOOTX64.EFI" \
    --loader "$core_out/esp/EFI/BOOT/BOOTX64.EFI" \
    --kernel "$core_out/esp/EFI/AIUEOS/KERNEL.ELF" \
    --initramfs "$core_out/esp/EFI/AIUEOS/INITRD.IMG" \
    --output "$image" --receipt "$receipt"
printf '%s\n' "$image"
