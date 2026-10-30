#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's net_build_dhcp over kotoba/dhcp-build.o (the wrapper as it is now in kernel/pci.c,
# extracted by gen-new.py) against the C it replaced (old.c, verbatim, over kotoba/ipv4-checksum.o and
# kotoba/udp-checksum.o as in the kernel), under qemu-system-x86_64 (TCG): 6000 frames -- random and all-zero MACs,
# message types 1, 3, 0, 2, 5, 255, requested and server addresses random, 0 and 255.255.255.255 -- into random
# buffers, comparing the answer and all 512 bytes of the buffer. JUN-552.
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
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/dhcp-build.o" "$aiueos/kotoba/ipv4-checksum.o" "$aiueos/kotoba/udp-checksum.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 1770 REQUESTS 0af0 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_DHCP_BUILD_DIFF_OK cases=6000 requests=2800 diffs=0"
