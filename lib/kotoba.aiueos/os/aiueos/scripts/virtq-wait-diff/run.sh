#!/bin/sh
# usage: run.sh OUTDIR -- rng_refill's completion wait over kotoba/virtq-wait.o (the loop as it is now in kernel/pci.c,
# extracted by gen-new.py) against the C it replaced (old.c, verbatim), both with the 10^8 budget made a parameter,
# under qemu-system-x86_64 (TCG) with a real timer interrupt: the PIT in one-shot mode, re-armed by its own handler,
# which returns with IF clear, so each halt consumes exactly one tick; the handler plays a scripted device (the RNG
# interrupt counter moves on one tick, the used index becomes the wanted one on another). 300 waits: completions after
# 0..6 ticks, the interrupt already counted, the index already there, stalls that run small budgets out, budgets up to
# 70000 and two stalls across the object's 65536-round chunk (65535 and 65537); comparing the answer and the ticks
# consumed. JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/virtq-wait.o"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 012c COMPLETED 00cc DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_VIRTQ_WAIT_DIFF_OK cases=300 completed=204 diffs=0"
