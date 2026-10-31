#!/bin/sh
# usage: run.sh OUTDIR COMPILER [CPU] -- qwen35-matvec.kotoba as ported to amu's native object route (check + row
# exports, run over the plan by kernel/qwen35_matvec_plan.h), compiled by COMPILER (amu 3d160442's Mac root; as
# kotoba/qwen35-matvec.o is now), against the kotoba-compiler/1 object it replaced (old-mv.o here, the committed
# object of main), under qemu-system-x86_64 (TCG) with CPU (default qemu64: the scalar dot; max: AVX2). JUN-633.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2 cpu=${3:-qemu64}
mkdir -p "$out"
cp "$aiueos/kotoba/qwen35-matvec.kotoba" "$out/mv-native.kotoba"
rm -f "$out/mv-native.o"
(cd "$out" && "$compiler" compile mv-native.kotoba --target x86_64-aiueos-kernel-v1 --output mv-native.o --fuel 16777216 3<. </dev/null >/dev/null)
test -f "$out/mv-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-mv.o" "$out/mv-native.o"
rm -f "$out/serial.txt"
timeout 3000 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 256 -cpu "$cpu" \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'VERDICTS\|CASES' "$out/serial.txt"
grep -q 'VERDICTS 0244  0018  0000  0019  0032  0019  0032  0019  0019  0032  0015  0019  0000' "$out/serial.txt"
grep -q 'CASES 0384 RAN 0244 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_QWEN35_MATVEC_NATIVE_DIFF_OK cpu=$cpu diffs=0"
