#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- qwen35-dequant-row.kotoba as ported to amu's native object route (one file, the
# codebooks as if-trees), compiled by COMPILER (the Mac root's F2-signed.macho; as kotoba/qwen35-dequant-row.o is now),
# against the kotoba-compiler/1 object it replaced (old-dq.o here, the committed object of main fad0f54b), under
# qemu-system-x86_64 (TCG): 1200 rows over every admitted type, counts up to 65536 and every refusal, comparing the
# answer and the destination bytes. The native object is recompiled under a test name from the source, so the two can
# be linked together. JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_qwen35_dequant_row/kotoba_aiueos_qwen35_dequant_row_native/' "$aiueos/kotoba/qwen35-dequant-row.kotoba" > "$out/dq-native.kotoba"
rm -f "$out/dq-native.o"
(cd "$out" && "$compiler" compile dq-native.kotoba --target x86_64-aiueos-kernel-v1 --output dq-native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/dq-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-dq.o" "$out/dq-native.o"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 256 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'VERDICTS\|CASES' "$out/serial.txt"
grep -q 'VERDICTS 03c0  001e  001e  003c  001e  001e  003c  0000' "$out/serial.txt"
grep -q 'CASES 04b0 WRITTEN 03c0 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_QWEN35_DEQUANT_ROW_NATIVE_DIFF_OK diffs=0"
