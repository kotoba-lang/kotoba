#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: build-plc-native-program.sh /path/to/amu PROGRAM.st}
source=${2:?usage: build-plc-native-program.sh /path/to/amu PROGRAM.st}
name=$(basename "$source" .st)
out=${AIUEOS_PLC_OUT:-"$repo/build/aiueos-plc/$name"}
mkdir -p "$out"
out=$(CDPATH= cd -- "$out" && pwd)
generated="$out/program.kotoba"
generated_again="$out/program.reproduced.kotoba"
elf="$out/program.elf"
elf_again="$out/program.reproduced.elf"
receipt="$out/program-receipt.json"
policy="$aiueos/kotoba/plc-runtime-policy.edn"

python3 "$aiueos/scripts/compile-plc-st.py" "$source" "$generated"
python3 "$aiueos/scripts/compile-plc-st.py" "$source" "$generated_again"
cmp "$generated" "$generated_again"

# JUN-722: amu's public CLI (bin/kotoba-compiler -> amu) no longer takes --target; cross targets are compiled by the
# native root, which reads the source from and writes the output into the directory open on FD 3. It takes no
# --policy flag. Measured 2026-10-31 on amu main b19e93b (amu-full-root.macho, sha256 ddeb35d9...): the generated
# program's raw `cap-call` is refused with E2101, and seed/74's user target refuses any capability (E7101), so no PLC
# program builds on the current compiler. The refusal is passed through unchanged; nothing falls back to the retired
# nbb/JVM route. Capability grants must come back with the compiler support, checked against $policy.
root=${AMU_NATIVE_ROOT:-"$compiler/seed/bootstrap/aarch64-macos/amu-full-root.macho"}
[ -x "$root" ] || { echo "error: amu native root not found: $root (set AMU_NATIVE_ROOT)" >&2; exit 1; }
[ -f "$policy" ]
compile() {
  rm -f "$out/$2"
  (cd "$out" && "$root" compile "$1" --target x86_64-aiueos-user-v1 \
    --output "$2" 3<. </dev/null >/dev/null)
  [ -f "$out/$2" ]
}
compile program.kotoba program.elf
compile program.reproduced.kotoba program.reproduced.elf
cmp "$elf" "$elf_again"

commit=$(git -C "$compiler" rev-parse HEAD)

set -- "$source" "$generated" "$elf" "$commit" "$receipt"
if [ -n "${AIUEOS_PLC_RT_KERNEL_RECEIPT:-}" ] || \
   [ -n "${AIUEOS_PLC_IO_MAP:-}" ] || \
   [ -n "${AIUEOS_PLC_ADMISSION:-}" ] || \
   [ -n "${AIUEOS_PLC_SIGNATURE:-}" ] || \
   [ -n "${AIUEOS_PLC_PUBLIC_KEY:-}" ]; then
  set -- "$@" --rt-kernel-receipt "${AIUEOS_PLC_RT_KERNEL_RECEIPT:?}" \
    --io-map "${AIUEOS_PLC_IO_MAP:?}" \
    --admission "${AIUEOS_PLC_ADMISSION:?}" \
    --signature "${AIUEOS_PLC_SIGNATURE:?}" \
    --public-key "${AIUEOS_PLC_PUBLIC_KEY:?}"
fi
python3 "$aiueos/scripts/make-plc-native-receipt.py" "$@"

find "$out" -type f \( -name '*.c' -o -name '*.o' -o -name '*.a' \
  -o -name '*.so' -o -name '*.class' -o -name '*.jar' \) -print -quit |
while IFS= read -r foreign; do
  [ -z "$foreign" ] || {
    echo "error: foreign/JVM artifact entered PLC output: $foreign" >&2
    exit 1
  }
done
printf 'AIUEOS_PLC_NATIVE_BUILD_OK elf=%s receipt=%s\n' "$elf" "$receipt"
