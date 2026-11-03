#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- qwen35-activation.kotoba as ported to amu's native object route (its own-length
# export, the conv one channel per call), compiled by COMPILER (the Mac root's F2-signed.macho; as
# kotoba/qwen35-activation.o is now), against the kotoba-compiler/1 object it replaced (old-act.o here, the committed
# object of main 46709484), under qemu-system-x86_64 (TCG): 3000 calls over the seven modes, counts up to 65536, values
# with specials and every old refusal, the new object called as the C calls it, comparing the answer and every byte
# written; and 200 calls the new object must refuse with -9. The native object is recompiled under a test name from
# the source, so the two can be linked together. JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_qwen35_activation/kotoba_aiueos_qwen35_activation_native/' "$aiueos/kotoba/qwen35-activation.kotoba" > "$out/act-native.kotoba"
rm -f "$out/act-native.o"
(cd "$out" && "$compiler" compile act-native.kotoba --target x86_64-aiueos-kernel-v1 --output act-native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/act-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-act.o" "$out/act-native.o"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 256 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'VERDICTS 09fc  0061  0061  00c2  002a  000e  0000  0000  0000  0000' "$out/serial.txt"
grep -q 'CASES 0c80 DIFFS 0000 NEG9 0000' "$out/serial.txt"
echo "AIUEOS_QWEN35_ACTIVATION_NATIVE_DIFF_OK calls=3000 applied=2556 diffs=0 new-length-refusals=200"
