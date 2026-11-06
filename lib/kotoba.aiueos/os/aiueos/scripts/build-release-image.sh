#!/bin/sh
set -eu

# JUN-942: the image's version N (the version it will be signed as: aiueos-image.py sign --version N) is required and has no default;
# the builder writes OSMETA.BIN with floor = active = N.
: "${AIUEOS_IMAGE_VERSION:?AIUEOS_IMAGE_VERSION is required (a positive integer: the version this image will be signed as)}"

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
set -- build \
  --efi "$efi" --kernel "$kernel" --initramfs "$initramfs" --data "$data_image" \
  --output "$image" --iso "$iso" --receipt "$receipt" --version "$AIUEOS_IMAGE_VERSION"
if [ -n "${AIUEOS_DISTRIBUTION_JSON:-}" ]; then
  set -- "$@" --distribution-json "$AIUEOS_DISTRIBUTION_JSON"
fi
python3 "$aiueos/scripts/make-release-image.py" "$@"
python3 "$aiueos/scripts/make-release-image.py" verify \
  --image "$image" --iso "$iso" --efi "$efi" --kernel "$kernel" \
  --initramfs "$initramfs" --version "$AIUEOS_IMAGE_VERSION"
echo "$receipt"
