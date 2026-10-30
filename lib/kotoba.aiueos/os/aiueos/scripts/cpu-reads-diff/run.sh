#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/cpu-reads.o against the C it replaced (old.c, verbatim: device_result.c's cpuid / rdrand64 /
# aiueos_cpu_random_bytes and qwen35_infer.c's read_cycles), under qemu-system-x86_64 (TCG) on three CPU models -- qemu64
# (no RDRAND), qemu64,+f16c (no RDRAND, CPUID.1:ECX[29] set) and max (RDRAND): read_cycles lies between two C reads 1000
# times; the random bytes give the C's status at 12 sizes up to 16384, write every byte on success and nothing past n,
# and leave the buffer untouched on refusal. JUN-554 / amu ADR 0389.
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
  "$out/old.o" "$aiueos/kotoba/cpu-reads.o"
for cpu in qemu64 qemu64,+f16c max; do
  rm -f "$out/serial.txt"
  timeout 300 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu "$cpu" \
    -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
  grep -q DONE "$out/serial.txt"
  case "$cpu" in max) want='CASES 03f7 RANDOM-OK 0c DIFFS 0000' ;; *) want='CASES 03f7 RANDOM-OK 00 DIFFS 0000' ;; esac
  grep -q "$want" "$out/serial.txt"
done
echo "AIUEOS_CPU_READS_DIFF_OK cases=1015x3 models=qemu64,qemu64+f16c,max diffs=0"
