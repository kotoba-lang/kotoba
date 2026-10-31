#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- qwen35-attention.kotoba as ported to amu's native object route, compiled by
# COMPILER (the Mac root's F2-signed.macho; as kotoba/qwen35-attention.o is now), against the kotoba-compiler/1 object
# it replaced (old-attn.o here, the committed object of main fad0f54b), under qemu-system-x86_64 (TCG): 600 calls over
# the three modes, head counts, kv groups, positions, region placements, values with specials and every refusal,
# comparing the answer and the whole arena; and 100 geometries the new object must refuse with -14 where the old one
# traps. The native object is recompiled under a test name from the source, so the two can be linked together.
# JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_qwen35_attention/kotoba_aiueos_qwen35_attention_native/' "$aiueos/kotoba/qwen35-attention.kotoba" > "$out/attn-native.kotoba"
rm -f "$out/attn-native.o"
(cd "$out" && "$compiler" compile attn-native.kotoba --target x86_64-aiueos-kernel-v1 --output attn-native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/attn-native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-attn.o" "$out/attn-native.o"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 256 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'VERDICTS 1a3  011  011  011  01b  011  011  011  005  005  010  011  009  000  000' "$out/serial.txt"
grep -q 'CASES 258 DIFFS 000 NEG14 000' "$out/serial.txt"
echo "AIUEOS_QWEN35_ATTENTION_NATIVE_DIFF_OK calls=600 ran=419 diffs=0 trap-geometries-refused=100"
