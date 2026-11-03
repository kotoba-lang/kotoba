#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- pci-config-write.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/pci-config-write.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main daa39bbe), under qemu-system-x86_64 (TCG): the bound grid and random tuples of driver.c, comparing
# each answer and the full trace of port accesses (../port-trace). JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
sh "$here/../port-trace/run-pair.sh" "$here" "$1" pci-config-write kotoba_aiueos_pci_config_write "$2" "-cpu qemu64 -nodefaults"
grep -qx 'CASES 000038e0 NONZERO 0000143f DIFFS 0000 ACCESSES pci-conf-data=5183 pci-conf-idx=5183' "$1/summary.txt"
echo "AIUEOS_PCI_CONFIG_WRITE_NATIVE_DIFF_OK diffs=0"
