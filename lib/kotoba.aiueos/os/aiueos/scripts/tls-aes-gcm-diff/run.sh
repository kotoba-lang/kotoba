#!/bin/sh
# usage: run.sh OUTDIR -- the C kernel/tls_aes_gcm.c and kotoba/tls-aes-gcm.o + kotoba/bytes.o, each linked with driver.c and the
# committed AES-GCM objects into a flat Multiboot image, run under qemu-system-x86_64 (TCG); the two serial logs must be identical.
# JUN-556. Executed, not booted in the kernel.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig cc $cf -I"$aiueos/kernel" -c -o "$out/c-tls.o" "$aiueos/kernel/tls_aes_gcm.c"
k="$aiueos/kotoba"
for v in c kotoba; do
  if [ $v = c ]; then objs="$out/c-tls.o"; else objs="$k/tls-aes-gcm.o $k/bytes.o"; fi
  # shellcheck disable=SC2086
  zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img-$v.bin" \
    "$out/entry.o" "$out/driver.o" $objs "$k/aes128-gcm.o" "$k/aes128-gcm-selftest.o"
  rm -f "$out/serial-$v.txt"
  timeout 300 qemu-system-x86_64 -kernel "$out/img-$v.bin" -display none -no-reboot -m 64 -cpu qemu64 \
    -debugcon "file:$out/serial-$v.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
done
grep -q DONE "$out/serial-c.txt"
cmp "$out/serial-c.txt" "$out/serial-kotoba.txt"
echo "AIUEOS_TLS_AES_GCM_DIFF_OK cases=$(grep -c 'aad=' "$out/serial-c.txt")"
