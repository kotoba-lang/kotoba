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

# JUN-722 / KOTOBA-175: amu's public CLI (bin/kotoba-compiler -> amu) takes no --target; cross targets are compiled by
# the native root, which reads the source from and writes the output into the directory open on FD 3. The PLC program
# is compiled for amu's x86_64-aiueos-user-plc-v1 target (amu ADR 0402): raw `cap-call` checked at compile time
# against the --capabilities set, which also becomes the ELF's capability bitmap, in the layout plc-user-elf-valid
# admits. The set is $policy: the script passes the list and requires the policy file to be exactly that list's
# canonical rendering, so a changed policy refuses here rather than being reinterpreted. Nothing falls back to the
# retired nbb/JVM route.
root=${AMU_NATIVE_ROOT:-"$compiler/seed/bootstrap/aarch64-macos/amu-full-root.macho"}
[ -x "$root" ] || { echo "error: amu native root not found: $root (set AMU_NATIVE_ROOT)" >&2; exit 1; }
capabilities=16,17,18,19
printf '{:allow #{%s}}\n' "$(printf '%s' "$capabilities" | sed 's/[0-9][0-9]*/[:cap\/call &]/g; s/,/ /g')" |
  cmp -s - "$policy" || {
  echo "error: $policy is not the canonical policy for capabilities $capabilities" >&2; exit 1; }
compile() {
  rm -f "$out/$2"
  (cd "$out" && "$root" compile "$1" --target x86_64-aiueos-user-plc-v1 \
    --capabilities "$capabilities" --output "$2" 3<. </dev/null >/dev/null)
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
