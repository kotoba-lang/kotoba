#!/bin/sh
# Fetch kotoba's pinned Amu into _native/amu (or DEST), the checkout kotoba's CI
# uses and the default of lib/kotoba.aiueos/os/aiueos/scripts/run-native-generator.sh.
#
#   scripts/fetch-native-amu.sh [DEST]
#
# The revision and file digests are scripts/native-ci-inputs.json's "amu" pin,
# the one kotoba's CI checks out. The fetch is a depth-1, blob-filtered fetch of
# that exact commit with a sparse checkout of the pinned files only (a few MB),
# then every pinned file is checked against its sha256. An existing DEST is
# reused only when it is a checkout of exactly that commit; anything else
# refuses rather than being overwritten. AMU_GIT_URL overrides the remote
# (default https://github.com/kotoba-lang/amu.git), for a mirror or a local clone.
set -eu

die() { echo "error: fetch-native-amu: $*" >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then sha256=sha256sum; else sha256="shasum -a 256"; fi

root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
pins="$root/scripts/native-ci-inputs.json"
dest=${1:-"$root/_native/amu"}
url=${AMU_GIT_URL:-https://github.com/kotoba-lang/amu.git}
command -v git >/dev/null 2>&1 || die "git is required"

revision=$(awk '/^  "amu": \{/ { a = 1 } a && /"revision":/ { sub(/.*"revision": "/, ""); sub(/".*/, ""); print; exit }' "$pins")
case "$revision" in *[!0-9a-f]*|'') die "no Amu revision in $pins" ;; esac
[ "${#revision}" = 40 ] || die "no Amu revision in $pins"
# path sha256, one per line, for every file under "amu" "files"
files=$(awk '/^  "amu": \{/ { a = 1 } /^  "contract": \{/ { a = 0 }
  a && /^      "[^"]+": \{$/ { p = $0; sub(/^ *"/, "", p); sub(/": \{$/, "", p) }
  a && p != "" && /"sha256":/ { s = $0; sub(/.*"sha256": "/, "", s); sub(/".*/, "", s); print p, s; p = "" }' "$pins")
[ -n "$files" ] || die "no pinned Amu files in $pins"

if [ -e "$dest" ]; then
  head=$(git -C "$dest" rev-parse --verify -q HEAD 2>/dev/null) || die "$dest exists and is not a git checkout"
  [ "$head" = "$revision" ] || die "$dest is at $head, not the pinned $revision; move it aside or pass another DEST"
else
  mkdir -p "$(dirname -- "$dest")"
  git init -q "$dest"
  git -C "$dest" remote add origin "$url"
  git -C "$dest" config extensions.partialClone origin 2>/dev/null || :
  git -C "$dest" sparse-checkout set --no-cone $(echo "$files" | sed 's/ .*//; s|^|/|')
  git -C "$dest" fetch -q --depth 1 --filter=blob:none origin "$revision" \
    || die "could not fetch Amu $revision from $url"
  git -C "$dest" -c advice.detachedHead=false checkout -q --detach "$revision"
fi

echo "$files" | while read -r path sha; do
  [ -f "$dest/$path" ] && [ ! -L "$dest/$path" ] || die "pinned file missing or a symlink: $dest/$path"
  actual=$($sha256 "$dest/$path" | cut -c1-64)
  [ "$actual" = "$sha" ] || die "pin mismatch for $dest/$path: $actual, pinned $sha"
done
echo "AMU_PINNED_OK revision=$revision files=$(echo "$files" | wc -l | tr -d ' ') path=$dest"
