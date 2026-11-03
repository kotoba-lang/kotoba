#!/bin/sh
# usage: run.sh OUTDIR -- kbd_recycle over kotoba/kbd-reap.o (as it is now in kernel/pci.c, extracted by gen-new.py)
# against the C it replaced (old.c, verbatim) under qemu-system-x86_64 (TCG): 100000 reaps over random used rings,
# ids, events and positions for want 0, 1 and 2, comparing the key answered, the position, the event counter, the
# available ring, the doorbell and that the used ring and events are left as they were. JUN-598.
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
  "$out/old.o" "$out/new.o" "${AIUEOS_KOTOBA_KBD_REAP_OBJECT:-$aiueos/kotoba/kbd-reap.o}"
rm -f "$out/serial.txt"
timeout 1500 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 186a0 KEYS 02018 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_KBD_REAP_DIFF_OK cases=100000 keys=8216 diffs=0"
