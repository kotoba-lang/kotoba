#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- cpu-feature-syscall.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/cpu-feature-syscall.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main daa39bbe), under qemu-system-x86_64 (TCG) on every processor of eight CPU models and
# topologies (../ap-run/run-models.sh). JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/../ap-run/run-models.sh" "$here" "$1" cpu-feature-syscall kotoba_aiueos_cpu_feature_syscall "$2"
grep -qx 'CASES 000001d0 NONZERO 00000150 DIFFS 0000 MODELS 8' "$1/summary.txt"
echo "AIUEOS_CPU_FEATURE_SYSCALL_NATIVE_DIFF_OK diffs=0"
