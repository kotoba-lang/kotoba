#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- relay-hello-payload.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/relay-hello-payload.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 40ab625f), under qemu-system-x86_64 (TCG): native export takes the MAC's length after the MAC (6 here, as kernel/pci.c passes). Random and edge nonce halves (0, 2^31, 2^32 - 1, negative, past 2^32 - 1), random MACs, capacities 0 .. 512 (around 91 and 160 most often), and null out or MAC pointers; each object writes its own copy of the same random-filled buffer, and the answers, the trap outcomes and every byte of the two buffers (600 bytes) are compared.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object is
# recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_relay_hello_payload/kotoba_aiueos_relay_hello_payload_native/' "$aiueos/kotoba/relay-hello-payload.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -mgeneral-regs-only -I"$here/../ud-guard" -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig cc -target x86_64-freestanding-none -c -o "$out/guard.o" "$here/../ud-guard/guard.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/guard.o" "$here/old.o" "$out/native.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'CASES' "$out/serial.txt"
grep -q 'CASES 00007530 NONZERO 000055ab DIFFS 0000 TRAPS 000001de' "$out/serial.txt"
echo "AIUEOS_RELAY_HELLO_PAYLOAD_NATIVE_DIFF_OK diffs=0"
