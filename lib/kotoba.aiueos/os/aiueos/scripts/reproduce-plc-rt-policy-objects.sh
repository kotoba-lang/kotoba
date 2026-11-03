#!/bin/sh
# usage: reproduce-plc-rt-policy-objects.sh /path/to/F2-signed.macho -- rebuild the PLC RT policy objects
# (kotoba/rt-scheduler-dispatch-plan.o and kotoba/plc-user-elf-valid.o) on amu's native object route with the measured Mac
# root (amu fd84f7e9, sha256 7f4e6e43...) and compare them with the committed bytes. The scheduler source exports the RT
# kernel's name itself, so no llvm-objcopy --redefine-sym step is involved (JUN-722).
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: reproduce-plc-rt-policy-objects.sh /path/to/F2-signed.macho}
[ "$(shasum -a 256 "$compiler" | awk '{print $1}')" = 7f4e6e433c385b992765075b6caffa4a80c51e449e090e68db3778e00ecf5db8 ] || {
  echo "error: compiler is not the measured native root (amu fd84f7e9 F2-signed.macho)" >&2; exit 1;
}
out=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-plc-rt-policy.XXXXXX")
trap 'rm -rf "$out"' EXIT HUP INT TERM
for name in rt-scheduler-dispatch-plan plc-user-elf-valid; do
  cp "$aiueos/kotoba/$name.kotoba" "$out/$name.kotoba"
  (cd "$out" && "$compiler" compile "$name.kotoba" --target x86_64-aiueos-kernel-v1 \
    --output "$name.o" --fuel 4194304 3<. </dev/null >/dev/null)
  cmp "$out/$name.o" "$aiueos/kotoba/$name.o"
done
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$out/rt-scheduler-dispatch-plan.o" \
  27272f7c3fc4abd51cde0c87455c88dda37ca2b4e265944a82f1aaf80ac4621c kotoba_aiueos_rt_scheduler_plan >/dev/null
python3 "$aiueos/scripts/verify-kotoba-kernel-object.py" "$out/plc-user-elf-valid.o" \
  de527141de96c352f5219e8a1d267a43a33a94bbd56baa06c3c007bd69dd49f8 kotoba_aiueos_user_elf_valid >/dev/null
echo "AIUEOS_PLC_RT_POLICY_REPRODUCE_OK scheduler=27272f7c validator=de527141"
