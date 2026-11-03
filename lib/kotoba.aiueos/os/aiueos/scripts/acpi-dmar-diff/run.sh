#!/bin/sh
# usage: run.sh OUTDIR -- kernel/acpi.c's parse_dmar over kotoba/acpi-dmar-parse.o (as it is now, extracted by gen-new.py)
# against the C it replaced (old.c, verbatim), under qemu-system-x86_64 (TCG): 4000 generated DMAR tables -- DRHDs on
# segment 0 and others with device scopes (odd paths included), other remapping structures, host address widths
# 30 / 31 / 63 / 64 and random, zero / unaligned / >= 2^52 / >= 2^63 register bases, truncated tables, wrong structure
# and scope lengths, tables shorter than header + 12, a corrupted byte -- comparing the return value and the four
# discovered_dmar globals. JUN-552.
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
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/acpi-dmar-parse.o"
rm -f "$out/serial.txt"
timeout 300 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0fa0 ACCEPTED 03de FOUND 0709 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_ACPI_DMAR_DIFF_OK cases=4000 accepted=990 found=1801 diffs=0"
