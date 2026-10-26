#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-native-owner-state.sh /path/to/compiler}
if [ -n "${AIUEOS_NATIVE_OWNER_STATE_WORK:-}" ]; then
  tmp=$AIUEOS_NATIVE_OWNER_STATE_WORK
  mkdir -p "$tmp"
else
  tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-owner-state.XXXXXX")
  trap 'rm -rf "$tmp"' EXIT HUP INT TERM
fi
source="$tmp/kernel-owner-state.kotoba"

# Mechanical mutation: claim only an already-owned slot.  The first claim of
# the zeroed state page must then fail before P/R can be published, proving the
# success marker depends on the persistent ownership state rather than prose.
needle='(if (= current 0)'
replacement='(if (= current 1)'
[ "$(grep -F -c "$needle" "$aiueos/native/kernel.kotoba")" = 1 ] || {
  echo "error: ownership mutation source is ambiguous" >&2; exit 1;
}
sed "s/$needle/$replacement/" "$aiueos/native/kernel.kotoba" >"$source"
grep -F "$needle" "$source" >/dev/null && {
  echo "error: ownership mutation did not apply" >&2; exit 1;
}

if [ "${AIUEOS_NATIVE_OWNER_STATE_BUILD_ONLY:-0}" = 1 ]; then
  AIUEOS_NATIVE_PROFILE=kernel \
  AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
  AIUEOS_NATIVE_OUT="$tmp/native" \
  AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
    "$aiueos/scripts/build-kotoba-native-boot.sh" "$compiler"
  echo "AIUEOS_KOTOBA_NATIVE_OWNER_STATE_BUILD_OK out=$tmp/boot"
  exit 0
fi

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS=45 \
AIUEOS_NATIVE_EXPECT_MARKER=M \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$compiler"
