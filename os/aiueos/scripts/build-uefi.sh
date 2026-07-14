#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
esp="$out/esp"
efi="$esp/EFI/BOOT/BOOTX64.EFI"
object="$out/uefi-main.obj"

command -v zig >/dev/null 2>&1 || {
  echo "error: Zig is required to build the freestanding UEFI application" >&2
  exit 1
}

mkdir -p "$(dirname -- "$efi")"
zig cc -target x86_64-windows-gnu -std=c11 -O2 \
  -ffreestanding -fshort-wchar -fno-stack-protector -mno-red-zone \
  -c -o "$object" "$aiueos/uefi/main.c"
zig lld-link /subsystem:efi_application /entry:efi_main /nodefaultlib \
  /fixed:no "/out:$efi" "$object"

magic=$(dd if="$efi" bs=1 count=2 2>/dev/null)
[ "$magic" = MZ ] || {
  echo "error: $efi is not a PE/COFF image" >&2
  exit 1
}

echo "$efi"
