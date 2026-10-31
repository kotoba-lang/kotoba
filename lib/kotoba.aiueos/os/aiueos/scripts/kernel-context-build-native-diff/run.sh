#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- kernel-context-build.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/kernel-context-build.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 118b8e69), under qemu-system-x86_64 (TCG): native export takes the stack's length right after the stack; the old one took (stack, entry, argument) and wrote inside a fixed 4 KiB window. Each case fills a stack buffer with random bytes, places the stack at offset 0 .. 15 in it, and calls the old object and the native one (length 4096, or 4097 .. 16384) with the same entry and argument words (random, small, higher-half, the i64 extremes); each call starts from the same buffer bytes at the same address (the kernel frame stores its own stack address), and the answers, the trap outcomes and every byte of the buffer after each call are compared. A null stack is included.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object is
# recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_kernel_context_build/kotoba_aiueos_kernel_context_build_native/' "$aiueos/kotoba/kernel-context-build.kotoba" > "$out/native.kotoba"
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
grep -q 'CASES 00001770 NONZERO 00001734 DIFFS 0000 TRAPS 0000003c' "$out/serial.txt"
echo "AIUEOS_KERNEL_CONTEXT_BUILD_NATIVE_DIFF_OK diffs=0"
