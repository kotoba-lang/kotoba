#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-native-wx.sh /path/to/compiler}
if [ -n "${AIUEOS_NATIVE_WX_WORK:-}" ]; then
  tmp=$AIUEOS_NATIVE_WX_WORK
  mkdir -p "$tmp"
else
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-wx.XXXXXX")
  trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fi
source="$tmp/kernel-wx.kotoba"

# Mechanical mutation: make every admitted kernel text leaf writable while
# leaving its independent P-only readback intact. Validation must stop before
# CR3 activation, so an invalid W+X table never becomes hardware authority.
needle='(store64-page page offset (+ physical 1))'
replacement='(store64-page page offset (+ physical 3))'
[ "$(grep -F -c "$needle" "$aiueos/native/kernel.kotoba")" = 1 ] || {
  echo "error: W^X mutation source is ambiguous" >&2; exit 1;
}
sed "s/$needle/$replacement/" "$aiueos/native/kernel.kotoba" >"$source"
grep -F "$needle" "$source" >/dev/null && {
  echo "error: W^X mutation did not apply" >&2; exit 1;
}

if [ "${AIUEOS_NATIVE_WX_BUILD_ONLY:-0}" = 1 ]; then
  AIUEOS_NATIVE_PROFILE=kernel \
  AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
  AIUEOS_NATIVE_OUT="$tmp/native" \
  AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
    "$aiueos/scripts/build-kotoba-native-boot.sh" "$compiler"
  echo "AIUEOS_KOTOBA_NATIVE_WX_BUILD_OK out=$tmp/boot"
  exit 0
fi

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS=47 \
AIUEOS_NATIVE_EXPECT_MARKER=M \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$compiler"
