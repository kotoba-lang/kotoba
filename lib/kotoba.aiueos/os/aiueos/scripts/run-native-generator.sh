#!/bin/sh
# JUN-555: run one Kotoba build generator natively with kotoba's pinned Amu.
#
#   run-native-generator.sh GENERATOR.kotoba DEST [--seed NAME] [--input NAME=PATH]... -- [ARG]...
#
# The generator source is appended to the exact Amu seed 00/01/02 helpers (and any
# further pinned seed module named by --seed, such as 03-source-sha256), compiled
# by the pinned Amu compiler for this host and run with an empty environment and
# a filesystem scope set to a fresh private directory. That directory holds only
# the named inputs, so the program can read those and write nothing outside it.
# It is called as `program out ARG...`; on exit 0 with an empty stderr its `out`
# file replaces DEST. Anything else refuses: there is no Python or hosted fallback.
# An ARG `@size:NAME` is replaced by the byte size of the staged input NAME: on the
# Mac root the FS2 whole-file read and stat trap, so generators read their inputs
# in bounded slices of a size the runner measured on its own private copy.
#
# One pin. The Amu revision and the sha256 of every Amu file used here come from
# kotoba's scripts/native-ci-inputs.json, the pin kotoba's CI checks out
# (.github/workflows/ci.yml). This script holds no digest of its own.
#
# Hosts (each refuses unless its files match that pin):
#   Darwin arm64   seed/bootstrap/aarch64-macos/amu-full-root.macho compiles,
#                  kotoba-packager-root.macho packages (fs2-cli-stdio-general),
#                  ad-hoc signed; the FS scope is FD 3.
#   Linux aarch64  seed/bootstrap/aarch64-linux-static-root.elf, --target aarch64-linux --format static
#   Linux x86_64   bin/amu-linux-x86_64, --target x86_64-linux --format static
#                  On Linux the FS scope is KEXE_CAP_RESOURCES_35, the grants are
#                  KEXE_ALLOW=35,37,38 and CPU and wall time are bounded.
#
# AIUEOS_AMU_SOURCE names the Amu checkout. Default: _native/amu in this kotoba
# checkout, the path kotoba's CI uses; scripts/fetch-native-amu.sh fetches it at
# the pin. AIUEOS_NATIVE_SECCOMP=if-available is passed on as KEXE_SECCOMP for
# Linux hosts whose kernel has no seccomp(2), such as qemu-user; any other value
# refuses, and without it the Linux runtime requires seccomp.
set -eu

die() { echo "error: native generator: $*" >&2; exit 1; }
if command -v sha256sum >/dev/null 2>&1; then sha256=sha256sum; else sha256="shasum -a 256"; fi

[ "$#" -ge 3 ] || die "usage: run-native-generator.sh GENERATOR DEST [--seed NAME] [--input NAME=PATH]... -- [ARG]..."
generator=$1 dest=$2
shift 2

here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
kotoba=$(CDPATH= cd -- "$here/../../../../.." && pwd)
pins="$kotoba/scripts/native-ci-inputs.json"
[ -f "$pins" ] && [ ! -L "$pins" ] || die "kotoba's Amu pin $pins is missing"
revision=$(awk '/^  "amu": \{/ { a = 1 } a && /"revision":/ { sub(/.*"revision": "/, ""); sub(/".*/, ""); print; exit }' "$pins")
case "$revision" in *[!0-9a-f]*|'') die "no Amu revision in $pins" ;; esac
[ "${#revision}" = 40 ] || die "no Amu revision in $pins"
fetch_hint="fetch it with: sh $kotoba/scripts/fetch-native-amu.sh (Amu $revision)"

amu=${AIUEOS_AMU_SOURCE:-"$kotoba/_native/amu"}
[ -d "$amu" ] || die "Amu source not found at $amu; $fetch_hint, or set AIUEOS_AMU_SOURCE"
amu=$(CDPATH= cd -- "$amu" && pwd)
case "$amu" in *[[:space:]]*) die "Amu source path must not contain whitespace: $amu" ;; esac
[ -f "$generator" ] && [ ! -L "$generator" ] || die "generator source missing or a symlink: $generator"

seccomp=
case "${AIUEOS_NATIVE_SECCOMP-}" in
  '') ;;
  if-available) seccomp=KEXE_SECCOMP=if-available ;;
  *) die "AIUEOS_NATIVE_SECCOMP must be unset or if-available" ;;
esac

# pin RELATIVE: the Amu file must be a regular file whose sha256 is the pin's.
pin() {
  expected=$(awk -v key="\"$1\": {" 'index($0, key) { f = 1; next }
    f && /"sha256":/ { sub(/.*"sha256": "/, ""); sub(/".*/, ""); print; exit }
    f && /}/ { exit }' "$pins")
  case "$expected" in *[!0-9a-f]*|'') die "kotoba's Amu pin names no $1" ;; esac
  [ "${#expected}" = 64 ] || die "kotoba's Amu pin names no $1"
  [ -f "$amu/$1" ] && [ ! -L "$amu/$1" ] || die "pinned Amu file missing or a symlink: $amu/$1; $fetch_hint"
  actual=$($sha256 "$amu/$1" | cut -c1-64)
  [ "$actual" = "$expected" ] \
    || die "pin mismatch for $amu/$1: $actual is not Amu $revision's $expected; $fetch_hint"
}

host="$(uname -s) $(uname -m)"
case "$host" in
  'Darwin arm64')
    route=macos compiler=seed/bootstrap/aarch64-macos/amu-full-root.macho
    packager=seed/bootstrap/aarch64-macos/kotoba-packager-root.macho
    pin "$packager" ;;
  'Linux aarch64'|'Linux arm64')
    route=linux target=aarch64-linux compiler=seed/bootstrap/aarch64-linux-static-root.elf ;;
  'Linux x86_64')
    route=linux target=x86_64-linux compiler=bin/amu-linux-x86_64 ;;
  *) die "no pinned Amu root for $host (Apple Silicon, Linux aarch64 or x86_64); no Python fallback" ;;
esac
pin "$compiler"
pin seed/00-ns-static.kotoba
pin seed/01-mem.kotoba
pin seed/02-io.kotoba

work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-native-generator.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
mkdir "$work/build" "$work/scope"
extra_seeds=

while [ "$#" -gt 0 ] && [ "$1" != -- ]; do
  if [ "$1" = --seed ] && [ "$#" -ge 2 ]; then
    case "$2" in *[!a-z0-9-]*) die "invalid seed module name: $2" ;; [0-9][0-9]-?*) ;; *) die "invalid seed module name: $2" ;; esac
    pin "seed/$2.kotoba"
    extra_seeds="$extra_seeds $amu/seed/$2.kotoba"
    shift 2
    continue
  fi
  [ "$1" = --input ] && [ "$#" -ge 2 ] || die "expected --seed NAME, --input NAME=PATH or --"
  name=${2%%=*} path=${2#*=}
  case "$name" in ''|out|*/*|.*) die "invalid input name: $name" ;; esac
  [ "$name" != "$2" ] && [ -f "$path" ] || die "input missing: $2"
  [ ! -e "$work/scope/$name" ] || die "duplicate input name: $name"
  cp "$path" "$work/scope/$name"
  shift 2
done
[ "$#" -gt 0 ] || die "missing -- before the generator arguments"
shift

for part in "$amu/seed/00-ns-static.kotoba" "$amu/seed/01-mem.kotoba" "$amu/seed/02-io.kotoba" $extra_seeds "$generator"; do
  cat "$part"
  echo
done > "$work/build/generator.kotoba"

# Linux static runtime: FS wire 35 scoped to one directory, plus the CLI and
# stdio wires; CPU and wall time bounded; no other environment.
linux_env() {
  echo "PATH=/nonexistent KEXE_ALLOW=35,37,38 KEXE_STACK_BYTES=8388608 KEXE_CPU_SECONDS=600"
  echo "KEXE_WALL_SECONDS=900 KEXE_CAP_RESOURCES_35=$1 $seccomp"
}
native() {
  if [ "$route" = macos ]; then
    (cd "$work/build" && env -i PATH=/nonexistent "$@" 3<.)
  else
    # shellcheck disable=SC2046 # linux_env is fixed words without whitespace in values
    (cd "$work/build" && env -i $(linux_env "$work/build") "$@")
  fi > "$work/native.stdout" 2> "$work/native.stderr" \
    && [ ! -s "$work/native.stderr" ] \
    || die "Amu step failed: $(basename "$1") $2: $(tail -c 500 "$work/native.stderr")"
}
if [ "$route" = macos ]; then
  native "$amu/$compiler" compile generator.kotoba --target aarch64-macos --output generator.kseed
  native "$amu/$compiler" extract-native generator.kseed --symbol main --output generator.raw
  offset=$(sed -n 's/^{:ok true, :output "generator.raw", :offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}$/\1 \2/p' \
    "$work/native.stdout")
  length=${offset#* } offset=${offset% *}
  [ -n "$offset" ] && [ "$length" = "$(wc -c < "$work/build/generator.raw" | tr -d ' ')" ] \
    || die "native main extraction is missing or inconsistent"
  native "$amu/$packager" generator-unsigned.macho generator.raw fs2-cli-stdio-general "$offset"
  cp "$work/build/generator-unsigned.macho" "$work/build/generator.exe"
  chmod 755 "$work/build/generator.exe"
  /usr/bin/codesign --force --sign - "$work/build/generator.exe" 2>/dev/null \
    || die "ad-hoc signing the generator failed"
else
  native "$amu/$compiler" compile generator.kotoba --target "$target" --output generator.exe --format static
  grep -q "^{:ok true, :target :$target, :format :static, " "$work/native.stdout" \
    && [ -f "$work/build/generator.exe" ] \
    || die "Amu static build of the generator did not report success"
  chmod 755 "$work/build/generator.exe"
fi

for arg do
  shift
  case "$arg" in
    @size:*)
      name=${arg#@size:}
      case "$name" in ''|out|*/*|.*) die "invalid input name: $name" ;; esac
      [ -f "$work/scope/$name" ] || die "@size names no staged input: $name"
      arg=$(wc -c < "$work/scope/$name" | tr -d ' ') ;;
  esac
  set -- "$@" "$arg"
done
status=0
if [ "$route" = macos ]; then
  (cd "$work/scope" && env -i PATH=/nonexistent "$work/build/generator.exe" out "$@" 3<.)
else
  # shellcheck disable=SC2046
  (cd "$work/scope" && env -i $(linux_env "$work/scope") "$work/build/generator.exe" out "$@")
fi > "$work/run.stdout" 2> "$work/run.stderr" || status=$?
if [ "$status" != 0 ] || [ -s "$work/run.stderr" ] || [ ! -f "$work/scope/out" ] || [ -L "$work/scope/out" ]; then
  cat "$work/run.stderr" >&2
  die "$(basename "$generator") refused (exit $status); $dest not written"
fi
cat "$work/run.stdout"
mv -f "$work/scope/out" "$dest"
