#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's read_bar and bar_extent over kotoba/pci-bar.o (the wrappers as they are now in
# kernel/pci.c, extracted by gen-new.py) against the C they replaced (old.c, verbatim, over kotoba/pci-extent-valid.o
# as in the kernel), under qemu-system-x86_64 (TCG), each over its own copy of an emulated function whose BARs answer
# the all-ones probe as hardware does: 8000 functions (32-bit and 64-bit memory BARs of 16 bytes .. 2^47, prefetch bits,
# I/O BARs, the reserved types, bases 0 and 0xfffffff0) at indices 0..7; comparing the answers, the base and length, the
# function's configuration words after, and an FNV hash of every configuration read and write in order. JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/pci-bar.o" "$aiueos/kotoba/pci-extent-valid.o"
rm -f "$out/serial.txt"
timeout 1200 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0fa00 ADMITTED 0614f DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_PCI_BAR_DIFF_OK cases=64000 admitted=24911 diffs=0"
