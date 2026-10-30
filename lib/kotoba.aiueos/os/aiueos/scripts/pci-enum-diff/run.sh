#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's enumeration decisions over kotoba/pci-enum.o against the verbatim C expressions they
# replaced (old.c), under qemu-system-x86_64 (TCG), exhaustively: the presence test, the virtio dispatch and the RTL8125
# test for every device ID under six vendors (virtio, Realtek, 0xffff, Intel, 0x1af5, 0) and every vendor under device
# 0x1044, the function count for all 256 header-type bytes, and the result cascade for every combination of the four
# driver flags with present / virtio counts 0..2. The scan loops and driver calls themselves are covered by the QEMU
# boot (every virtio device probed). JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$aiueos/kotoba/pci-enum.o"
rm -f "$out/serial.txt"
timeout 1200 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 140190 DIFFS 000000' "$out/serial.txt"
echo "AIUEOS_PCI_ENUM_DIFF_OK cases=1311120 diffs=0"
