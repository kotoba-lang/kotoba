#!/bin/sh
# usage: run.sh OUTDIR -- kernel/job_protocol.c and kotoba/job-protocol.o, each linked with driver.c and the committed
# kotoba/job-protocol-dispatch.o into a flat Multiboot image, run under qemu-system-x86_64 (TCG); the two serial logs must be
# identical. driver.c carries the 96 wire vectors of contracts/job-protocol-v1.edn. JUN-553. Executed, not booted in the kernel.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic"
zig cc $cf -I"$aiueos/kernel" -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig cc $cf -I"$aiueos/kernel" -c -o "$out/c-jp.o" "$aiueos/kernel/job_protocol.c"
for v in c kotoba; do
  if [ $v = c ]; then glue="$out/c-jp.o"; else glue="$aiueos/kotoba/job-protocol.o"; fi
  zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img-$v.bin" \
    "$out/entry.o" "$out/driver.o" "$glue" "$aiueos/kotoba/job-protocol-dispatch.o"
  rm -f "$out/serial-$v.txt"
  timeout 300 qemu-system-x86_64 -kernel "$out/img-$v.bin" -display none -no-reboot -m 64 -cpu qemu64 \
    -debugcon "file:$out/serial-$v.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
done
grep -q DONE "$out/serial-c.txt"
cmp "$out/serial-c.txt" "$out/serial-kotoba.txt"
echo "AIUEOS_JOB_PROTOCOL_DIFF_OK lines=$(wc -l < "$out/serial-c.txt" | tr -d ' ')"
