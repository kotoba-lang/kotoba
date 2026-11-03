#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/tls13-keyschedule.o against verbatim copies of the C hmac_sha256 / hkdf_expand_label that
# kernel/tls13.c had (in driver.c), both over the committed kotoba/sha256.o, under qemu-system-x86_64 (TCG): RFC 4231 case 1 and
# 330 cases (key lengths 0..200, data 0..12225, label / context / output lengths across the info bound), then two non-canonical
# lengths, which the object refuses. JUN-553. Executed, not a kernel boot.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" \
  "$out/entry.o" "$out/driver.o" "$aiueos/kotoba/tls13-keyschedule.o" "$aiueos/kotoba/sha256.o"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q '^01 0d27b29d63b2ef16 b0 f7 ' "$out/serial.txt"    # RFC 4231 test case 1
grep -q '^0 0 $' "$out/serial.txt"                         # both non-canonical lengths refused
grep -q 'CASES 014a DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_TLS13_KEYSCHEDULE_DIFF_OK cases=330 diffs=0"
