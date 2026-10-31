#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- ecdsa-p256.kotoba as built on amu's native object route by COMPILER (amu main's Mac
# full root, amu-full-root.macho; as kotoba/ecdsa-p256.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main caf31e54), under qemu-system-x86_64 (TCG): the Wycheproof, RFC 6979 and random cases driver.c describes.
# Both are called through the #UD guard (../ud-guard), so a trap is compared as well as an answer. The native object is
# recompiled under a test name from the source, so the two can be linked together. The cases are split over 8 images
# (driver.c built with -DSHARD=k -DNSHARD=8 takes cases k, k+8, ...) run in parallel; their CASES lines are summed. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1 compiler=$2 n=8
mkdir -p "$out"
sed 's/kotoba_aiueos_ecdsa_p256_sha256_verify/kotoba_aiueos_ecdsa_p256_sha256_verify_native/' "$aiueos/kotoba/ecdsa-p256.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 2147483647 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig cc -target x86_64-freestanding-none -c -o "$out/guard.o" "$here/../ud-guard/guard.S"
k=0
while [ $k -lt $n ]; do
  zig cc $cf -mgeneral-regs-only -DSHARD=$k -DNSHARD=$n -I"$here/../ud-guard" -c -o "$out/driver$k.o" "$here/driver.c"
  zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img$k.bin" "$out/entry.o" "$out/driver$k.o" \
    "$out/guard.o" "$here/old.o" "$out/native.o"
  rm -f "$out/serial$k.txt"
  (timeout 3600 qemu-system-x86_64 -kernel "$out/img$k.bin" -display none -no-reboot -m 64 -cpu qemu64 \
    -debugcon "file:$out/serial$k.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true) &
  k=$((k + 1))
done
wait
k=0
while [ $k -lt $n ]; do grep -q DONE "$out/serial$k.txt"; sed "s/^/SHARD$k /" "$out/serial$k.txt" | grep -v ' DONE$'; k=$((k + 1)); done
cat "$out"/serial[0-9]*.txt | awk 'function h(s,  i, v) { v = 0; for (i = 1; i <= length(s); i++) v = v * 16 + index("0123456789abcdef", substr(s, i, 1)) - 1; return v }
  /^CASES /{c+=h($2); z+=h($4); d+=h($6); t+=h($8)}
  END {printf "CASES %08x NONZERO %08x DIFFS %04x TRAPS %08x\n", c, z, d, t}' > "$out/serial.txt"
grep 'CASES' "$out/serial.txt"
grep -q 'CASES 000002d6 NONZERO 000000e3 DIFFS 0000 TRAPS 00000004' "$out/serial.txt"
echo "AIUEOS_ECDSA_P256_NATIVE_DIFF_OK diffs=0"
