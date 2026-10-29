#!/bin/sh
# usage: run.sh OBJECT OUTDIR  -> prints the serial output of the QEMU x86 TCG run
set -eu
python3 "$(dirname "$0")/build.py" "$1" "$2" >/dev/null
rm -f "$2/serial.txt"
timeout 30 qemu-system-x86_64 -kernel "$2/image.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$2/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 || true
cat "$2/serial.txt"
