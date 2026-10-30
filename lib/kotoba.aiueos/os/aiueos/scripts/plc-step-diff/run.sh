#!/bin/sh
# usage: run.sh OUTDIR -- kernel/plc_runtime.c's scan-cycle core over kotoba/plc-step.o (plc_release and plc_call as they
# are now, extracted by gen-new.py) against the C it replaced (old.c, verbatim), under qemu-system-x86_64 (TCG): 300 runs
# of up to 20 scans -- releases at and off the tick, well-formed scans (inputs, both stages, watchdog, commit) with one
# call in seven perturbed or injected, budgets extended past the deadline, ticks near 2^32 and 2^63 -- comparing every
# return value and the whole runtime struct after each step. Every fault kind is reached. JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function -Wno-unused-variable"
python3 -I "$here/gen-new.py" "$aiueos/kernel/plc_runtime.c" "$out/new.c"
zig cc $cf -I"$here" -c -o "$out/old.o" "$here/old.c"
zig cc $cf -I"$here" -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/plc-step.o"
rm -f "$out/serial.txt"
timeout 300 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'STEPS 000c90 COMMITS 000f1 FAULTS 012c DIFFS 00000' "$out/serial.txt"
grep -q 'KINDS 000 030 065 04b 027 00c 019 000' "$out/serial.txt"
echo "AIUEOS_PLC_STEP_DIFF_OK steps=3216 commits=241 diffs=0 faults=release,capability,stage,watchdog,budget,deadline"
