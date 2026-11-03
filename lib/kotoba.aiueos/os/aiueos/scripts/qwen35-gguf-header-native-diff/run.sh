#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- qwen35-gguf-header-valid.kotoba compiled by amu's native root (COMPILER, the Mac
# root's F2-signed.macho; as kotoba/qwen35-gguf-header-valid.o is now) against the kotoba-compiler/1 object it replaced
# (old-header.o here, the committed object of main 8cf589c8), under qemu-system-x86_64 (TCG): 200000 calls over
# artifact sizes, accessible lengths, a null base and right or wrong header fields, comparing the verdict. The native
# object is recompiled under a test name from the source, so the two can be linked together. JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_qwen35_gguf_header_valid/kotoba_aiueos_qwen35_gguf_header_valid_native/' \
  "$aiueos/kotoba/qwen35-gguf-header-valid.kotoba" > "$out/header-native.kotoba"
rm -f "$out/header-native.o"
(cd "$out" && "$compiler" compile header-native.kotoba --target x86_64-aiueos-kernel-v1 --output header-native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/header-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-header.o" "$out/header-native.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'VERDICTS 0b632  007bd  067f3  08b53  065ba  055e6  0396b  0394a  02db6  00000' "$out/serial.txt"
grep -q 'CASES 30d40 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_QWEN35_GGUF_HEADER_NATIVE_DIFF_OK cases=200000 admitted=46642 diffs=0"
