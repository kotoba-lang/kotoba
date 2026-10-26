#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
amu=${1:?usage: AIUEOS_AMU_SELFHOST_BIN=/path/to/native/amu build-kotoba-rt-kernel.sh /path/to/amu-source}
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
amu_commit=$(git -C "$amu" rev-parse HEAD)
untracked=$(git -C "$amu" ls-files --others --exclude-standard)
[ -z "$untracked" ] || {
  echo "error: Amu source tree has untracked files; provenance cannot include them" >&2
  printf '%s\n' "$untracked" >&2
  exit 1
}
amu_worktree_sha256=$(git -C "$amu" diff --binary HEAD | shasum -a 256 | awk '{print $1}')
out=${AIUEOS_KOTOBA_RT_OUT:-"$repo/build/aiueos-kotoba-rt"}
source="$aiueos/native/rt-kernel.kotoba"
root_source="$aiueos/native/rt-system.kotoba"
kernel="$out/KERNEL.ELF"
second="$out/KERNEL.reproduced.ELF"
receipt="$out/receipt.json"
mkdir -p "$out"
compile_system() {
  "$amu_bin" compile "$root_source" \
    --source-path "$aiueos/native" \
    --source-path "$aiueos/kotoba" --unpinned --jvm-free \
    --target x86_64-aiueos-kernel-v1 --artifact image --fuel 1048576 \
    --output "$1"
}
compile_system "$kernel"
compile_system "$second"
cmp "$kernel" "$second"
rm -f "$second"
python3 "$aiueos/scripts/verify-kotoba-rt-kernel.py" \
  "$kernel" "$source" "$amu_commit" "$amu_worktree_sha256" "$receipt" \
  "$root_source" "$aiueos/kotoba/sha256.kotoba" \
  "$aiueos/kotoba/ecdsa-p256.kotoba" \
  "$aiueos/kotoba/plc-user-elf-valid.kotoba"
foreign=$(find "$out" -type f \( -name '*.c' -o -name '*.o' -o -name '*.obj' \
  -o -name '*.a' -o -name '*.so' \) -print -quit)
[ -z "$foreign" ] || {
  echo "error: C/foreign artifact entered Kotoba RT output: $foreign" >&2; exit 1;
}
