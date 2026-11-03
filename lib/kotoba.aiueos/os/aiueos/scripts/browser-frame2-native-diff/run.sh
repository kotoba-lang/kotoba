#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- browser-frame2.kotoba as built on amu's native object route by COMPILER (amu main's Mac
# full root, amu-full-root.macho; as kotoba/browser-frame2.o is now), against the kotoba-compiler/1 object it replaced (old.o
# here, the committed object of main 80fd051f), under qemu-system-x86_64 (TCG), on the kernel's desktop-loop inputs and
# the edge inputs driver.c describes; the other two browser objects are the kernel's (kotoba/browser-ime.o, kotoba/browser-reduce.o).
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer and every state byte.
# The native object is recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_browser_frame2/kotoba_aiueos_browser_frame2_native/' "$aiueos/kotoba/browser-frame2.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 2147483647 3<. </dev/null >/dev/null)
test -f "$out/native.o"
sed -e "s|@FONT@|$aiueos/fonts/aiueos-16.fnt|" -e "s|@DICT@|$aiueos/ime/aiueos-kanji.dic|" "$here/assets.S" > "$out/assets.S"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -I"$here/../ud-guard" -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig cc -target x86_64-freestanding-none -c -o "$out/guard.o" "$here/../ud-guard/guard.S"
zig cc -target x86_64-freestanding-none -c -o "$out/assets.o" "$out/assets.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/guard.o" "$out/assets.o" "$here/old.o" "$out/native.o" "$aiueos/kotoba/browser-ime.o" "$aiueos/kotoba/browser-reduce.o"
rm -f "$out/serial.txt"
timeout 3000 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'CASES' "$out/serial.txt"
grep -q 'CASES 0000cc55 NONZERO 0000cc55 DIFFS 0000 TRAPS 00000000' "$out/serial.txt"
echo "AIUEOS_BROWSER_FRAME2_NATIVE_DIFF_OK diffs=0"
