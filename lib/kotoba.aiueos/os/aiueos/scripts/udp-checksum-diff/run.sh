#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's net_udp_checksum and net_udp_rx_checksum_ok over kotoba/udp-checksum.o (the wrappers
# as they are now in kernel/pci.c, extracted by gen-new.py) against the C they replaced (old.c, verbatim, over
# kotoba/ipv4-checksum.o as in the kernel), under qemu-system-x86_64 (TCG): 8000 frames with UDP lengths 0..2160
# (the checksum object's 2048-byte bound at its edges, odd lengths, all-0x00 / all-0xff bytes), each also with the
# checksum field a sender would write and then one bit off; comparing the sent value and the receive admission.
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
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/udp-checksum.o" "$aiueos/kotoba/ipv4-checksum.o"
rm -f "$out/serial.txt"
timeout 1200 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 05cd8 RX-OK 1e7e DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_UDP_CHECKSUM_DIFF_OK cases=23768 rx-ok=7806 diffs=0"
