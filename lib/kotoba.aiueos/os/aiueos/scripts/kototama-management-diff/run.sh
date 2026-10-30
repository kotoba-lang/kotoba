#!/bin/sh
# usage: run.sh OUTDIR -- aiueos_kototama_runtime_management_command over kotoba/kototama-management.o (as it is now in
# kernel/kototama_runtime.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim), under
# qemu-system-x86_64 (TCG): 12 commands (the three, prefixes, extensions, case and spacing changes, empty) x 8 runtime
# states x restart allowed / refused x 22 output capacities, null output and null command, and every single-byte change of
# the three commands; return value, output buffer, restart calls and the reboot-pxe flag are compared. JUN-554.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-object.py" "$out/gen.kotoba"
cmp -s "$out/gen.kotoba" "$aiueos/kotoba/kototama-management.kotoba" || { echo "kototama-management.kotoba is not gen-object.py's output" >&2; exit 1; }
python3 -I "$here/gen-new.py" "$aiueos/kernel/kototama_runtime.c" "$out/new.c"
zig cc $cf -I"$here" -I"$aiueos/kernel" -c -o "$out/old.o" "$here/old.c"
zig cc $cf -I"$here" -I"$aiueos/kernel" -c -o "$out/new.o" "$out/new.c"
zig cc $cf -I"$here" -I"$aiueos/kernel" -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/kototama-management.o"
rm -f "$out/serial.txt"
timeout 300 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 010c1 REPLIED 00605 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_KOTOTAMA_MANAGEMENT_DIFF_OK cases=4289 replied=1541 diffs=0"
