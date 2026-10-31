#!/bin/sh
# usage: run-models.sh HERE OUT NAME EXPORT COMPILER -- shared by the CPUID differentials (JUN-552): NAME.kotoba rebuilt
# by COMPILER on the native route under EXPORT_native, linked with the kotoba-compiler/1 object (HERE/old.o) and
# HERE/driver.c (ap.h), booted under qemu-system-x86_64 (TCG) on each CPU model and topology below; every processor
# answers through both objects. OUT/summary.txt totals the cases, nonzero answers and differences over all models.
set -eu
here=$1 out=$2 name=$3 ex=$4 compiler=$5
ap=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$ap/../.." && pwd)
mkdir -p "$out"
sed "s/$ex/${ex}_native/" "$aiueos/kotoba/$name.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$ap/entry.S"
total=0 nz=0 bad=0 models=0
# -smp topology (8 processors over 2 sockets x 2 cores x 2 threads gives Local APIC ids 0 .. 7; 6 over 2 x 3 gives
# 0 1 2 4 5 6) ; CPU model (with and without NX and SYSCALL, and an extended-leaf ceiling below and at 0x80000001)
for cfg in "8,sockets=2,cores=2,threads=2;qemu64" "6,sockets=2,cores=3;qemu64,-nx" "4;qemu64,-syscall" \
           "2;qemu64,-nx,-syscall" "2;qemu64,xlevel=0x80000000" "2;qemu64,xlevel=0x80000001" "4;max" "1;max,-nx"; do
  smp=${cfg%%;*} cpu=${cfg#*;} n=${smp%%,*}
  zig cc $cf -DNCPU="$n" -mgeneral-regs-only -I"$ap" -c -o "$out/driver.o" "$here/driver.c"
  zig ld.lld -nostdlib -static -T "$ap/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
    "$here/old.o" "$out/native.o"
  rm -f "$out/serial.txt"
  timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu "$cpu" -smp "$smp" \
    -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
  grep -q DONE "$out/serial.txt"
  line=$(grep '^CPUS' "$out/serial.txt"); set -- $line
  [ "$((0x$2))" = "$n" ] || { echo "only $((0x$2)) of $n processors answered under $cpu"; exit 1; }
  echo "$cpu -smp $smp: $line ids $(grep '^CPU ' "$out/serial.txt" | awk '{printf "%s:%s ", $2, $3}')"
  total=$((total + 0x$4)) nz=$((nz + 0x$6)) bad=$((bad + 0x$8)) models=$((models + 1))
done
printf 'CASES %08x NONZERO %08x DIFFS %04x MODELS %d\n' "$total" "$nz" "$bad" "$models" > "$out/summary.txt"
cat "$out/summary.txt"
