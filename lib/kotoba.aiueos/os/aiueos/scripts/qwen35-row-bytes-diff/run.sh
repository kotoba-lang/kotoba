#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/qwen35-row-bytes.o against aiueos_qwen35_quant_row_bytes as kernel/qwen35_quant.c had
# it (old.c, verbatim), under qemu-system-x86_64 (TCG): 300 types x 32 edge element counts (block boundaries, 2^62,
# 2^63, 2^64-1 and the wrap region) and 120 random ones each, and 4000 types with bits above the low 8. JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
zig cc $cf -I"$aiueos/kernel" -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$aiueos/kotoba/qwen35-row-bytes.o"
rm -f "$out/serial.txt"
timeout 300 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 00c1c0 SIZED 0003cb DIFFS 000000' "$out/serial.txt"
echo "AIUEOS_QWEN35_ROW_BYTES_DIFF_OK cases=49600 sized=971 diffs=0"
