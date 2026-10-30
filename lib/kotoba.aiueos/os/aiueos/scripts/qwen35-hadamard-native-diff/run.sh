#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- qwen35-hadamard.kotoba as ported to amu's native object route, compiled by COMPILER
# (the Mac root's F2-signed.macho; as kotoba/qwen35-hadamard.o is now), against the kotoba-compiler/1 object it
# replaced (old-had.o here, the committed object of main 327d9b96), under qemu-system-x86_64 (TCG): 300 transforms over
# both modes, widths up to 65536, the permutation off and on, values with specials and every refusal, comparing the
# answer and the whole arena. The native object is recompiled under a test name from the source, so the two can be
# linked together. JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_qwen35_hadamard/kotoba_aiueos_qwen35_hadamard_native/' "$aiueos/kotoba/qwen35-hadamard.kotoba" > "$out/had-native.kotoba"
rm -f "$out/had-native.o"
(cd "$out" && "$compiler" compile had-native.kotoba --target x86_64-aiueos-kernel-v1 --output had-native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/had-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-had.o" "$out/had-native.o"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 256 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'VERDICTS 09d  00d  00d  00d  00d  00d  01a  00d  00d  00d  00d  000' "$out/serial.txt"
grep -q 'CASES 12c DIFFS 000' "$out/serial.txt"
echo "AIUEOS_QWEN35_HADAMARD_NATIVE_DIFF_OK transforms=300 ran=157 diffs=0"
