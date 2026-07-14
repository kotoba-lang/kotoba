#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
efi="$out/esp/EFI/BOOT/BOOTX64.EFI"
kernel="$out/esp/EFI/AIUEOS/KERNEL.ELF"
image="$out/aiueos-x86_64-gpt.img"
receipt="$out/aiueos-x86_64-build-receipt.json"

"$aiueos/scripts/build-uefi.sh" >/dev/null
python3 "$aiueos/scripts/make-release-image.py" build \
  --efi "$efi" --kernel "$kernel" --output "$image" --receipt "$receipt"
python3 "$aiueos/scripts/make-release-image.py" verify \
  --image "$image" --efi "$efi" --kernel "$kernel"
echo "$receipt"
