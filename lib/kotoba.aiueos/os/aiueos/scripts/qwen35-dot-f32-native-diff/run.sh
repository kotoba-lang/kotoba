#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- qwen35-dot-f32.kotoba as ported to amu's native object route, compiled by COMPILER
# (the Mac root's F2-signed.macho; as kotoba/qwen35-dot-f32.o is now), against the kotoba-compiler/1 object it
# replaced (old-dot.o here, the committed object of main 8cf589c8), under qemu-system-x86_64 (TCG): 4000 calls over
# counts, values with specials and every refusal, comparing the 64-bit answer. The native object is recompiled under a
# test name from the source, so the two can be linked together. JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_qwen35_dot_f32/kotoba_aiueos_qwen35_dot_f32_native/' "$aiueos/kotoba/qwen35-dot-f32.kotoba" > "$out/dot-native.kotoba"
rm -f "$out/dot-native.o"
(cd "$out" && "$compiler" compile dot-native.kotoba --target x86_64-aiueos-kernel-v1 --output dot-native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/dot-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-dot.o" "$out/dot-native.o"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0fa0 SUMS 0ee8 REFUSED 00b8 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_QWEN35_DOT_F32_NATIVE_DIFF_OK cases=4000 sums=3816 refused=184 diffs=0"
