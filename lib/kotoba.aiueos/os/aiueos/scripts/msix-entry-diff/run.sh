#!/bin/sh
# usage: run.sh OUTDIR -- setup_rng_msix's and setup_blk_msix's MSI-X programming over kotoba/msix-entry.o (as it is now
# in kernel/pci.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim), under qemu-system-x86_64 (TCG)
# behind the MMIO trap harness (scripts/mmio-trap): an emulated device that keeps the queue vector, refuses it
# (NO_VECTOR) or answers another, over 4000 random register files, messages and APIC ids; comparing the answer, every
# bus transaction in order (reads, writes, their widths' bytes and values) and the registers after. JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
trap=$aiueos/scripts/mmio-trap
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function -I$here"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc $cf -mgeneral-regs-only -c -o "$out/trap.o" "$trap/trap.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$trap/entry.S"
zig ld.lld -nostdlib -static -T "$trap/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/trap.o" "$out/old.o" "$out/new.o" "${AIUEOS_KOTOBA_MSIX_ENTRY_OBJECT:-$aiueos/kotoba/msix-entry.o}"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0fa0 KEPT 0a6f DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_MSIX_ENTRY_DIFF_OK cases=4000 kept=2671 diffs=0"
