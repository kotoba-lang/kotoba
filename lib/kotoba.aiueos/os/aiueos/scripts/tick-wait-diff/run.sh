#!/bin/sh
# usage: run.sh OUTDIR -- aiueos_plc_rt_begin_scan's release wait over kotoba/tick-wait.o (as it is now in
# kernel/plc_runtime.c, extracted by gen-new.py) against the loop it replaced (old.c, verbatim), under
# qemu-system-x86_64 (TCG) with a real timer interrupt counting the ticks (one per halt): 400 waits with the release
# passed, reached, 1..300 ticks away and 65535 and 65537 ticks away; comparing the tick each stops on. JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/plc_runtime.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "${AIUEOS_KOTOBA_TICK_WAIT_OBJECT:-$aiueos/kotoba/tick-wait.o}"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0190 TICKS 00029774 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_TICK_WAIT_DIFF_OK cases=400 ticks=169844 diffs=0"
