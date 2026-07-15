#!/bin/sh
set -eu

usage() {
  echo "usage: $0 <aiueos-checkout> <40-digit-pinned-commit> [destination-subdir]" >&2
  exit 64
}

[ "$#" -ge 2 ] && [ "$#" -le 3 ] || usage
destination=$1
pinned_commit=$2
destination_subdir=${3:-os/aiueos}

[ "${#pinned_commit}" -eq 40 ] || {
  echo "refusing non-immutable destination revision: $pinned_commit" >&2
  exit 65
}
case "$pinned_commit" in
  *[!0-9a-f]*) echo "refusing non-immutable destination revision: $pinned_commit" >&2; exit 65 ;;
esac

actual_commit=$(git -C "$destination" rev-parse HEAD)
[ "$actual_commit" = "$pinned_commit" ] || {
  echo "destination HEAD $actual_commit does not match pin $pinned_commit" >&2
  exit 66
}

source_tree=os/aiueos
destination_tree=$destination/$destination_subdir
[ -d "$source_tree" ] || { echo "missing source tree: $source_tree" >&2; exit 67; }
[ -d "$destination_tree" ] || { echo "missing destination tree: $destination_tree" >&2; exit 68; }

source_manifest=$(mktemp)
destination_manifest=$(mktemp)
trap 'rm -f "$source_manifest" "$destination_manifest"' EXIT HUP INT TERM

git ls-files -s "$source_tree" | sed "s#\t$source_tree/#\t#" >"$source_manifest"
git -C "$destination" ls-files -s "$destination_subdir" |
  sed "s#\t$destination_subdir/#\t#" >"$destination_manifest"

if ! cmp -s "$source_manifest" "$destination_manifest"; then
  echo "source and pinned destination differ (path, mode, or blob id)" >&2
  diff -u "$source_manifest" "$destination_manifest" || true
  exit 69
fi

echo "verified aiueos extraction at $pinned_commit"
echo "review destination CI and west pin, then remove os/aiueos and its ci job"
