#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
amu=${1:?usage: smoke-qemu-kotoba-native-overlap.sh /path/to/amu}
if [ -n "${AIUEOS_NATIVE_OVERLAP_WORK:-}" ]; then
  tmp=$AIUEOS_NATIVE_OVERLAP_WORK
  mkdir -p "$tmp"
else
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-overlap.XXXXXX")
  trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fi
source="$tmp/kernel-overlap.kotoba"

# Mechanical mutation: the second allocation returns the already-owned first
# page. The kernel must reject it before deriving or zeroing a second region.
needle='(+ physical-start 4096)'
replacement='physical-start'
grep -F "$needle" "$aiueos/native/kernel.kotoba" >/dev/null
sed "s/$needle/$replacement/" "$aiueos/native/kernel.kotoba" >"$source"
grep -F "$needle" "$source" >/dev/null && {
  echo "error: allocator overlap mutation did not apply" >&2; exit 1;
}

if [ "${AIUEOS_NATIVE_OVERLAP_BUILD_ONLY:-0}" = 1 ]; then
  AIUEOS_NATIVE_PROFILE=kernel \
  AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
  AIUEOS_NATIVE_OUT="$tmp/native" \
  AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
    "$aiueos/scripts/build-kotoba-native-boot.sh" "$amu"
  echo "AIUEOS_KOTOBA_NATIVE_OVERLAP_BUILD_OK out=$tmp/boot"
  exit 0
fi

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS=41 \
AIUEOS_NATIVE_EXPECT_MARKER=M \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$amu"
