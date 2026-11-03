#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/p256-did.o against p256_did / base58_encode as kernel/device_result.c had them (old.c,
# verbatim), under qemu-system-x86_64 (TCG): 400 public keys (all-zero, all-0xff, X with leading zero bytes, both Y
# parities) x 17 output capacities over a patterned buffer, and arguments only the object refuses. JUN-554.
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
  "$out/old.o" "$aiueos/kotoba/p256-did.o"
rm -f "$out/serial.txt"
timeout 300 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 01a94 WHOLE 00c80 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_P256_DID_DIFF_OK cases=6804 whole=3200 diffs=0"
