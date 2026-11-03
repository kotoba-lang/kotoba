#!/bin/sh
# usage: run.sh OUTDIR -- virtio_blk_sector_io_ex's completion wait over kotoba/blk-wait.o (the loop as it is now in
# kernel/pci.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim), both with the 10^8 budget made a
# parameter, under qemu-system-x86_64 (TCG) with a real timer interrupt (the one-shot PIT of scripts/virtq-wait-diff,
# so each halt consumes exactly one tick); the handler plays a scripted device (the block interrupt counter moves on
# one tick, the used index becomes the target or overshoots it on another). 400 waits with MSI-X (halting) and without
# (pause), the target wrapping to 0, the index already there, past the target, far behind it, a wrong completion
# element or status, stalls that run small budgets out, budgets up to 1020, completions after 65535..65538 halts and
# stalls across the object's 65536-round chunk; comparing the answer, the ticks consumed, the submitted index and the
# slowest-wait and overshoot statistics. JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function -I$here"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "${AIUEOS_KOTOBA_BLK_WAIT_OBJECT:-$aiueos/kotoba/blk-wait.o}"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0190 COMPLETED 0064 OVERSHOT 005b DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_BLK_WAIT_DIFF_OK cases=400 completed=100 overshot=91 diffs=0"
