#!/bin/sh
# usage: run.sh OUTDIR -- select_output_token's selection over kotoba/qwen35-select.o (the model-handoff select_view of
# kernel/qwen35_infer.c, extracted by gen-new.py) against the C loop it replaced (old.c, verbatim), under
# qemu-system-x86_64 (TCG): 400 logit views of 1..17408 floats -- random bits, many ties, near-equal values, specials
# (+-0, +-inf, NaNs, denormals, +-max), across the 4096-logit window boundaries -- each from the initial state, a carried
# state and a state whose two logits equal a logit of the view, comparing the result and the four choice fields bit for
# bit. JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/qwen35_infer.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/qwen35-select.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 04b0 NONFINITE 01d7 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_QWEN35_SELECT_DIFF_OK cases=1200 nonfinite=471 diffs=0"
