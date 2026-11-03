#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- rtl8125-ring-build.kotoba as built on amu's native object route by COMPILER (amu main's Mac
# full root, amu-full-root.macho; as kotoba/rtl8125-ring-build.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 90e7f59a), under qemu-system-x86_64 (TCG): random descriptor memory at a 256-aligned base, a base off by 8..248, or a null base; descriptor length 32 or another; frame addresses positive, zero, negative or near 2^63; kind -1..2; capacity 0..2049, the kernel's 2048 or random. Both objects start from the same 768 random bytes; answers, traps (through the #UD guard) and every byte are compared.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object is
# recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_rtl8125_ring_build/kotoba_aiueos_rtl8125_ring_build_native/' "$aiueos/kotoba/rtl8125-ring-build.kotoba" > "$out/native.kotoba"
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
grep -q 'CASES 00004e20 NONZERO 000035ce DIFFS 0000 TRAPS 00000000' "$out/serial.txt"
echo "AIUEOS_RTL8125_RING_BUILD_NATIVE_DIFF_OK diffs=0"
