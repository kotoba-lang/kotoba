#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- msr-write.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/msr-write.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the committed
# object of main 9f16e6ce), both linked into one image and called through the #UD guard (../ud-guard) under
# qemu-system-x86_64 (TCG) on qemu64 and max. The native object is recompiled under a test name from the source, so the two
# can be linked together. JUN-552 / amu ADR 0399.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_msr_write/kotoba_aiueos_msr_write_native/' "$aiueos/kotoba/msr-write.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -I"$here/../ud-guard" -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig cc -target x86_64-freestanding-none -c -o "$out/guard.o" "$here/../ud-guard/guard.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/guard.o" "$here/old.o" "$out/native.o"
for cpu in qemu64 max; do
  rm -f "$out/serial-$cpu.txt"
  timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu $cpu \
    -debugcon "file:$out/serial-$cpu.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
  grep -q DONE "$out/serial-$cpu.txt"
  grep 'CASES' "$out/serial-$cpu.txt"
  grep -qx 'CASES 00000714 NONZERO 00000390 DIFFS 0000 TRAPS 00000000 ' "$out/serial-$cpu.txt"
  grep -qx 'BOUND 03 OLD-WROTE 03 NATIVE-TRAPPED 03 ' "$out/serial-$cpu.txt"
done
echo "AIUEOS_msr_write_NATIVE_DIFF_OK diffs=0" | tr a-z A-Z
