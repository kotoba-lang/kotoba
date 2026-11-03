#!/bin/sh
# usage: run.sh OUTDIR -- kotoba/xstate-setup.o against qwen35_infer.c's prepare_bsp_extended_state and cpu_has_avx2 as they
# were (old.c, verbatim), under qemu-system-x86_64 (TCG) on five CPU models -- qemu64 (no XSAVE), qemu64,+xsave (no AVX),
# SandyBridge (AVX, no AVX2), Haswell and max (AVX2): the AVX2 answer before setup, CR4 and XCR0 after it (each version
# from the same start state), and the AVX2 answer after it. JUN-554 / amu ADR 0390.
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
  "$out/old.o" "$aiueos/kotoba/xstate-setup.o"
for cpu in qemu64 qemu64,+xsave SandyBridge Haswell max; do
  rm -f "$out/serial.txt"
  timeout 120 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu "$cpu" \
    -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
  grep -q DONE "$out/serial.txt"
  grep -q 'DIFFS 00' "$out/serial.txt"
  case "$cpu" in
    Haswell|max) grep -q 'XCR0 00000007 00000007 AVX2 1 1' "$out/serial.txt" ;;
    SandyBridge) grep -q 'XCR0 00000007 00000007 AVX2 0 0' "$out/serial.txt" ;;
    *) grep -q 'CR4 00000620 00000620 XCR0 00000000 00000000 AVX2 0 0' "$out/serial.txt" ;;
  esac
done
echo "AIUEOS_XSTATE_SETUP_DIFF_OK models=qemu64,qemu64+xsave,SandyBridge,Haswell,max diffs=0"
