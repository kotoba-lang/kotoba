#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
amu=${1:?usage: AIUEOS_AMU_SELFHOST_BIN=/path/to/native/amu build-kotoba-native-boot.sh /path/to/amu-source}
profile=${AIUEOS_NATIVE_PROFILE:-browser-gop-desktop-v1}
if [ "$profile" = browser-gop-desktop-v1 ]; then
  if [ -n "${AIUEOS_NATIVE_BOOT_OUT:-}" ]; then
    export AIUEOS_NATIVE_DESKTOP_OUT="$AIUEOS_NATIVE_BOOT_OUT"
  fi
  exec "$aiueos/scripts/build-kotoba-native-desktop.sh" "$amu"
fi
if [ "$profile" != kernel ]; then
  echo "error: unsupported AIUEOS_NATIVE_PROFILE: $profile" >&2
  exit 1
fi
amu_bin=${AIUEOS_AMU_SELFHOST_BIN:-}
[ -n "$amu_bin" ] && [ -x "$amu_bin" ] || {
  echo "error: set AIUEOS_AMU_SELFHOST_BIN to an executable Amu selfhost compiler" >&2; exit 1;
}
amu_magic=$(LC_ALL=C od -An -tx1 -N4 "$amu_bin" | tr -d '[:space:]')
case "$amu_magic" in
  cffaedfe|feedfacf|7f454c46) ;;
  *) echo "error: AIUEOS_AMU_SELFHOST_BIN must be a native Mach-O or ELF executable, not a launcher: $amu_bin" >&2; exit 1 ;;
esac
amu_binary_sha256=$(shasum -a 256 "$amu_bin" | awk '{print $1}')
export AIUEOS_AMU_SELFHOST_BINARY_SHA256="$amu_binary_sha256"
git -C "$amu" rev-parse --show-toplevel >/dev/null || {
  echo "error: Amu source tree not found: $amu" >&2; exit 1;
}
kotoba_native=${AIUEOS_KOTOBA_NATIVE_ROOT:-"$(dirname -- "$amu")/kotoba-native"}
[ -f "$kotoba_native/src/kotoba/native/elf64.cljc.cljk" ] || {
  echo "error: kotoba-native source not found: $kotoba_native/src" >&2; exit 1;
}
amu_commit=$(git -C "$amu" rev-parse HEAD)
untracked=$(git -C "$amu" ls-files --others --exclude-standard)
[ -z "$untracked" ] || {
  echo "error: Amu source tree has untracked files; provenance cannot include them" >&2
  printf '%s\n' "$untracked" >&2
  exit 1
}
amu_worktree_sha256=$(git -C "$amu" diff --binary HEAD | shasum -a 256 | awk '{print $1}')
kotoba_native_commit=$(git -C "$kotoba_native" rev-parse HEAD)
kotoba_native_untracked=$(git -C "$kotoba_native" ls-files --others --exclude-standard)
[ -z "$kotoba_native_untracked" ] || {
  echo "error: kotoba-native source tree has untracked files; provenance cannot include them" >&2
  printf '%s\n' "$kotoba_native_untracked" >&2
  exit 1
}
kotoba_native_worktree_sha256=$(git -C "$kotoba_native" diff --binary HEAD | shasum -a 256 | awk '{print $1}')
export AMU_KOTOBA_NATIVE_SRC="$kotoba_native/src"
native_out=${AIUEOS_NATIVE_OUT:-"$repo/build/aiueos-native"}
out=${AIUEOS_NATIVE_BOOT_OUT:-"$repo/build/aiueos-native-boot"}
efi="$out/esp/EFI/BOOT/BOOTX64.EFI"
second="$out/BOOTX64.reproduced.EFI"
receipt="$out/receipt.json"
payload=${AIUEOS_NATIVE_BOOT_PAYLOAD:-}
AIUEOS_NATIVE_OUT="$native_out" \
  "$aiueos/scripts/build-kotoba-native-kernel.sh" "$amu" >/dev/null
mkdir -p "$(dirname -- "$efi")"
set -- package-aiueos-boot "$native_out/KERNEL.ELF" --output "$efi" --jvm-free
if [ -n "$payload" ]; then set -- "$@" --payload "$payload"; fi
if [ "${AIUEOS_NATIVE_K16_PREFLIGHT:-0}" = 1 ]; then set -- "$@" --k16-preflight; fi
"$amu_bin" "$@"
set -- package-aiueos-boot "$native_out/KERNEL.ELF" --output "$second" --jvm-free
if [ -n "$payload" ]; then set -- "$@" --payload "$payload"; fi
if [ "${AIUEOS_NATIVE_K16_PREFLIGHT:-0}" = 1 ]; then set -- "$@" --k16-preflight; fi
"$amu_bin" "$@"
cmp "$efi" "$second"; rm -f "$second"
if [ -n "$payload" ]; then
  python3 "$aiueos/scripts/verify-kotoba-native-boot.py" \
    "$efi" "$native_out/KERNEL.ELF" "$amu_commit" "$amu_worktree_sha256" \
    "$kotoba_native_commit" "$kotoba_native_worktree_sha256" "$receipt" "$payload"
else
  python3 "$aiueos/scripts/verify-kotoba-native-boot.py" \
  "$efi" "$native_out/KERNEL.ELF" "$amu_commit" "$amu_worktree_sha256" \
  "$kotoba_native_commit" "$kotoba_native_worktree_sha256" "$receipt"
fi
foreign=$(find "$out" -type f \( -name '*.c' -o -name '*.o' -o -name '*.obj' -o -name '*.a' -o -name '*.so' \) -print -quit)
[ -z "$foreign" ] || { echo "error: foreign/C artifact entered native boot output: $foreign" >&2; exit 1; }
