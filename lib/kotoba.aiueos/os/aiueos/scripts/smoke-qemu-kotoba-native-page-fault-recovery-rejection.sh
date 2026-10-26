#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: smoke-qemu-kotoba-native-page-fault-recovery-rejection.sh /path/to/compiler}
tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-page-fault-recovery-rejection.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
source="$tmp/kernel-page-fault-recovery-rejection.kotoba"

python3 - "$aiueos/native/kernel.kotoba" "$source" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text()
needle = """(kernel-configure-page-fault-recovery
                                       (kernel-subregion 4096 1073737728
                                                         (- seventh-start 4096) 4096)
                                       (kernel-subregion 4096 1073737728
                                                         (- eighth-start 4096) 4096))"""
replacement = """(kernel-configure-page-fault-recovery
                                       (kernel-subregion 4096 1073737728
                                                         (- seventh-start 4096) 4096)
                                       (kernel-subregion 4096 1073737728
                                                         (- seventh-start 4096) 4096))"""
if source.count(needle) != 1:
    raise SystemExit("error: recovery configuration source is ambiguous")
Path(sys.argv[2]).write_text(source.replace(needle, replacement))
PY

AIUEOS_NATIVE_KERNEL_SOURCE="$source" \
AIUEOS_NATIVE_OUT="$tmp/native" \
AIUEOS_NATIVE_BOOT_OUT="$tmp/boot" \
AIUEOS_NATIVE_EXPECT_STATUS=49 \
AIUEOS_NATIVE_EXPECT_MARKER=M \
  "$aiueos/scripts/smoke-qemu-kotoba-native.sh" "$compiler"

echo "AIUEOS_KOTOBA_NATIVE_PAGE_FAULT_RECOVERY_REJECTION_OK marker=M status=49 reason=frame-stack-alias"
