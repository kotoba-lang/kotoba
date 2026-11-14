#!/bin/sh
# macOS arm64 Native FS2 E boundary observation, not a concurrent-race test.
set -eu
[ "$#" -eq 2 ] || { echo 'usage: probe <pinned-amu> <new-output>' >&2; exit 2; }
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || exit 2
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
amu=$(CDPATH= cd -- "$1" && pwd -P)
parent=$(CDPATH= cd -- "$(dirname -- "$2")" && pwd -P)
out="$parent/$(basename -- "$2")"
mkdir "$out"
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
pins="$repo/lib/kotoba.awaiFs/native-inputs.json"
for spec in 'seed/bootstrap/aarch64-macos/amu-full-root.macho' 'seed/bootstrap/aarch64-macos/kotoba-packager-root.macho'; do
 p="$amu/$spec"; [ -f "$p" ] && [ ! -L "$p" ] || exit 1
 [ "$(sha "$p")" = "$(jq -er --arg k "$spec" '.files[$k].sha256' "$pins")" ] || exit 1
 codesign --verify --strict "$p"
done
cp "$amu/seed/bootstrap/aarch64-macos/amu-full-root.macho" "$out/compiler"
cp "$amu/seed/bootstrap/aarch64-macos/kotoba-packager-root.macho" "$out/packager"
[ "$(sha "$out/compiler")" = "$(jq -er '.files["seed/bootstrap/aarch64-macos/amu-full-root.macho"].sha256' "$pins")" ] || exit 1
[ "$(sha "$out/packager")" = "$(jq -er '.files["seed/bootstrap/aarch64-macos/kotoba-packager-root.macho"].sha256' "$pins")" ] || exit 1
codesign --verify --strict "$out/compiler"; codesign --verify --strict "$out/packager"
template="$repo/lib/kotoba.awaiFs/test/native_fs2_range_probe.kotoba"
[ "$(grep -c 'E/PATH.*SPEC' "$template")" = 1 ] || exit 1
for mode in valid missing short; do
 mkdir -p "$out/$mode/src"; printf A > "$out/$mode/fixture"
 path=fixture; spec=0:1; expected=0
 [ "$mode" != missing ] || { path=absent; expected=133; }
 [ "$mode" != short ] || { spec=0:2; expected=133; }
 sed -e "s/PATH/$path/g" -e "s/SPEC/$spec/g" "$template" > "$out/$mode/src/main.kotoba"
 (
  cd "$out/$mode"; exec 3<.
  printf 'KSL1\nentry /src/main.kotoba\nroot /src\nfile %s /src/main.kotoba\n' "$(sha src/main.kotoba)" > source.ksl
  "$out/compiler" compile /src/main.kotoba --target aarch64-macos --output program.kseed --source-path /src --source-lock source.ksl --source-lock-sha256 "$(sha source.ksl)" > compile.stdout 2> compile.stderr
  "$out/compiler" extract-native program.kseed --symbol main --output program.raw > extract.stdout 2> extract.stderr
  offset=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\1/p' extract.stdout)
  length=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\2/p' extract.stdout)
  [ -n "$offset" ] && [ "$length" = "$(wc -c < program.raw | tr -d ' ')" ] || exit 1
  "$out/packager" unsigned.macho program.raw fs2-cli-stdio-general "$offset" > pack.stdout 2> pack.stderr
  cp unsigned.macho program.macho; chmod 700 program.macho; codesign --force --sign - program.macho > sign.stdout 2> sign.stderr
  status=0; ./program.macho > run.stdout 2> run.stderr || status=$?
  printf '%s\n' "$status" > result.txt
  [ "$status" -eq "$expected" ]
 )
done
printf 'Native FS2 E: valid=0 missing=133 short=133\n'
