#!/bin/sh
set -eu

: "${AIUEOS_KERNEL:?set AIUEOS_KERNEL to a Linux kernel image}"
: "${AIUEOS_SYSTEM:?set AIUEOS_SYSTEM to system.aiueos.edn}"

ARCH="${AIUEOS_ARCH:-aarch64}"
OUT="${AIUEOS_INITRAMFS:-target/aiueos.initramfs.cpio.gz}"

scripts/build-linux-bundle.sh "$ARCH"
kbb -M -m aiueos.launcher image build "$AIUEOS_SYSTEM" \
  --jre-dir target/jre-linux --runtime-root target/linux-runtime-root \
  --jar target/aiueos-standalone.jar --out "$OUT" \
  --shutdown-after-boot
kbb -M -m aiueos.launcher vm boot --arch "$ARCH" \
  --kernel "$AIUEOS_KERNEL" --initramfs "$OUT"
