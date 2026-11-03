#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- pic-disable.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/pic-disable.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main daa39bbe), under qemu-system-x86_64 (TCG): every pair from driver.c's base set, comparing
# each answer and the full trace of port accesses (../port-trace). JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/../port-trace/run-pair.sh" "$here" "$1" pic-disable kotoba_aiueos_pic_disable "$2" "-cpu qemu64 -nodefaults"
grep -qx 'CASES 00000af9 NONZERO 00000288 DIFFS 0000 ACCESSES ioport80=6480 pic=7776' "$1/summary.txt"
echo "AIUEOS_PIC_DISABLE_NATIVE_DIFF_OK diffs=0"
