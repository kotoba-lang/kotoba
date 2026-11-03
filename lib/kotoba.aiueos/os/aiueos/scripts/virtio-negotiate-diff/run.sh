#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's negotiate over kotoba/virtio-negotiate.o (the wrapper as it is now in kernel/pci.c,
# extracted by gen-new.py) against the C it replaced (old.c, verbatim), under qemu-system-x86_64 (TCG) behind the MMIO
# trap harness (scripts/mmio-trap): an emulated device whose device_feature follows the select, whose status 0 resets it
# (or not), and which keeps or refuses FEATURES_OK, over 4000 random register files with VIRTIO_F_VERSION_1 offered or
# not; comparing the answer, every bus transaction in order (reads, writes and their values) and the registers after.
# JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
trap=$aiueos/scripts/mmio-trap
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc $cf -mgeneral-regs-only -c -o "$out/trap.o" "$trap/trap.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$trap/entry.S"
zig ld.lld -nostdlib -static -T "$trap/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/trap.o" "$out/old.o" "$out/new.o" "$aiueos/kotoba/virtio-negotiate.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 0fa0 NEGOTIATED 0855 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_VIRTIO_NEGOTIATE_DIFF_OK cases=4000 negotiated=2133 diffs=0"
