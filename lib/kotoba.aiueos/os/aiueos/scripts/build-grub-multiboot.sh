#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}
mb="$out/multiboot"
grub_root="$mb/grub-root"
iso="$mb/aiueos-grub.iso"
mkrescue=${GRUB_MKRESCUE:-x86_64-elf-grub-mkrescue}

command -v "$mkrescue" >/dev/null 2>&1 || {
  echo "error: $mkrescue is required (brew install x86_64-elf-grub xorriso mtools)" >&2
  exit 1
}

"$aiueos/scripts/build-multiboot.sh" >/dev/null

rm -rf "$grub_root"
mkdir -p "$grub_root/boot/grub"
# GRUB's multiboot2 ELF loader wants a complete ELF with section headers, so
# it takes the linked 64-bit image directly (GRUB still enters it in 32-bit
# protected mode per the MB2 spec; the trampoline is the ELF entry). QEMU's
# built-in MB1 loader instead needs the 32-bit-wrapped image. Both carry the
# same MB1+MB2 headers and code.
cp "$mb/MULTIBOOT.x86_64.ELF" "$grub_root/boot/aiueos.elf"
cat > "$grub_root/boot/grub/grub.cfg" <<'CFG'
set timeout=0
set default=0
# Load every available video backend and set a linear graphics mode so GRUB
# can honour the kernel's Multiboot2 framebuffer request tag.
insmod all_video
set gfxmode=1024x768x32
set gfxpayload=keep
menuentry "aiueos multiboot2" {
  multiboot2 /boot/aiueos.elf
  boot
}
CFG

# GRUB's mkrescue embeds a boot timestamp; SOURCE_DATE_EPOCH keeps it fixed so
# the ISO is reproducible.
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} "$mkrescue" \
  -o "$iso" "$grub_root" --compress=no >/dev/null 2>&1

[ -f "$iso" ] || { echo "error: grub-mkrescue did not produce $iso" >&2; exit 1; }
echo "$iso"
