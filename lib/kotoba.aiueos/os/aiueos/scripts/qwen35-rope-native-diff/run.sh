#!/bin/sh
# usage: run.sh OUTDIR -- qwen35-rope.kotoba compiled by amu's native root (as kotoba/qwen35-rope.o is now) against the
# kotoba-compiler/1 object it replaced (old-rope.o here, the committed object of main 6ef8c9ff), under
# qemu-system-x86_64 (TCG): 3000 calls over heads, positions and value patterns with specials, and every refusal;
# comparing the answer and every output bit. The native object is recompiled under a test name from the source, so
# the two can be linked together. COMPILER is the native root (F2-signed.macho). JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_qwen35_rope/kotoba_aiueos_qwen35_rope_native/' "$aiueos/kotoba/qwen35-rope.kotoba" > "$out/rope-native.kotoba"
rm -f "$out/rope-native.o"
(cd "$out" && "$compiler" compile rope-native.kotoba --target x86_64-aiueos-kernel-v1 --output rope-native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/rope-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-rope.o" "$out/rope-native.o"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0bb8 ROTATED 0adc REFUSED 00dc DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_QWEN35_ROPE_NATIVE_DIFF_OK cases=3000 rotated=2780 refused=220 diffs=0"
