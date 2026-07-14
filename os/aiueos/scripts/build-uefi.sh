#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
esp="$out/esp"
efi="$esp/EFI/BOOT/BOOTX64.EFI"
object="$out/uefi-main.obj"
kernel_dir="$esp/EFI/AIUEOS"
kernel="$kernel_dir/KERNEL.ELF"
kernel_object="$out/kernel-main.o"
kernel_entry_object="$out/kernel-entry.o"
kernel_paging_object="$out/kernel-paging.o"

command -v zig >/dev/null 2>&1 || {
  echo "error: Zig is required to build the freestanding UEFI application" >&2
  exit 1
}

mkdir -p "$(dirname -- "$efi")" "$kernel_dir"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_object" "$aiueos/kernel/main.c"
zig cc -target x86_64-freestanding-none \
  -c -o "$kernel_entry_object" "$aiueos/kernel/entry.S"
zig cc -target x86_64-freestanding-none -std=c11 -O2 \
  -ffreestanding -fno-stack-protector -mno-red-zone \
  -c -o "$kernel_paging_object" "$aiueos/kernel/paging.c"
zig ld.lld -nostdlib -static -z max-page-size=0x1000 \
  -T "$aiueos/kernel/linker.ld" -o "$kernel" \
  "$kernel_entry_object" "$kernel_object" "$kernel_paging_object"
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
[ "$(dd if="$kernel" bs=1 count=4 2>/dev/null | od -An -tx1 | tr -d ' \n')" = 7f454c46 ] || {
  echo "error: $kernel is not an ELF image" >&2
  exit 1
}

echo "$efi"
