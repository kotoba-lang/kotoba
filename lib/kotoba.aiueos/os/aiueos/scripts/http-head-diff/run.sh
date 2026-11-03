#!/bin/sh
# usage: run.sh OUTDIR -- pci.c's HTTP response heads over kotoba/http-head.o against the C they replaced (old.c,
# verbatim): net_http_cid_admit's status line and terminator at the object's own export (the body's SHA-256 after it
# is unchanged C), and rtl8125_http_success through its wrapper (extracted by gen-new.py), under qemu-system-x86_64
# (TCG): 3000 responses (12 status lines -- 1.1 / 1.0 / 2, 200 / 204 / 299 / 2a0 / 301 / 404, case and prefix changes,
# short ones -- headers, the terminator present or broken, bodies up to 4096 bytes), each also without a body, cut, with
# every byte of the status line changed and at every length under 13, plus 2000 random CR / LF-heavy buffers; comparing
# the body offset and the success answer. JUN-552.
set -eu
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(CDPATH= cd -- "$here/../.." && pwd)
out=$1
mkdir -p "$out"
cf="-target x86_64-freestanding-none -std=c11 -O2 -ffreestanding -fno-stack-protector -mno-red-zone -fno-pic -Wall -Werror -Wno-unused-function"
python3 -I "$here/gen-new.py" "$aiueos/kernel/pci.c" "$out/new.c"
zig cc $cf -c -o "$out/old.o" "$here/old.c"
zig cc $cf -c -o "$out/new.o" "$out/new.c"
zig cc $cf -c -o "$out/driver.o" "$here/driver.c"
zig cc -target x86_64-freestanding-none -c -o "$out/entry.o" "$here/entry.S"
zig ld.lld -nostdlib -static -T "$here/link.ld" --oformat binary -o "$out/img.bin" "$out/entry.o" "$out/driver.o" \
  "$out/old.o" "$out/new.o" "$aiueos/kotoba/http-head.o"
rm -f "$out/serial.txt"
timeout 900 qemu-system-x86_64 -kernel "$out/img.bin" -display none -no-reboot -m 64 -cpu qemu64 \
  -debugcon "file:$out/serial.txt" -device isa-debug-exit,iobase=0xf4,iosize=4 >/dev/null 2>&1 || true
grep -q DONE "$out/serial.txt"
grep -q 'CASES 14ff0 BODY 141e SUCCESS 0ffa DIFFS 0000' "$out/serial.txt"
echo "AIUEOS_HTTP_HEAD_DIFF_OK cases=86000 body=5150 success=4090 diffs=0"
