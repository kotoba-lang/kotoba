#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- allocator-plan.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/allocator-plan.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 118b8e69), under qemu-system-x86_64 (TCG): 256-record, 16-byte allocation tables (page words zero, small, near 2^32 or random; active bytes 0, 1 or random; one free record at a random place or none), called with the shipped geometry (4096, 256, 16) or one argument disturbed, claim requests (0) and release requests naming every slot with its own page, another page or page 0, and a null table; answers and traps compared.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object is
# recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_allocator_plan/kotoba_aiueos_allocator_plan_native/' "$aiueos/kotoba/allocator-plan.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -I"$here/../ud-guard" -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig cc -target x86_64-freestanding-none -c -o "$out/guard.o" "$here/../ud-guard/guard.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/guard.o" "$here/old.o" "$out/native.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'CASES' "$out/serial.txt"
grep -q 'CASES 00002ee0 NONZERO 00000879 DIFFS 0000 TRAPS 00000019' "$out/serial.txt"
echo "AIUEOS_ALLOCATOR_PLAN_NATIVE_DIFF_OK diffs=0"
