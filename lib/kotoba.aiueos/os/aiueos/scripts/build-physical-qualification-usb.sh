#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-qualification"}
probe_out="$out/probe"
core_out="$out/core"
image="$out/aiueos-k16-physical-qualification.img"
receipt="$out/aiueos-k16-physical-qualification-receipt.json"

source_commit=$(git -C "$repo" rev-parse HEAD)
if [ -n "$(git -C "$repo" status --porcelain --untracked-files=no)" ] &&
   [ "${AIUEOS_ALLOW_DIRTY_QUALIFICATION_BUILD:-0}" != 1 ]; then
  echo "error: qualification release must be built from a clean tracked tree" >&2
  exit 1
fi

mkdir -p "$out"
AIUEOS_OUT="$core_out" AIUEOS_PHYSICAL_QUALIFICATION=1 \
  SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} "$aiueos/scripts/build-uefi.sh" >/dev/null
AIUEOS_OUT="$probe_out" SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} \
  "$aiueos/scripts/build-hw-probe.sh" >/dev/null
AIUEOS_SOURCE_COMMIT="$source_commit" SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} \
  python3 "$aiueos/scripts/make-physical-qualification-usb.py" build \
    --probe "$probe_out/esp/EFI/BOOT/BOOTX64.EFI" \
    --loader "$core_out/esp/EFI/BOOT/BOOTX64.EFI" \
    --kernel "$core_out/esp/EFI/AIUEOS/KERNEL.ELF" \
    --initramfs "$core_out/esp/EFI/AIUEOS/INITRD.IMG" \
    --output "$image" --receipt "$receipt"
printf '%s\n' "$image"
