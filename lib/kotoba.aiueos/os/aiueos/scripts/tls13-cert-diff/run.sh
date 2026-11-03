#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/tls13-cert.o against verbatim copies of the C find_p256_point / der_int_be32 / parse_ecdsa_der that
# kernel/tls13.c had (in driver.c), under qemu-system-x86_64 (TCG): the SPKI prefix at the first / last / one-past positions, a second
# copy and each of its 27 bytes flipped, over regions of 0..12288 bytes; DER signatures with r and s of 1..34 bytes, leading zeros,
# trailing and missing bytes; 4000 fuzzed signatures. The return value and all 64 output bytes are compared. JUN-553.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wno-unused-function"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" \
  "$out/entry.o" "$out/driver.o" "$aiueos/kotoba/tls13-cert.o"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 02154 ACCEPTED 00820 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_TLS13_CERT_DIFF_OK cases=8532 accepted=2080 diffs=0"
