#!/bin/sh
# usage: run.sh OUTDIR [OBJECT] -- kotoba/tss-descriptor.o (or OBJECT) against the TSS descriptor expression
# aiueos_process_initialize used, copied into driver.c, under qemu-system-x86_64 (TCG): a grid of every refusal
# boundary and 20000 random admitted (base, limit) pairs, comparing the answer and the 24 bytes around the output.
# JUN-599.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 object=${2:-$aiueos/kotoba/tss-descriptor.o}
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" "$object"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'CASES' "$out/serial.txt"
grep -q 'CASES 00004f9a BUILT 00004d20 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_TSS_DESCRIPTOR_DIFF_OK diffs=0"
