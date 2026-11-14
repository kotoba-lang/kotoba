#!/bin/sh
# Native macOS/arm64 stream SHA gate. Shell orchestrates; Native determines verdicts.
set -eu
if [ "$#" -ne 2 ]; then echo "usage: $0 <pinned-amu-checkout> <new-output-dir>" >&2; exit 2; fi
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || { echo 'requires native macOS arm64' >&2; exit 2; }
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
amu=$(CDPATH= cd -- "$1" && pwd -P)
parent=$(CDPATH= cd -- "$(dirname -- "$2")" && pwd -P)
out="$parent/$(basename -- "$2")"
mkdir "$out" || { echo 'output exists or cannot be created' >&2; exit 2; }
compiler="$amu/seed/bootstrap/aarch64-macos/amu-full-root.macho"
packager="$amu/seed/bootstrap/aarch64-macos/kotoba-packager-root.macho"
pins="$repo/lib/kotoba.awaiFs/native-inputs.json"
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
check_pin() {
  path=$1; key=$2
  [ -f "$path" ] && [ ! -L "$path" ] || { echo 'missing or symlinked artifact' >&2; exit 1; }
  expected=$(jq -er --arg k "$key" '.files[$k].sha256' "$pins")
  [ "$(sha "$path")" = "$expected" ] || { echo 'artifact digest mismatch' >&2; exit 1; }
  codesign --verify --strict "$path"
}
check_pin "$compiler" seed/bootstrap/aarch64-macos/amu-full-root.macho
check_pin "$packager" seed/bootstrap/aarch64-macos/kotoba-packager-root.macho
cp "$compiler" "$out/compiler"
cp "$packager" "$out/packager"
check_pin "$out/compiler" seed/bootstrap/aarch64-macos/amu-full-root.macho
check_pin "$out/packager" seed/bootstrap/aarch64-macos/kotoba-packager-root.macho
chmod 700 "$out/compiler" "$out/packager"
source_sha=$(sha "$repo/lib/kotoba.ioMultiformats/src/multiformats/sha256.kotoba")
test_sha=$(sha "$repo/lib/kotoba.awaiFs/test/native_stream_sha.kotoba")
for mode in positive negative; do
  dir="$out/$mode"
  mkdir -p "$dir/src/multiformats"
  cp "$repo/lib/kotoba.awaiFs/test/native_stream_sha.kotoba" "$dir/src/corpus.kotoba"
  cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/sha256.kotoba" "$dir/src/multiformats/sha256.kotoba"
  [ "$(sha "$dir/src/corpus.kotoba")" = "$test_sha" ] &&
    [ "$(sha "$dir/src/multiformats/sha256.kotoba")" = "$source_sha" ] || { echo 'source changed during staging' >&2; exit 1; }
  if [ "$mode" = negative ]; then
    [ "$(grep -c 'case index 0 1779033703' "$dir/src/multiformats/sha256.kotoba")" = 1 ] || { echo 'negative anchor changed' >&2; exit 1; }
    sed 's/case index 0 1779033703/case index 0 1779033702/' "$dir/src/multiformats/sha256.kotoba" > "$dir/mutated"
    mv "$dir/mutated" "$dir/src/multiformats/sha256.kotoba"
  fi
  {
    printf 'KSL1\nentry /src/corpus.kotoba\nroot /src\n'
    printf 'file %s /src/corpus.kotoba\n' "$(sha "$dir/src/corpus.kotoba")"
    printf 'file %s /src/multiformats/sha256.kotoba\n' "$(sha "$dir/src/multiformats/sha256.kotoba")"
  } > "$dir/source.ksl"
  lock=$(sha "$dir/source.ksl")
  (
    cd "$dir"
    exec 3<.
    "$out/compiler" compile /src/corpus.kotoba --target aarch64-macos --output program.kseed --source-path /src --source-lock source.ksl --source-lock-sha256 "$lock" > compile.stdout 2> compile.stderr
    "$out/compiler" extract-native program.kseed --symbol main --output program.raw > extract.stdout 2> extract.stderr
    offset=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\1/p' extract.stdout)
    length=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\2/p' extract.stdout)
    [ -n "$offset" ] && [ -n "$length" ] && [ "$length" = "$(wc -c < program.raw | tr -d ' ')" ] || { echo 'invalid extracted entry' >&2; exit 1; }
    "$out/packager" unsigned.macho program.raw fs2-cli-stdio-general "$offset" > pack.stdout 2> pack.stderr
    cp unsigned.macho program.macho
    chmod 700 program.macho
    codesign --force --sign - program.macho > sign.stdout 2> sign.stderr
    status=0
    ./program.macho > run.stdout 2> run.stderr || status=$?
    printf '%s\n' "$status" > exit.txt
    if [ "$mode" = positive ]; then [ "$status" -eq 0 ]; else [ "$status" -eq 1 ]; fi
  ) || { echo "$mode Native control failed; retained $dir" >&2; exit 1; }
done
[ "$(sha "$repo/lib/kotoba.ioMultiformats/src/multiformats/sha256.kotoba")" = "$source_sha" ] &&
  [ "$(sha "$repo/lib/kotoba.awaiFs/test/native_stream_sha.kotoba")" = "$test_sha" ] || { echo 'source changed during gate' >&2; exit 1; }
printf 'Native stream SHA positive=0 negative=1\n'
