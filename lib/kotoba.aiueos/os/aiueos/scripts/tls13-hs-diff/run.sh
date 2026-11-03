#!/bin/sh
# usage: run.sh OUTDIR -- kernel/tls13.c's handshake state machine over kotoba/tls13-hs.o (consume_hs_messages,
# process_record and aiueos_tls13_feed as they are now, extracted by gen-new.py) against the C it replaced (old.c,
# verbatim), both over prelude.h's scripted callees, under qemu-system-x86_64 (TCG): 360 record streams (ServerHello, an
# encrypted flight with messages dropped, reordered, retyped, oversize or split across records, then application data,
# NewSessionTicket, alerts, close_notify, unknown types, a corrupted byte) fed in 5 chunk sizes under 3 callee scripts;
# the callee trace and the final state are compared. JUN-553.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/tls13.c" "$out/new.c"
zig cc $cf -I"$here" -c -o "$out/old.o" "$here/old.c"
zig cc $cf -I"$here" -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/tls13-hs.o"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 01518 READY 0027d APP 00158 DIFFS 00000' "$out/serial.txt"
echo "AIUEOS_TLS13_HS_DIFF_OK runs=5400 ready=637 app=344 diffs=0"
