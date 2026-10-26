#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-native-page-fault.sh /path/to/compiler guard-write|text-write|nx-execute}
probe=${2:?usage: smoke-qemu-kotoba-native-page-fault.sh /path/to/compiler guard-write|text-write|nx-execute}
tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-page-fault.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
source="$tmp/kernel-page-fault.kotoba"

case "$probe" in
  guard-write)
    replacement='(kernel-probe-guard-write)'
    marker=MPRCDG
    status=51
    ;;
  text-write)
    replacement='(kernel-probe-text-write)'
    marker=MPRCDW
    status=53
    ;;
  nx-execute)
    replacement='(kernel-probe-nx-execute)'
    marker=MPRCDX
    status=55
    ;;
  *) echo "error: unknown page-fault probe: $probe" >&2; exit 2 ;;
esac

needle='(+ 424200 42)'
[ "$(grep -F -c "$needle" "$aiueos/native/kernel.kotoba")" = 1 ] || {
  echo "error: page-fault probe source is ambiguous" >&2; exit 1;
}
sed "s/$needle/$replacement/" "$aiueos/native/kernel.kotoba" >"$source"
grep -F "$needle" "$source" >/dev/null && {
  echo "error: page-fault probe mutation did not apply" >&2; exit 1;
}

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS="$status" \
AIUEOS_NATIVE_EXPECT_MARKER="$marker" \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$compiler"

echo "AIUEOS_KOTOBA_NATIVE_PAGE_FAULT_OK probe=$probe marker=$marker status=$status source=cpu-cr2-error-code"
