#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's find_virtio_caps over kotoba/virtio-caps.o (the wrapper as it is now in kernel/pci.c,
# extracted by gen-new.py) against the C it replaced (old.c, verbatim, over kotoba/virtio-cap-valid.o as in the kernel),
# both reading one synthetic 256-byte configuration space, under qemu-system-x86_64 (TCG): 30000 generated capability
# chains (common / notify / device / other vendor kinds, MSI-X, MSI, others; random lengths, BARs, offsets and extents,
# the capability bit off, misaligned starts, loops), each also with one byte changed and some with a capability at 0xfc,
# plus 4000 edge chains (MSI-X at 0xf4 / 0xf8, common configurations of 55 / 56 bytes), 47- and 48-step chains and
# noise; comparing the answer and, when admitted, every field of the capabilities. JUN-598.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/virtio-caps.o" "$aiueos/kotoba/virtio-cap-valid.o"
rm -f "$out/serial.txt"
timeout 1200 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 130b0 ADMITTED 08b2 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_VIRTIO_CAPS_DIFF_OK cases=78000 admitted=2226 diffs=0"
