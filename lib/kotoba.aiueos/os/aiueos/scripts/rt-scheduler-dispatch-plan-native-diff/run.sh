#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- rt-scheduler-dispatch-plan.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/rt-scheduler-dispatch-plan.o is now), against the amu 53799cb object it replaced (old.o here, the
# committed object of main 455b84fb, which exports kotoba_aiueos_scheduler_dispatch_plan), under qemu-system-x86_64 (TCG): random 16-slot, 16-byte RT descriptor tables, called with the shipped geometry (256, 16, 16) or one argument disturbed, a state word whose current slot is 0 .. 19 with the quantum-expired bit (256) and random high bits, and a null base; answers and traps compared.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object
# exports the RT kernel's name, so it links beside the old object without a rename. JUN-722, JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
cp "$aiueos/kotoba/rt-scheduler-dispatch-plan.kotoba" "$out/native.kotoba"
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
grep -q 'CASES 00009c40 NONZERO 0000483d DIFFS 0000 TRAPS 0000004f' "$out/serial.txt"
echo "AIUEOS_RT_SCHEDULER_DISPATCH_PLAN_NATIVE_DIFF_OK diffs=0"
