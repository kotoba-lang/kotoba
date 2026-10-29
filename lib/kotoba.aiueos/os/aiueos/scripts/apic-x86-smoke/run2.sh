#!/bin/sh
# usage: run2.sh OUTDIR FUNC CONTRACT OBJECT... -> serial output of the QEMU run
set -eu
out=$1; shift
python3 "$(dirname "$0")/build2.py" "$out" "$@" >/dev/null
rm -f "$out/serial.txt"
timeout 60 qemu-system-x86_64 -kernel "$out/image.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 || true
cat "$out/serial.txt"
