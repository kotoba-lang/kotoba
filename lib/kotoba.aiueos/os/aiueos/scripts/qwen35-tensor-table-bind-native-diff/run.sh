#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- qwen35-tensor-table-bind.kotoba as ported to amu's native object route, compiled by
# COMPILER (the Mac root's F2-signed.macho; as kotoba/qwen35-tensor-table-bind.o is now), against the kotoba-compiler/1
# object it replaced (old-tt.o here, the committed object of main c2785c88), under qemu-system-x86_64 (TCG), over the
# Qwen3.8 tensor table tests/make_qwen35_header_fixture.py builds: the table as built, refused early, cut short, and
# with every seventh record's name, dimension count, dimension, type or offset changed, comparing the answer and the
# plan bytes. The native object is recompiled under a test name from the source, so the two can be linked together.
# JUN-633, JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
python3 -I "$aiueos/tests/make_qwen35_header_fixture.py" "$out/header.gguf" >/dev/null
python3 -I "$here/records.py" "$out/header.gguf" "$out/records.h" >/dev/null
sed 's/kotoba_aiueos_qwen35_tensor_table_bind/kotoba_aiueos_qwen35_tensor_table_bind_native/' "$aiueos/kotoba/qwen35-tensor-table-bind.kotoba" > "$out/tt-native.kotoba"
rm -f "$out/tt-native.o"
(cd "$out" && "$compiler" compile tt-native.kotoba --target x86_64-aiueos-kernel-v1 --output tt-native.o --fuel ${TT_FUEL:-4194304} 3<. </dev/null >/dev/null)
test -f "$out/tt-native.o"
(cd "$out" && zig ld.lld -m elf_x86_64 -r -b binary header.gguf -o header.o)
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -I$out"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old-tt.o" "$out/tt-native.o" "$out/header.o"
rm -f "$out/serial.txt"
timeout 3000 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 512 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 274 BOUND 001 DIFFS 000' "$out/serial.txt"
echo "AIUEOS_QWEN35_TENSOR_TABLE_BIND_NATIVE_DIFF_OK scans=628 bound=1 diffs=0"
