#!/bin/sh
# usage: run.sh OUTDIR -- the text-building segment of aiueos_device_result_http_request over
# kotoba/device-result-text.o (as it is now in kernel/device_result.c, extracted by gen-new.py) against the C it replaced
# (old.c, verbatim), both over prelude.h's stubs, under qemu-system-x86_64 (TCG): 600 results (zero, all-ones, 2^63,
# 19- and 20-digit numbers, random) comparing the canonical text that is hashed and the JSON body byte for byte; then the
# object at every capacity 0..700 in both modes, and arguments it refuses. JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function -Wno-unused-variable -Wno-unused-label"
python3 -I "$here/gen-object.py" "$out/gen.kotoba"
cmp -s "$out/gen.kotoba" "$aiueos/kotoba/device-result-text.kotoba" || { echo "device-result-text.kotoba is not gen-object.py's output" >&2; exit 1; }
python3 -I "$here/gen-new.py" "$aiueos/kernel/device_result.c" "$out/new.c"
zig cc $cf -I"$here" -I"$aiueos/kernel" -c -o "$out/old.o" "$here/old.c"
zig cc $cf -I"$here" -I"$aiueos/kernel" -c -o "$out/new.o" "$out/new.c"
zig cc $cf -I"$aiueos/kernel" -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/device-result-text.o"
rm -f "$out/serial.txt"
timeout 300 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 07d7 SENT 0258 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_DEVICE_RESULT_TEXT_DIFF_OK cases=2007 sent=600 diffs=0"
