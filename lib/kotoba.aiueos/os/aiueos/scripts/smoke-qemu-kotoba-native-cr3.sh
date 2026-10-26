#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-native-cr3.sh /path/to/compiler}
if [ -n "${AIUEOS_NATIVE_CR3_WORK:-}" ]; then
  tmp=$AIUEOS_NATIVE_CR3_WORK
  mkdir -p "$tmp"
else
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-cr3.XXXXXX")
  trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fi
source="$tmp/kernel-cr3.kotoba"

# Mechanical mutation: keep the firmware CR3 active.  Page-table construction
# still succeeds, but readback must reject this before publishing P/R/C.
needle='(kernel-write-cr3 pml4)'
replacement='(kernel-write-cr3 (kernel-read-cr3))'
[ "$(grep -F -c "$needle" "$aiueos/native/kernel.kotoba")" = 1 ] || {
  echo "error: CR3 mutation source is ambiguous" >&2; exit 1;
}
sed "s/$needle/$replacement/" "$aiueos/native/kernel.kotoba" >"$source"
grep -F "$needle" "$source" >/dev/null && {
  echo "error: CR3 mutation did not apply" >&2; exit 1;
}

if [ "${AIUEOS_NATIVE_CR3_BUILD_ONLY:-0}" = 1 ]; then
  AIUEOS_NATIVE_PROFILE=kernel \
  AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
  AIUEOS_NATIVE_OUT="$tmp/native" \
  AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
    "$aiueos/scripts/build-kotoba-native-boot.sh" "$compiler"
  echo "AIUEOS_KOTOBA_NATIVE_CR3_BUILD_OK out=$tmp/boot"
  exit 0
fi

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS=49 \
AIUEOS_NATIVE_EXPECT_MARKER=M \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$compiler"
