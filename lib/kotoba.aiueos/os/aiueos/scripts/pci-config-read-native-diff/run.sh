#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- pci-config-read.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/pci-config-read.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 9f16e6ce), under qemu-system-x86_64 (TCG): the bound grid, every dword of buses 0 and 1 and
# random tuples of driver.c, comparing each answer and the full trace of port accesses (../port-trace). JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/../port-trace/run-pair.sh" "$here" "$1" pci-config-read kotoba_aiueos_pci_config_read "$2" "-cpu qemu64 -nodefaults"
grep -qx 'CASES 0000c858 NONZERO 00000133 DIFFS 0000 ACCESSES pci-conf-data=39208 pci-conf-idx=39208' "$1/summary.txt"
echo "AIUEOS_PCI_CONFIG_READ_NATIVE_DIFF_OK diffs=0"
