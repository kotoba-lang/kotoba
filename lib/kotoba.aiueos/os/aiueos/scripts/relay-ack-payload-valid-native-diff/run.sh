#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- relay-ack-payload-valid.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/relay-ack-payload-valid.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main 40ab625f), under qemu-system-x86_64 (TCG): The 55-byte ACK "AIUEOS_NODE_ACK_V1 boot=<16 hex> state=accepted" for random nonces (and nonce halves at 0, 2^31 and 2^32 - 1), then one byte mutated in turn (each position, to a random byte, an upper-case hex digit or a neighbour), the expected nonce halves off by one, negative or past 2^32 - 1, lengths other than 55, and a null payload; answers and traps compared.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object is
# recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_relay_ack_payload_valid/kotoba_aiueos_relay_ack_payload_valid_native/' "$aiueos/kotoba/relay-ack-payload-valid.kotoba" > "$out/native.kotoba"
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
grep -q 'CASES 00009c40 NONZERO 00003040 DIFFS 0000 TRAPS 0000009c' "$out/serial.txt"
echo "AIUEOS_RELAY_ACK_PAYLOAD_VALID_NATIVE_DIFF_OK diffs=0"
