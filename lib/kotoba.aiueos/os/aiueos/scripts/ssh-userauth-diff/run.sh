#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's SSH publickey userauth parsing over kotoba/ssh-userauth.o (the wrappers as they are now
# in kernel/pci.c, extracted by gen-new.py) against the C it replaced (old.c, verbatim), under qemu-system-x86_64 (TCG):
# 600 generated USERAUTH_REQUESTs -- "none" and "publickey", with and without a signature, other methods, services and
# message numbers, ecdsa-sha2-nistp256 and other algorithms, authorized and unauthorized P-256 blobs, one X or Y byte off,
# a 64-byte point -- each truncated, with every byte flipped (every sixth request) and length bytes moved by one, and 400
# bare blobs; comparing the method checks, the publickey fields (has_sig, the algorithm and blob pointers and lengths,
# the offset after the key) and the authorized-key result with its 64 output bytes. JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function -Wno-unused-variable"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/ssh-userauth.o"
rm -f "$out/serial.txt"
timeout 600 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 05fbb AUTHORIZED 0177 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_SSH_USERAUTH_DIFF_OK cases=24507 authorized=375 diffs=0"
