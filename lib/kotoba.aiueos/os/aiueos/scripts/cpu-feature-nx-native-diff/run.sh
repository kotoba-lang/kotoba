#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- cpu-feature-nx.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/cpu-feature-nx.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main daa39bbe), under qemu-system-x86_64 (TCG) on every processor of eight CPU models and
# topologies (../ap-run/run-models.sh). JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/../ap-run/run-models.sh" "$here" "$1" cpu-feature-nx kotoba_aiueos_cpu_feature_nx "$2"
grep -qx 'CASES 000001d0 NONZERO 00000120 DIFFS 0000 MODELS 8' "$1/summary.txt"
echo "AIUEOS_CPU_FEATURE_NX_NATIVE_DIFF_OK diffs=0"
