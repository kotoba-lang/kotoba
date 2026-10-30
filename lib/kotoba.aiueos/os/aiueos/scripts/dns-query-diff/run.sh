#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's net_build_dns_query_named over kotoba/dns-query.o (the wrapper as it is now in
# kernel/pci.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim, over kotoba/ipv4-checksum.o as in
# the kernel), under qemu-system-x86_64 (TCG): 6000 queries -- random MACs, addresses (0 included) and server ports,
# questions of 5..255 bytes plus the out-of-range lengths 0, 1, 4, 256 and 300 -- comparing the answer and all 1024
# bytes of the frame buffer. JUN-552.
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
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/dns-query.o" "$aiueos/kotoba/ipv4-checksum.o"
rm -f "$out/serial.txt"
timeout 1200 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 1770 BUILT 173e DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_DNS_QUERY_DIFF_OK cases=6000 built=5950 diffs=0"
