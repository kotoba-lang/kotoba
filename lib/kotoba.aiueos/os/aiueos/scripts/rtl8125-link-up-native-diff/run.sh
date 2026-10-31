#!/bin/sh
# usage: run.sh OUTDIR COMPILER -- rtl8125-link-up.kotoba as built on amu's native object route by COMPILER (the Mac root's
# F2-signed.macho; as kotoba/rtl8125-link-up.o is now), against the kotoba-compiler/1 object it replaced (old.o here, the
# committed object of main ce88ee0d), under qemu-system-x86_64 (TCG) behind the MMIO trap harness (../mmio-trap): the MMIO trap harness (../mmio-trap). Random 4 KiB register files whose PHYSTATUS (0x6c) has the link bit set or clear, with the window length 4096 or another; both objects start from the same registers, and the answers, every bus transaction in order (the FNV trace and the count) and the registers after are compared.
# The native object is recompiled under a test name from the source, so the two can be linked together. JUN-708.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
trap=$aiueos/scripts/mmio-trap
out=$1 compiler=$2
mkdir -p "$out"
sed 's/kotoba_aiueos_rtl8125_link_up/kotoba_aiueos_rtl8125_link_up_native/' "$aiueos/kotoba/rtl8125-link-up.kotoba" > "$out/native.kotoba"
rm -f "$out/native.o"
(cd "$out" && "$compiler" compile native.kotoba --target x86_64-aiueos-kernel-v1 --output native.o --fuel 4194304 3<. </dev/null >/dev/null)
test -f "$out/native.o"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc $cf -mgeneral-regs-only -c -o "$out/trap.o" "$trap/trap.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$trap/entry.S"
zig ld.lld -nostdlib -static -T "$trap/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/trap.o" "$here/old.o" "$out/native.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep 'CASES' "$out/serial.txt"
grep -q 'CASES 1770 ADMITTED 0a79 DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_RTL8125_LINK_UP_NATIVE_DIFF_OK diffs=0"
