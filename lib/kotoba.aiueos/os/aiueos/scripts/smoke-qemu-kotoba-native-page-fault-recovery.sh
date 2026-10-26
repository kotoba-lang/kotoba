#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-native-page-fault-recovery.sh /path/to/compiler}
tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-page-fault-recovery.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
source="$tmp/kernel-page-fault-recovery.kotoba"

handler='(kernel-page-fault-handler-address)'
probe='(+ 424200 42)'
[ "$(grep -F -c "$handler" "$aiueos/native/kernel.kotoba")" = 1 ] || {
  echo "error: page-fault handler source is ambiguous" >&2; exit 1;
}
[ "$(grep -F -c "$probe" "$aiueos/native/kernel.kotoba")" = 1 ] || {
  echo "error: page-fault probe source is ambiguous" >&2; exit 1;
}
sed -e 's/(kernel-page-fault-handler-address)/(kernel-page-fault-recovery-handler-address)/' \
    -e 's/(+ 424200 42)/(kernel-probe-recoverable-guard-write)/' \
    "$aiueos/native/kernel.kotoba" >"$source"

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS=33 \
AIUEOS_NATIVE_EXPECT_MARKER=MPRCDRE \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$compiler"

echo "AIUEOS_KOTOBA_NATIVE_PAGE_FAULT_RECOVERY_OK marker=MPRCDRE status=33 source=cpu-frame dedicated-handler-stack iretq"
