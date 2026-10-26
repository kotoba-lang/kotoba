#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
compiler=${1:?usage: test-rt-scheduler-object.sh /path/to/amu}
source="$repo/os/aiueos/kotoba/rt-scheduler-dispatch-plan.kotoba"
tmp=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-rt-scheduler.XXXXXX")
trap 'rm -rf "$tmp"' EXIT HUP INT TERM

compile() {
  "$compiler/bin/kotoba-compiler" compile "$source" \
    --target x86_64-aiueos-kernel-v1 --artifact object --fuel 32768 \
    --output "$1"
}

compile "$tmp/one.o"
compile "$tmp/two.o"
cmp "$tmp/one.o" "$tmp/two.o"

symbols=$(nm -g "$tmp/one.o")
printf '%s\n' "$symbols" | grep -Eq \
  ' T kotoba_aiueos_scheduler_dispatch_plan$'
[ -z "$(nm -u "$tmp/one.o")" ] || {
  echo "error: RT scheduler object has undefined imports" >&2
  exit 1
}

digest=$(shasum -a 256 "$tmp/one.o" | awk '{print $1}')
commit=$(git -C "$compiler" rev-parse HEAD)
printf 'AIUEOS_RT_SCHEDULER_OBJECT_OK sha256=%s compiler=%s imports=0\n' \
  "$digest" "$commit"
