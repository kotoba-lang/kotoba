#!/bin/sh
# Which rebuilt object breaks the boot?
#
# ADR-0035 defined a per-object differential, deferred it, and recorded that
# the deferral is precisely what let a non-booting tree become a merge
# candidate. This is that differential, done the way the ADR asked -- gated on
# the boot rather than on the digest.
#
#   ./os/aiueos/scripts/bisect-object-migration.sh <compiler-checkout>
#
# It regenerates every shipped kernel object with the compiler you point it at,
# then binary-searches for the smallest set whose migration stops the machine
# booting. Each probe restores every other object to what the tree ships, so a
# probe measures exactly one variable.
#
# Two things it will not do:
#
#   It will not call a run good because it produced some markers. GOOD is the
#   marker count of a control run with nothing migrated, measured at the start
#   -- not a constant, because a cold boot emits four fewer markers than a warm
#   one and hardcoding either would make an ordering artifact look like a
#   result.
#
#   It will not report a culprit it did not confirm. After the search narrows to
#   one object, that object is migrated alone and the boot must break again.
set -eu
compiler=${1:?usage: bisect-object-migration.sh /path/to/compiler-checkout}
here=$(cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(cd -- "$here/.." && pwd)
root=$(cd -- "$aiueos/../.." && pwd)
work=$(mktemp -d); trap 'rm -rf "$work"' EXIT
cd "$root"

echo "== regenerating objects with $(git -C "$compiler" rev-parse --short HEAD)"
: > "$work/objects"
for o in os/aiueos/kotoba/*.o; do
  base=$(basename "$o" .o); src="os/aiueos/kotoba/$base.kotoba"
  [ -f "$src" ] || continue
  if "$compiler/bin/amu" compile "$root/$src" --target x86_64-aiueos-kernel-v1 \
       --output "$work/$base.o" >/dev/null 2>&1; then
    old=$(shasum -a 256 "$o" | awk '{print $1}')
    new=$(shasum -a 256 "$work/$base.o" | awk '{print $1}')
    [ "$old" = "$new" ] || echo "$base $old $new" >> "$work/objects"
  else
    echo "DOES-NOT-COMPILE $base" >&2
  fi
done
n=$(wc -l < "$work/objects" | tr -d ' ')
echo "== $n objects change bytes under this compiler"
[ "$n" -gt 0 ] || { echo "AIUEOS_MIGRATION_BISECT_NOTHING_TO_DO"; exit 0; }

probe() {  # probe <base>... ; echoes the marker count
  git checkout -q -- os/aiueos/kotoba os/aiueos/scripts/build-uefi.sh
  for b in "$@"; do
    old=$(awk -v b="$b" '$1==b {print $2}' "$work/objects")
    new=$(awk -v b="$b" '$1==b {print $3}' "$work/objects")
    cp "$work/$b.o" "os/aiueos/kotoba/$b.o"
    sed -i '' "s/$old/$new/g" os/aiueos/scripts/build-uefi.sh
  done
  ./os/aiueos/scripts/build-uefi.sh >"$work/build.log" 2>&1 || { echo BUILD_FAILED; return; }
  ./os/aiueos/scripts/smoke-qemu-uefi.sh >"$work/smoke.log" 2>&1 || true
  grep -c '^AIUEOS_' build/aiueos/kernel-serial.log 2>/dev/null || echo 0
}

good=$(probe)
echo "== control (nothing migrated): $good markers"
case "$good" in ''|*[!0-9]*|0) echo "AIUEOS_MIGRATION_BISECT_UNDECIDED control did not boot" >&2; exit 3;; esac

set -- $(awk '{print $1}' "$work/objects")
if [ "$(probe "$@")" = "$good" ]; then
  echo "AIUEOS_MIGRATION_BISECT_OK all $n migrated objects boot identically"
  git checkout -q -- os/aiueos/kotoba os/aiueos/scripts/build-uefi.sh
  exit 0
fi
while [ $# -gt 1 ]; do
  half=$(( $# / 2 ))
  first=$(echo "$@" | tr ' ' '\n' | head -"$half" | tr '\n' ' ')
  if [ "$(probe $first)" = "$good" ]; then
    set -- $(echo "$@" | tr ' ' '\n' | tail -n +$((half+1)) | tr '\n' ' ')
  else
    set -- $first
  fi
  echo "   narrowed to $#"
done
alone=$(probe "$1")
git checkout -q -- os/aiueos/kotoba os/aiueos/scripts/build-uefi.sh
if [ "$alone" = "$good" ]; then
  echo "AIUEOS_MIGRATION_BISECT_UNCONFIRMED $1 booted when migrated alone" >&2
  exit 1
fi
echo "AIUEOS_MIGRATION_BISECT_CULPRIT $1 markers=$alone good=$good"
