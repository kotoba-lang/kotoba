#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}

# Previous-version pair for the update-flow gate: built first, without the
# catalog-policy self-test compile gate, so its kernel digest and serial
# evidence are distinguishable from the current version below.
AIUEOS_INPUT_SMOKE_SYNTHETIC=1 "$aiueos/scripts/build-uefi.sh" >/dev/null
cp "$out/esp/EFI/BOOT/BOOTX64.EFI" "$out/update-previous-bootx64.efi"
cp "$out/esp/EFI/AIUEOS/KERNEL.ELF" "$out/update-previous-kernel.elf"
cp "$out/esp/EFI/AIUEOS/INITRD.IMG" "$out/update-previous-initrd.img"

# The release-image smoke uses the same explicitly test-only input event and
# catalog-policy self-test as the direct UEFI smoke. Normal release builds
# leave both compile gates disabled.
AIUEOS_INPUT_SMOKE_SYNTHETIC=1 AIUEOS_CATALOG_POLICY_SELFTEST=1 \
  "$aiueos/scripts/build-release-image.sh" >/dev/null

# Fail-closed: a single flipped byte in the embedded ISO kernel must be
# rejected by the release verifier before any boot evidence is claimed.
python3 - "$out/aiueos-x86_64.iso" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1])
corrupt = source.with_name("corrupt-release.iso")
data = bytearray(source.read_bytes())
data[23 * 2048 + 300 * 512] ^= 1
corrupt.write_bytes(data)
PY
if python3 "$aiueos/scripts/make-release-image.py" verify \
  --iso "$out/corrupt-release.iso" \
  --efi "$out/esp/EFI/BOOT/BOOTX64.EFI" \
  --kernel "$out/esp/EFI/AIUEOS/KERNEL.ELF" >/dev/null 2>&1; then
  echo "error: corrupted release ISO was not rejected by the verifier" >&2
  exit 1
fi
rm -f "$out/corrupt-release.iso"
echo "AIUEOS_RELEASE_ISO_REJECTION_OK corrupted-kernel-byte"

# Fail-closed: a flipped byte inside the recovery partition's kernel must be
# rejected by the same verifier.
python3 "$aiueos/scripts/make-release-image.py" corrupt \
  --image "$out/aiueos-x86_64-gpt.img" \
  --output "$out/corrupt-recovery.img" --target recovery-kernel >/dev/null
if python3 "$aiueos/scripts/make-release-image.py" verify \
  --image "$out/corrupt-recovery.img" \
  --efi "$out/esp/EFI/BOOT/BOOTX64.EFI" \
  --kernel "$out/esp/EFI/AIUEOS/KERNEL.ELF" >/dev/null 2>&1; then
  echo "error: corrupted recovery partition was not rejected by the verifier" >&2
  exit 1
fi
rm -f "$out/corrupt-recovery.img"
echo "AIUEOS_RECOVERY_PARTITION_REJECTION_OK corrupted-kernel-byte"

# GPT raw-disk boot. The journal smoke mutates the virtio-blk data disk, so a
# pristine copy is staged before each boot.
cp "$out/aiueos-x86_64-data.img" "$out/virtio-blk-smoke.img"
AIUEOS_DISK_IMAGE="$out/aiueos-x86_64-gpt.img" \
  AIUEOS_PRESERVE_BLK_IMAGE=1 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"

# El Torito UEFI boot from the release ISO.
cp "$out/aiueos-x86_64-data.img" "$out/virtio-blk-smoke.img"
AIUEOS_CDROM_IMAGE="$out/aiueos-x86_64.iso" \
  AIUEOS_PRESERVE_BLK_IMAGE=1 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"

# Recovery fallback: with the primary loader's PE magic corrupted, firmware
# LoadImage fails on the primary ESP and falls back to the recovery ESP. The
# only valid loader/kernel pair is on the recovery partition, so the complete
# evidence gate below proves the recovery boot path.
python3 "$aiueos/scripts/make-release-image.py" corrupt \
  --image "$out/aiueos-x86_64-gpt.img" \
  --output "$out/corrupt-primary-loader.img" --target primary-loader >/dev/null
cp "$out/aiueos-x86_64-data.img" "$out/virtio-blk-smoke.img"
AIUEOS_DISK_IMAGE="$out/corrupt-primary-loader.img" \
  AIUEOS_PRESERVE_BLK_IMAGE=1 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
rm -f "$out/corrupt-primary-loader.img"
echo "AIUEOS_RECOVERY_FALLBACK_OK primary-loader-corrupt firmware-fallback full-evidence"

# Loader-level kernel recovery: with the primary kernel corrupted, the loader
# must reject it by digest, admit the identical kernel from the recovery
# volume, and still pass the complete evidence gate.
python3 "$aiueos/scripts/make-release-image.py" corrupt \
  --image "$out/aiueos-x86_64-gpt.img" \
  --output "$out/corrupt-primary-kernel.img" --target primary-kernel >/dev/null
cp "$out/aiueos-x86_64-data.img" "$out/virtio-blk-smoke.img"
AIUEOS_DISK_IMAGE="$out/corrupt-primary-kernel.img" \
  AIUEOS_PRESERVE_BLK_IMAGE=1 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
grep -F "AIUEOS_LOADER_FAIL kernel-sha256" "$out/uefi-debug.log" >/dev/null || {
  echo "error: corrupted primary kernel was not rejected before recovery" >&2
  exit 1
}
grep -F "AIUEOS_LOADER_RECOVERY_OK kernel-from-alternate-volume sha256-v1" "$out/uefi-debug.log" >/dev/null || {
  echo "error: loader kernel recovery evidence was not observed" >&2
  exit 1
}
rm -f "$out/corrupt-primary-kernel.img"
echo "AIUEOS_RECOVERY_KERNEL_FALLBACK_OK primary-kernel-corrupt loader-fallback digest-admitted full-evidence"

# Legacy-BIOS refusal fixture: SeaBIOS executes the protective-MBR stub, which
# must print its marker and terminate deterministically through isa-debug-exit
# (status 23 = (0x0b << 1) | 1). BIOS is not a supported boot path.
qemu=${QEMU_SYSTEM_X86_64:-qemu-system-x86_64}
bios_log="$out/bios-stub-debug.log"
rm -f "$bios_log"
set +e
"$qemu" \
  -machine q35,accel=tcg -cpu max -m 128M \
  -drive "format=raw,snapshot=on,file=$out/aiueos-x86_64-gpt.img" \
  -device isa-debugcon,iobase=0xe9,chardev=debug \
  -chardev file,id=debug,path="$bios_log" \
  -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
  -display none -serial none -monitor none -no-reboot
bios_status=$?
set -e
[ "$bios_status" -eq 23 ] || {
  echo "error: BIOS stub did not exit deterministically (status $bios_status)" >&2
  test -f "$bios_log" && sed -n '1,20p' "$bios_log" >&2
  exit 1
}
grep -F "AIUEOS_BIOS_STUB uefi-required" "$bios_log" >/dev/null || {
  echo "error: BIOS stub refusal marker was not observed" >&2
  exit 1
}
echo "AIUEOS_BIOS_STUB_OK uefi-required deterministic-exit"

# Update flow: a previous-version release image receives the current
# loader/kernel pair on its primary ESP only; the recovery partition keeps the
# previous version. The updated image must boot the new version (self-test
# marker present, no recovery fallback involved).
python3 "$aiueos/scripts/make-release-image.py" build \
  --efi "$out/update-previous-bootx64.efi" \
  --kernel "$out/update-previous-kernel.elf" \
  --initramfs "$out/update-previous-initrd.img" \
  --output "$out/update-base.img" --receipt "$out/update-base-receipt.json" >/dev/null
python3 "$aiueos/scripts/make-release-image.py" apply-update \
  --image "$out/update-base.img" \
  --efi "$out/esp/EFI/BOOT/BOOTX64.EFI" \
  --kernel "$out/esp/EFI/AIUEOS/KERNEL.ELF" \
  --initramfs "$out/esp/EFI/AIUEOS/INITRD.IMG" \
  --output "$out/update-applied.img" --receipt "$out/update-receipt.json" >/dev/null
python3 "$aiueos/scripts/make-release-image.py" verify \
  --image "$out/update-applied.img" \
  --efi "$out/esp/EFI/BOOT/BOOTX64.EFI" \
  --kernel "$out/esp/EFI/AIUEOS/KERNEL.ELF" \
  --initramfs "$out/esp/EFI/AIUEOS/INITRD.IMG" \
  --recovery-efi "$out/update-previous-bootx64.efi" \
  --recovery-kernel "$out/update-previous-kernel.elf" \
  --recovery-initramfs "$out/update-previous-initrd.img" >/dev/null
cp "$out/aiueos-x86_64-data.img" "$out/virtio-blk-smoke.img"
AIUEOS_DISK_IMAGE="$out/update-applied.img" \
  AIUEOS_PRESERVE_BLK_IMAGE=1 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
! grep -F "AIUEOS_LOADER_RECOVERY_OK" "$out/uefi-debug.log" >/dev/null || {
  echo "error: updated image booted through recovery instead of its primary" >&2
  exit 1
}
echo "AIUEOS_UPDATE_APPLY_OK new-version-booted recovery-preserved receipt=update-receipt.json"

# Rollback: corrupting the updated primary loader must boot the preserved
# previous version from the recovery partition (self-test marker absent).
python3 "$aiueos/scripts/make-release-image.py" corrupt \
  --image "$out/update-applied.img" \
  --output "$out/update-rollback.img" --target primary-loader >/dev/null
cp "$out/aiueos-x86_64-data.img" "$out/virtio-blk-smoke.img"
AIUEOS_DISK_IMAGE="$out/update-rollback.img" \
  AIUEOS_PRESERVE_BLK_IMAGE=1 \
  AIUEOS_EXPECT_CATALOG_POLICY_SELFTEST=0 \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
rm -f "$out/update-base.img" "$out/update-applied.img" "$out/update-rollback.img"
echo "AIUEOS_UPDATE_ROLLBACK_OK previous-version-recovered firmware-fallback full-evidence"

# Release signing: prove the stdlib RSA-2048 PKCS#1 v1.5 SHA-256 verifier
# accepts a signature over the build receipt and rejects a tampered receipt.
# The CI key is ephemeral; the production key never enters the repository, so
# real release signatures are produced offline against the same verifier.
openssl genrsa -out "$out/release-ci-key.pem" 2048 2>/dev/null
openssl rsa -in "$out/release-ci-key.pem" -pubout \
  -out "$out/release-ci-pub.pem" 2>/dev/null
openssl dgst -sha256 -sign "$out/release-ci-key.pem" \
  -out "$out/aiueos-x86_64-build-receipt.sig" \
  "$out/aiueos-x86_64-build-receipt.json"
python3 "$aiueos/scripts/verify-release-signature.py" \
  --receipt "$out/aiueos-x86_64-build-receipt.json" \
  --signature "$out/aiueos-x86_64-build-receipt.sig" \
  --public-key "$out/release-ci-pub.pem"
cp "$out/aiueos-x86_64-build-receipt.json" "$out/tampered-receipt.json"
printf '\n' >> "$out/tampered-receipt.json"
if python3 "$aiueos/scripts/verify-release-signature.py" \
  --receipt "$out/tampered-receipt.json" \
  --signature "$out/aiueos-x86_64-build-receipt.sig" \
  --public-key "$out/release-ci-pub.pem" >/dev/null 2>&1; then
  echo "error: tampered receipt was not rejected by the signature verifier" >&2
  exit 1
fi
rm -f "$out/release-ci-key.pem" "$out/tampered-receipt.json"
echo "AIUEOS_RELEASE_SIGNING_OK rsa2048-pkcs1-sha256 receipt-signed tamper-rejected"
echo "AIUEOS_RELEASE_MEDIA_SMOKE_OK gpt iso recovery loader-kernel-recovery bios-stub update-rollback signed-receipt"
