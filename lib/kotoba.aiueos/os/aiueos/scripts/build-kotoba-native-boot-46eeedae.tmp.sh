#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: build-kotoba-native-boot.sh /path/to/compiler}
expected=49a9efdf97a5f2a18ffb099faa3389532a58628d
actual=$(git -C "$compiler" rev-parse HEAD)
[ "$actual" = "$expected" ] || {
  echo "error: compiler HEAD is $actual; expected $expected" >&2; exit 1;
}
native_out=${AIUEOS_NATIVE_OUT:-"$repo/build/aiueos-native"}
out=${AIUEOS_NATIVE_BOOT_OUT:-"$repo/build/aiueos-native-boot"}
efi="$out/esp/EFI/BOOT/BOOTX64.EFI"
second="$out/BOOTX64.reproduced.EFI"
receipt="$out/receipt.json"
mkdir -p "$native_out"
AIUEOS_NATIVE_OUT="$native_out" \
  "$aiueos/scripts/build-kotoba-native-kernel-46eeedae.tmp.sh" "$compiler" >"$native_out/kernel-build.log"
# The kernel build's own verifier prints one OK line; it used to go to /dev/null,
# so a boot build that skipped verification and one that passed it printed the
# same three lines. Re-say the line here or refuse.
grep -a 'AIUEOS_KOTOBA_NATIVE_KERNEL_OK' "$native_out/kernel-build.log" || {
  echo "error: kernel build log has no AIUEOS_KOTOBA_NATIVE_KERNEL_OK line ($native_out/kernel-build.log)" >&2; exit 1; }
mkdir -p "$(dirname -- "$efi")"
set -- package-aiueos-boot "$native_out/KERNEL.ELF" --output "$efi"
if [ "${AIUEOS_NATIVE_K16_PREFLIGHT:-0}" = 1 ]; then
  set -- "$@" --k16-preflight
  # A note for the panel beside the build digest. Derived from the tree, not
  # the clock: the same commit packages to the same bytes, which is what the
  # cmp below checks. -dirty is the honest case while iterating.
  set -- "$@" --k16-note "${AIUEOS_K16_NOTE:-$(git -C "$repo" describe --always --dirty 2>/dev/null || echo local)}"
fi
"$compiler/bin/kotoba-compiler" "$@"
set -- package-aiueos-boot "$native_out/KERNEL.ELF" --output "$second"
if [ "${AIUEOS_NATIVE_K16_PREFLIGHT:-0}" = 1 ]; then
  set -- "$@" --k16-preflight
  # A note for the panel beside the build digest. Derived from the tree, not
  # the clock: the same commit packages to the same bytes, which is what the
  # cmp below checks. -dirty is the honest case while iterating.
  set -- "$@" --k16-note "${AIUEOS_K16_NOTE:-$(git -C "$repo" describe --always --dirty 2>/dev/null || echo local)}"
fi
"$compiler/bin/kotoba-compiler" "$@"
cmp "$efi" "$second"; rm -f "$second"
python3 "$aiueos/scripts/verify-kotoba-native-boot.py" \
  "$efi" "$native_out/KERNEL.ELF" "$expected" "$receipt"
foreign=$(find "$out" -type f \( -name '*.c' -o -name '*.o' -o -name '*.obj' -o -name '*.a' -o -name '*.so' \) -print -quit)
[ -z "$foreign" ] || { echo "error: foreign/C artifact entered native boot output: $foreign" >&2; exit 1; }
