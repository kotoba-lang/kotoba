#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-native-page-table.sh /path/to/compiler}
if [ -n "${AIUEOS_NATIVE_PAGE_TABLE_WORK:-}" ]; then
  tmp=$AIUEOS_NATIVE_PAGE_TABLE_WORK
  mkdir -p "$tmp"
else
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-page-table.XXXXXX")
  trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fi
source="$tmp/kernel-page-table.kotoba"

# Mechanical mutation: map the guard page while leaving the independent
# readback expectation at zero. Validation must stop before loading CR3.
needle='(store64-page page offset 0)'
replacement='(store64-page page offset (+ physical 3))'
[ "$(grep -F -c "$needle" "$aiueos/native/kernel.kotoba")" = 1 ] || {
  echo "error: page-table mutation source is ambiguous" >&2; exit 1;
}
sed "s/$needle/$replacement/" "$aiueos/native/kernel.kotoba" >"$source"
grep -F "$needle" "$source" >/dev/null && {
  echo "error: page-table mutation did not apply" >&2; exit 1;
}

if [ "${AIUEOS_NATIVE_PAGE_TABLE_BUILD_ONLY:-0}" = 1 ]; then
  AIUEOS_NATIVE_PROFILE=kernel \
  AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
  AIUEOS_NATIVE_OUT="$tmp/native" \
  AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
    "$aiueos/scripts/build-kotoba-native-boot.sh" "$compiler"
  echo "AIUEOS_KOTOBA_NATIVE_PAGE_TABLE_BUILD_OK out=$tmp/boot"
  exit 0
fi

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS=47 \
AIUEOS_NATIVE_EXPECT_MARKER=M \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$compiler"
