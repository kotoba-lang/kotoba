#!/bin/sh
# usage: run-pair.sh HERE OUT NAME EXPORT COMPILER QEMU-ARGS -- shared by the port-I/O differentials (JUN-552): builds
# HERE/driver.c twice, once against the kotoba-compiler/1 object (HERE/old.o) and once against NAME.kotoba rebuilt by
# COMPILER on the native route under EXPORT_native (-DNATIVE), boots each under qemu-system-x86_64 (TCG) with every
# device-register access traced, and compares the two traces and the two debugcon logs (compare.py), leaving the
# result in OUT/summary.txt for run.sh to check.
set -eu
here=$1 out=$2 name=$3 ex=$4 compiler=$5 qargs=$6
pt=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$pt/../.." && pwd)
mkdir -p "$out"
sed "s/$ex/${ex}_native/" "$aiueos/kotoba/$name.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
for side in old new; do
  if [ $side = old ]; then def=; obj=$here/old.o; else def=-DNATIVE; obj=$out/native.o; fi
  zig cc $cf $def -mgeneral-regs-only -c -o "$out/driver-$side.o" "$here/driver.c"
  zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img-$side.bin" "$out/entry.o" \
    "$out/driver-$side.o" "$obj"
  rm -f "$out/serial-$side.txt" "$out/trace-$side.txt"
  # shellcheck disable=SC2086
  timeout 900 qemu-system-x86_64 -kernel "$out/img-$side.bin" -display none -no-reboot -m 64 $qargs \
    -trace 'memory_region_ops_*' -D "$out/trace-$side.txt" \
    -debugcon "file:$out/serial-$side.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
  grep -q DONE "$out/serial-$side.txt"
done
python3 -I "$pt/compare.py" "$out/trace-old.txt" "$out/trace-new.txt" "$out/serial-old.txt" "$out/serial-new.txt" \
  > "$out/summary.txt" || true
cat "$out/summary.txt"
