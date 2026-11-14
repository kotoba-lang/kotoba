#!/bin/sh
# Local macOS Native full Forest writer and reader; no host codec in this gate.
set -eu
[ "$#" -eq 2 ] || { echo 'usage: gate PINNED_AMU NEW_OUTPUT' >&2; exit 2; }
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || exit 2
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
amu=$(CDPATH= cd -- "$1" && pwd -P)
parent=$(CDPATH= cd -- "$(dirname -- "$2")" && pwd -P)
out="$parent/$(basename -- "$2")"
mkdir "$out"
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
pins="$repo/lib/kotoba.awaiFs/native-inputs.json"
compiler="$amu/seed/bootstrap/aarch64-macos/amu-full-root.macho"
packager="$amu/seed/bootstrap/aarch64-macos/kotoba-packager-root.macho"
for spec in seed/bootstrap/aarch64-macos/amu-full-root.macho seed/bootstrap/aarch64-macos/kotoba-packager-root.macho; do
 p="$amu/$spec"; [ -f "$p" ] && [ ! -L "$p" ] || exit 1
 [ "$(sha "$p")" = "$(jq -er --arg k "$spec" '.files[$k].sha256' "$pins")" ] || exit 1
 codesign --verify --strict "$p"
done
mkdir -p "$out/src/zstd" "$out/src/awai/fs" "$out/src/multiformats" "$out/src/ipld/car" "$out/src/ipld"
for f in frame_write frame_header; do cp "$repo/lib/org.ietf.zstd/src/zstd/$f.kotoba" "$out/src/zstd/"; done
for f in forest_write forest_index_write forest_index forest_blocks; do cp "$repo/lib/kotoba.awaiFs/src/awai/fs/$f.kotoba" "$out/src/awai/fs/"; done
for f in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$f.kotoba" "$out/src/multiformats/"; done
cp "$repo/lib/kotoba.ioIpldCar/src/ipld/car/pack.kotoba" "$out/src/ipld/car/"
cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$out/src/ipld/"
cp "$repo/lib/kotoba.awaiFs/test/native_forest_write.kotoba" "$out/src/main.kotoba"
{
 printf 'KSL1\nentry /src/main.kotoba\nroot /src\n'
 find "$out/src" -type f -name '*.kotoba' | LC_ALL=C sort | while IFS= read -r p; do rel=${p#"$out"}; printf 'file %s %s\n' "$(sha "$p")" "$rel"; done
} > "$out/source.ksl"
(
 cd "$out"; exec 3<.
 "$compiler" compile /src/main.kotoba --target aarch64-macos --output program.kseed --source-path /src --source-lock source.ksl --source-lock-sha256 "$(sha source.ksl)" > compile.stdout 2> compile.stderr
 "$compiler" extract-native program.kseed --symbol main --output program.raw > extract.stdout 2> extract.stderr
 offset=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\1/p' extract.stdout)
 length=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\2/p' extract.stdout)
 [ -n "$offset" ] && [ "$length" = "$(wc -c < program.raw | tr -d ' ')" ] || exit 1
 "$packager" unsigned.macho program.raw fs2-cli-stdio-general "$offset" > pack.stdout 2> pack.stderr
 cp unsigned.macho program.macho; chmod 700 program.macho; codesign --force --sign - program.macho > sign.stdout 2> sign.stderr
 ./program.macho > run.stdout 2> run.stderr
)
printf 'Native Forest full Pack writer and reader: pass\n'
