#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/tls13-hello.o against the C clienthello_build / parse_serverhello that kernel/tls13.c had (in
# driver.c, rewritten only to take their state as parameters; parse_serverhello stops where the C calls transcript_add), under
# qemu-system-x86_64 (TCG): ServerHellos over session-id lengths 0..33, 0..2 key shares, with and without TLS 1.3, both extension
# orders, one byte short and long, and 6000 mutated ones; ClientHellos for host lengths 0..255 and the unconfigured default. JUN-553.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wno-unused-function"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" \
  "$out/entry.o" "$out/driver.o" "$aiueos/kotoba/tls13-hello.o"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 01d39 ACCEPTED 01024 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_TLS13_HELLO_DIFF_OK cases=7481 accepted=4132 diffs=0"
