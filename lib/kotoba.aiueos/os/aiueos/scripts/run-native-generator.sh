#!/bin/sh
# JUN-555: run one Kotoba build generator natively with the pinned Amu Mac root.
#
#   run-native-generator.sh GENERATOR.kotoba DEST [--input NAME=PATH]... -- [ARG]...
#
# The generator source is appended to the exact Amu seed 00/01/02 helpers,
# compiled by the pinned Amu compiler, packaged by the pinned packager
# (fs2-cli-stdio-general) and run with an empty environment and its FD 3 scope
# set to a fresh private directory. That directory holds only the named inputs,
# so the program can read those and write nothing outside it. It is called as
# `program out ARG...`; on exit 0 with an empty stderr its `out` file replaces
# DEST. Anything else refuses: there is no Python or hosted fallback.
#
# AIUEOS_AMU_SOURCE names the Amu checkout (default: the kotoba-lang/amu sibling of
# this kotoba checkout). Its compiler, packager and seed bytes must match the pins.
set -eu

die() { echo "error: native generator: $*" >&2; exit 1; }

[ "$#" -ge 3 ] || die "usage: run-native-generator.sh GENERATOR DEST [--input NAME=PATH]... -- [ARG]..."
generator=$1 dest=$2
shift 2

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
amu=${AIUEOS_AMU_SOURCE:-"$here/../../../../../../amu"}
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] \
  || die "needs the Apple Silicon Amu root; this host has no native route (no Python fallback)"
[ -d "$amu" ] || die "Amu source not found at $amu (set AIUEOS_AMU_SOURCE)"
amu=$(CDPATH= cd -- "$amu" && pwd)
[ -f "$generator" ] && [ ! -L "$generator" ] || die "generator source missing or a symlink: $generator"

# Amu 3c9eb7f7 (seed/bootstrap/aarch64-macos/root.json and the seeds it was built with).
root="$amu/seed/bootstrap/aarch64-macos"
compiler="$root/amu-full-root.macho"
packager="$root/kotoba-packager-root.macho"
pin() {
  [ -f "$1" ] && [ ! -L "$1" ] || die "pinned input missing or a symlink: $1"
  actual=$(shasum -a 256 "$1" | cut -c1-64)
  [ "$actual" = "$2" ] || die "pin mismatch for $1: $actual"
}
pin "$compiler" 6235e1916598e303cd2a991f3172af7daa948e1a1553e63ea2d6208ccb12c0e3
pin "$packager" e95284408f091c8979ef74ece57116a4df2250e61e42074da5dc95ca30264142
pin "$amu/seed/00-ns-static.kotoba" 4ec4d56aef26b60bf4fdb9d070691c9355055e4ff79db960790f1afc4b7fd8b1
pin "$amu/seed/01-mem.kotoba" 8a3a191d6e735f16363228854714869ea8d71d15373cedb40c359a1f9cd36159
pin "$amu/seed/02-io.kotoba" 6427f01e724a57142590a6b1942cfbca24ea4e4bbdd82e6ecbdecd50d8df1238

work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-generator.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir "$work/build" "$work/scope"

while [ "$#" -gt 0 ] && [ "$1" != -- ]; do
  [ "$1" = --input ] && [ "$#" -ge 2 ] || die "expected --input NAME=PATH or --"
  name=${2%%=*} path=${2#*=}
  case "$name" in ''|out|*/*|.*) die "invalid input name: $name" ;; esac
  [ "$name" != "$2" ] && [ -f "$path" ] || die "input missing: $2"
  [ ! -e "$work/scope/$name" ] || die "duplicate input name: $name"
  cp "$path" "$work/scope/$name"
  shift 2
done
[ "$#" -gt 0 ] || die "missing -- before the generator arguments"
shift

for part in "$amu/seed/00-ns-static.kotoba" "$amu/seed/01-mem.kotoba" "$amu/seed/02-io.kotoba" "$generator"; do
  cat "$part"
  echo
done > "$work/build/generator.kotoba"

native() {
  (cd "$work/build" && env -i PATH=/nonexistent "$@" 3<.) > "$work/native.stdout" 2> "$work/native.stderr" \
    && [ ! -s "$work/native.stderr" ] \
    || die "Amu step failed: $(basename "$1") $2: $(tail -c 500 "$work/native.stderr")"
}
native "$compiler" compile generator.kotoba --target aarch64-macos --output generator.kseed
native "$compiler" extract-native generator.kseed --symbol main --output generator.raw
offset=$(sed -n 's/^{:ok true, :output "generator.raw", :offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}$/\1 \2/p' \
  "$work/native.stdout")
length=${offset#* } offset=${offset% *}
[ -n "$offset" ] && [ "$length" = "$(wc -c < "$work/build/generator.raw" | tr -d ' ')" ] \
  || die "native main extraction is missing or inconsistent"
native "$packager" generator-unsigned.macho generator.raw fs2-cli-stdio-general "$offset"
cp "$work/build/generator-unsigned.macho" "$work/build/generator.macho"
chmod 755 "$work/build/generator.macho"
/usr/bin/codesign --force --sign - "$work/build/generator.macho" 2>/dev/null \
  || die "ad-hoc signing the generator failed"

status=0
(cd "$work/scope" && env -i PATH=/nonexistent "$work/build/generator.macho" out "$@" 3<.) \
  > "$work/run.stdout" 2> "$work/run.stderr" || status=$?
if [ "$status" != 0 ] || [ -s "$work/run.stderr" ] || [ ! -f "$work/scope/out" ] || [ -L "$work/scope/out" ]; then
  cat "$work/run.stderr" >&2
  die "$(basename "$generator") refused (exit $status); $dest not written"
fi
cat "$work/run.stdout"
mv -f "$work/scope/out" "$dest"
