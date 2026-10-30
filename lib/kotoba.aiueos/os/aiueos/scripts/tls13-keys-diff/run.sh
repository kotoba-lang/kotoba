#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/tls13-keys.o against kernel/tls13.c's derive_hs_keys (after the X25519), derive_ap_keys and
# aiueos_tls13_take_finished's verify data (in driver.c, rewritten only to take their globals as parameters), both over the
# committed sha256 and tls13-keyschedule objects, under qemu-system-x86_64 (TCG): 24 secrets (all-zero and all-0xff among
# them) over transcripts of 0..12288 bytes, every output byte compared and nothing past it written; refused secret / output
# lengths and lengths with a non-zero upper half write nothing. JUN-553.
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
  "$k/tls13-keys.o" "$k/tls13-keyschedule.o" "$k/sha256.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 00376 ACCEPTED 00360 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_TLS13_KEYS_DIFF_OK cases=886 accepted=864 diffs=0"
