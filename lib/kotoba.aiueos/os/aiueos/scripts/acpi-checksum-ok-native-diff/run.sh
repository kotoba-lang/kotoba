#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- acpi-checksum-ok.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/acpi-checksum-ok.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 83f97125), under qemu-system-x86_64 (TCG), comparing the answer for every tuple driver.c
# makes. The native object is recompiled under a test name from the source, so the two can be linked together. JUN-600.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_acpi_checksum_ok/kotoba_aiueos_acpi_checksum_ok_native/' "$aiueos/kotoba/acpi-checksum-ok.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$here/old.o" "$out/native.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'CASES' "$out/serial.txt"
grep -q 'CASES 00000fa5 NONZERO 000007d8 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_ACPI_CHECKSUM_OK_NATIVE_DIFF_OK diffs=0"
