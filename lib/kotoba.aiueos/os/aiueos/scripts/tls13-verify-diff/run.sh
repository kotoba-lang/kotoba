#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/tls13-verify.o against kernel/tls13.c's finish_check / verify_certificate_verify (in driver.c,
# rewritten only to take their globals as parameters), both over the committed sha256, tls13-keyschedule and tls13-cert objects,
# under qemu-system-x86_64 (TCG): Finished over transcripts of 0..12224 bytes with the right verify data, each bit position
# flipped and wrong lengths; 1500 CertificateVerify messages, valid and with byte / scheme / header / length / signature-length
# mutations. Return value, scheme, r || s and digest are compared. JUN-553.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wno-unused-function"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
k="$aiueos/kotoba"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$k/tls13-verify.o" "$k/tls13-keyschedule.o" "$k/tls13-cert.o" "$k/sha256.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0072c ACCEPTED 00216 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_TLS13_VERIFY_DIFF_OK cases=1836 accepted=534 diffs=0"
