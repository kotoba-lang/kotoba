#!/bin/sh
# usage: run.sh OUTDIR -- the split-virtqueue ring operations over kotoba/virtq-ring.o against the C they replaced
# (old.c: virtio_rng's and rng_refill's ring writes verbatim, and the same struct-field writes / reads for any slot),
# under qemu-system-x86_64 (TCG): 4000 rounds of virtio_rng's first request, rng_refill's (the available index wrapping
# through 0xffff), 8 posts at random slots, positions, lengths, flags, next and indices, the two refusals (a slot or a
# ring position past the page, nothing written), and used-ring reads at random slots and past the page; comparing the
# answers and both 4 KiB pages whole. JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$aiueos/kotoba/virtq-ring.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 157c0 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_VIRTQ_RING_DIFF_OK cases=88000 diffs=0"
