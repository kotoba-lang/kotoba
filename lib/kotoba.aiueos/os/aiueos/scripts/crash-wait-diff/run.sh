#!/bin/sh
# usage: run.sh OUTDIR -- crash_sector_io_polled's completion wait over kotoba/blk-wait.o with MSI-X off (the loop as it
# is now in kernel/pci.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim), both with the 10^8
# budget made a parameter, under qemu-system-x86_64 (TCG). 300 waits: a ring already complete, with a wrong element or
# status, behind (budgets up to 70000 run out, two across the object's 65536-round chunk), past the target, the target
# wrapping to 0, and 100 in which one PIT interrupt lands mid-spin and makes the used index the target or passes it;
# comparing the answer and the submitted index. JUN-598.
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
grep -q 'CASES 012c COMPLETED 0056 MOVING 0063 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_CRASH_WAIT_DIFF_OK cases=300 completed=86 moving=99 diffs=0"
