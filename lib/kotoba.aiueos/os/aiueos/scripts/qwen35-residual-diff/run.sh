#!/bin/sh
# usage: run.sh OUTDIR -- the model-handoff image's residual add over kotoba/qwen35-residual.o (as it is now in
# kernel/qwen35_infer.c, extracted by gen-new.py) against the C loop it replaced (old.c, verbatim, compiled with
# vectorization as the kernel is) under qemu-system-x86_64 (TCG): 600 vectors of 5120 binary32 with special values
# mixed in, comparing every element's bits. JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function -I$here"
python3 -I "$here/gen-new.py" "$aiueos/kernel/qwen35_infer.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "${AIUEOS_KOTOBA_QWEN35_RESIDUAL_OBJECT:-$aiueos/kotoba/qwen35-residual.o}"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'VECTORS 0258 ELEMENTS 002ee000 REFUSED 0000 DIFFS 0000 00000000' "$out/serial.txt"
echo "AIUEOS_QWEN35_RESIDUAL_DIFF_OK vectors=600 elements=3072000 diffs=0"
