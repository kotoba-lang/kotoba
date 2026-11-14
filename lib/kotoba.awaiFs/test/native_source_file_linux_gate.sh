#!/bin/sh
# Local Linux arm64 Native smoke; pin validation and an empty output are mandatory.
set -eu
[ "$#" -eq 2 ] || { echo 'usage: gate PINNED_AMU NEW_OUTPUT' >&2; exit 2; }
[ "$(uname -s)" = Linux ] && [ "$(uname -m)" = aarch64 ] || exit 2
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
amu=$(CDPATH= cd -- "$1" && pwd -P)
parent=$(CDPATH= cd -- "$(dirname -- "$2")" && pwd -P)
out="$parent/$(basename -- "$2")"
case "$out" in *[!a-zA-Z0-9_./-]*) echo 'unsupported path character' >&2; exit 2;; esac
mkdir "$out"
compiler="$amu/seed/bootstrap/aarch64-linux-static-root.elf"
provider="$amu/seed/x86_64-kx64-runner.kotoba"
pins="$repo/lib/kotoba.awaiFs/native-inputs.json"
for key in seed/bootstrap/aarch64-linux-static-root.elf seed/x86_64-kx64-runner.kotoba; do
 [ -f "$amu/$key" ] && [ ! -L "$amu/$key" ] || exit 1
 [ "$(sha256sum "$amu/$key" | cut -d' ' -f1)" = "$(jq -er --arg k "$key" '.files[$k].sha256' "$pins")" ] || exit 1
done
mkdir -p "$out/src/awai/fs"
cp "$repo/lib/kotoba.awaiFs/src/awai/fs/source_file.kotoba" "$out/src/awai/fs/"
printf abcdef > "$out/input"
dd if=/dev/zero bs=1 count=262138 status=none >> "$out/input"
printf xyz >> "$out/input"
printf abcdef > "$out/short-input"
export KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608
build() {
 label=$1; path=$2; count=$3
 sed -e "s@SOURCE_INPUT_PATH@$path@g" -e "s/read-range path 2 3/read-range path 2 $count/" "$repo/lib/kotoba.awaiFs/test/native_source_file_smoke.kotoba" > "$out/src/main.kotoba"
 { printf 'KSL1\nentry %s/src/main.kotoba\nroot %s/src\n' "$out" "$out"; find "$out/src" -name '*.kotoba' -type f | LC_ALL=C sort | while IFS= read -r p; do printf 'file %s %s\n' "$(sha256sum "$p" | cut -d' ' -f1)" "$p"; done; } > "$out/$label.ksl"
 "$compiler" compile "$out/src/main.kotoba" --target aarch64-macos --output "$out/$label.kseed" --source-path "$out/src" --source-lock "$out/$label.ksl" --source-lock-sha256 "$(sha256sum "$out/$label.ksl" | cut -d' ' -f1)" > "$out/$label.compile.stdout" 2> "$out/$label.compile.stderr"
 "$compiler" compile "$provider" --target aarch64-linux --output "$out/$label.elf" --format packed --payload "$out/$label.kseed" > "$out/$label.pack.stdout" 2> "$out/$label.pack.stderr"
 chmod 700 "$out/$label.elf"
}
build positive "$out/input" 3
build missing "$out/missing" 3
build short "$out/short-input" 7
export KEXE_ALLOW=35 KEXE_CAP_RESOURCES_35="$out" KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456
"$out/positive.elf" > "$out/positive.stdout" 2> "$out/positive.stderr"
grep -Eq ':status :ok[[:space:]]+:result 0([^0-9]|$)' "$out/positive.stdout"
for label in missing short; do
 status=0; "$out/$label.elf" > "$out/$label.stdout" 2> "$out/$label.stderr" || status=$?
 [ "$status" -eq 126 ] && grep -q ':fs/range-unavailable' "$out/$label.stderr" || exit 1
done
printf 'Native bounded source read and provider refusals passed\n'
