#!/bin/sh
# usage: run.sh OUTDIR -- aiueos_acpi_initialize's MADT walk over kotoba/acpi-madt-parse.o (as it is now in kernel/acpi.c,
# extracted by gen-new.py) against the C it replaced (old.c, verbatim), under qemu-system-x86_64 (TCG): 6000 generated
# MADTs -- Local APIC and x2APIC entries under every flag combination, more than 256 enabled processors, up to 18 I/O
# APICs (zero, unaligned, duplicate GSI bases, 0xfec00000 or not), timer overrides on and off bus 0 / source 0, other
# entry types, truncation, short lengths, a corrupted byte -- comparing the return value and the 260 words of discovered
# state. JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function -Wno-unused-variable"
python3 -I "$here/gen-new.py" "$aiueos/kernel/acpi.c" "$out/new.c"
zig cc $cf -I"$here" -c -o "$out/old.o" "$here/old.c"
zig cc $cf -I"$here" -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/acpi-madt-parse.o"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 1770 ACCEPTED 0166 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_ACPI_MADT_DIFF_OK cases=6000 accepted=358 diffs=0"
