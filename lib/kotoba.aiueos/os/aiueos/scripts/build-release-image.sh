#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
efi="$out/esp/EFI/BOOT/BOOTX64.EFI"
kernel="$out/esp/EFI/AIUEOS/KERNEL.ELF"
initramfs="$out/esp/EFI/AIUEOS/INITRD.IMG"
image="$out/aiueos-x86_64-gpt.img"
iso="$out/aiueos-x86_64.iso"
receipt="$out/aiueos-x86_64-build-receipt.json"
data_image="$out/aiueos-x86_64-data.img"

"$aiueos/scripts/build-uefi.sh" >/dev/null
python3 "$aiueos/scripts/make-aiuefs-image.py" \
  --entry "app/hello,$aiueos/kotoba/user-smoke.elf,$aiueos/kotoba/user-smoke.sig" \
  --entry "app/worker,$aiueos/kotoba/user-smoke.elf,$aiueos/kotoba/user-smoke.sig" \
  --catalog-signature "$aiueos/kotoba/app-catalog.sig" --output "$data_image"
python3 "$aiueos/scripts/make-release-image.py" build \
  --efi "$efi" --kernel "$kernel" --initramfs "$initramfs" --data "$data_image" \
  --output "$image" --iso "$iso" --receipt "$receipt"
python3 "$aiueos/scripts/make-release-image.py" verify \
  --image "$image" --iso "$iso" --efi "$efi" --kernel "$kernel" \
  --initramfs "$initramfs"
echo "$receipt"
