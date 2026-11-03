#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- cpu-apic-id.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/cpu-apic-id.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main daa39bbe), under qemu-system-x86_64 (TCG) on every processor of eight CPU models and
# topologies (../ap-run/run-models.sh). JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/../ap-run/run-models.sh" "$here" "$1" cpu-apic-id kotoba_aiueos_cpu_apic_id "$2"
grep -qx 'CASES 000001d0 NONZERO 00000150 DIFFS 0000 MODELS 8' "$1/summary.txt"
echo "AIUEOS_CPU_APIC_ID_NATIVE_DIFF_OK diffs=0"
