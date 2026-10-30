#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/rtl8125-arp.o, through kernel/rtl8125.c's wrappers (built with AIUEOS_RTL8125_ARP_ONLY),
# against the C ARP helpers it replaced (verbatim in driver.c), under qemu-system-x86_64 (TCG): tests/rtl8125_handoff_model.c's
# checks; 400 request frames (to broadcast, to us, elsewhere; zero and all-ones addresses) at 9 lengths with every byte of the
# 42 mutated; the reply at 6 capacities over a patterned buffer; and arguments only the object refuses. JUN-553.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
zig cc $cf -c -o "$out/driver.o" -I"$aiueos/kernel" "$here/driver.c"
zig cc $cf -c -o "$out/model.o" -I"$aiueos/kernel" "$aiueos/tests/rtl8125_handoff_model.c"
zig cc $cf -c -o "$out/rtl8125.o" -DAIUEOS_RTL8125_ARP_ONLY "$aiueos/kernel/rtl8125.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/model.o" "$out/rtl8125.o" "$aiueos/kotoba/rtl8125-arp.o"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'AIUEOS_RTL8125_MODEL_OK' "$out/serial.txt"
grep -q 'CASES 09ddb ACCEPTED 01980 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_RTL8125_ARP_DIFF_OK cases=40411 accepted=6528 diffs=0"
