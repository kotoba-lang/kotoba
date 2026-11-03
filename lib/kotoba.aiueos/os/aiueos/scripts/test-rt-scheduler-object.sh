#!/bin/sh
# usage: test-rt-scheduler-object.sh /path/to/amu-native-root -- compile kotoba/rt-scheduler-dispatch-plan.kotoba twice on
# amu's native object route (the Mac root image, e.g. F2-signed.macho) and check that the object is reproducible, exports
# the RT kernel's name kotoba_aiueos_rt_scheduler_plan directly and imports nothing (JUN-722).
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
compiler=${1:?usage: test-rt-scheduler-object.sh /path/to/amu-native-root}
source="$repo/os/aiueos/kotoba/rt-scheduler-dispatch-plan.kotoba"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-rt-scheduler.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM
cp "$source" "$tmp/rt.kotoba"

compile() {
  (cd "$tmp" && "$compiler" compile rt.kotoba --target x86_64-aiueos-kernel-v1 \
    --output "$1" --fuel 4194304 3<. </dev/null >/dev/null)
}

compile one.o
compile two.o
cmp "$tmp/one.o" "$tmp/two.o"
python3 "$repo/os/aiueos/scripts/verify-kotoba-kernel-object.py" "$tmp/one.o" \
  "$(shasum -a 256 "$tmp/one.o" | awk '{print $1}')" kotoba_aiueos_rt_scheduler_plan >/dev/null

digest=$(shasum -a 256 "$tmp/one.o" | awk '{print $1}')
root=$(shasum -a 256 "$compiler" | awk '{print $1}')
printf 'AIUEOS_RT_SCHEDULER_OBJECT_OK sha256=%s compiler-sha256=%s imports=0\n' \
  "$digest" "$root"
