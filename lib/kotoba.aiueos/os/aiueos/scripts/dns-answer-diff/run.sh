#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's net_dns_answer_ok_named over kotoba/dns-answer.o (the wrapper as it is now in
# kernel/pci.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim, over kotoba/ipv4-checksum.o as in
# the kernel), under qemu-system-x86_64 (TCG): 1500 generated answers -- the pointer and the copied-question layouts,
# questions of 5..255 bytes, other server ports, RCODE set, A = 0, UDP checksum zero or right, padding and trailing bytes
# -- each with a shorter question, out-of-range question lengths, truncations, every byte flipped (every fifth answer) or
# 24 bit flips, and the IPv4 / UDP length fields moved by one under recomputed checksums; comparing the result and *out_a.
# JUN-552.
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
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/dns-answer.o" "$aiueos/kotoba/ipv4-checksum.o"
rm -f "$out/serial.txt"
timeout 1200 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 014e13 ADMITTED 02e45 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_DNS_ANSWER_DIFF_OK cases=85523 admitted=11845 diffs=0"
