#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- app-catalog-valid.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/app-catalog-valid.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 118b8e69), under qemu-system-x86_64 (TCG): Valid aiuefs-v3 catalogs of 1 .. 4 entries (printable NUL-padded ids, disjoint extents of 1 .. 12288 bytes, each signature sector past its extent, signer 1) with a routing pair outside every extent, then one thing mutated in turn: the magic, the version, the count against the length, an id byte (empty, out of range, a byte after the NUL, a duplicate id), an extent or signature sector moved onto a neighbour's or onto a routing sector, a length at 0 or 12289, the capacity at the last extent's end or signature, the signer, the routing sectors, the routing length; plus random catalogs, lengths outside 80 .. 272, and null catalog or routing pointers; answers and traps compared.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object is
# recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_app_catalog_valid/kotoba_aiueos_app_catalog_valid_native/' "$aiueos/kotoba/app-catalog-valid.kotoba" > "$out/native.kotoba"
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
grep -q 'CASES 00007530 NONZERO 00001819 DIFFS 0000 TRAPS 0000022e' "$out/serial.txt"
echo "AIUEOS_APP_CATALOG_VALID_NATIVE_DIFF_OK diffs=0"
