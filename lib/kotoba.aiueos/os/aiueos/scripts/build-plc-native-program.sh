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

compile() {
  "$compiler/bin/kotoba-compiler" compile "$1" \
    --target x86_64-aiueos-user-v1 --policy "$policy" --output "$2"
}
compile "$generated" "$elf"
compile "$generated_again" "$elf_again"
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
