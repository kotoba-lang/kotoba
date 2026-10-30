#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's prepare_queue_index over kotoba/virtio-queue.o (the wrapper as it is now in
# kernel/pci.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim), under qemu-system-x86_64 (TCG)
# behind the MMIO trap harness (scripts/mmio-trap): an emulated device with four queues (maximum sizes, enable bits,
# notify offsets, rings; queue_select shows the selected one, a size above the maximum is clamped), 6000 setups (indices
# 0..5, sizes, multipliers, notify capability lengths, already-enabled queues); comparing the doorbell pointer, every bus
# transaction in order, the registers and every queue's state after. JUN-598.
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
  "$out/trap.o" "$out/old.o" "$out/new.o" "$aiueos/kotoba/virtio-queue.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 1770 PROGRAMMED 06da DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_VIRTIO_QUEUE_DIFF_OK cases=6000 programmed=1754 diffs=0"
