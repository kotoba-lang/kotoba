#!/bin/sh
# Local Native index writer/reader cross-check; no host decoder in this gate.
set -eu
[ "$#" -eq 4 ] || { echo 'usage: gate PINNED_AMU EXTRACTED_2PACK PINNED_NATIVE_READER NEW_OUTPUT' >&2; exit 2; }
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || exit 2
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
amu=$(CDPATH= cd -- "$1" && pwd -P)
input=$(CDPATH= cd -- "$2" && pwd -P)
reader=$3
parent=$(CDPATH= cd -- "$(dirname -- "$4")" && pwd -P)
out="$parent/$(basename -- "$4")"
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
[ -f "$reader" ] && [ ! -L "$reader" ] || exit 1
[ "$(sha "$reader")" = 38af499f3e09ff715c43639360d62662b4722f087bd9a3e623af46a83e5a4731 ] || exit 1
codesign --verify --strict "$reader"
[ "$(sha "$input/gib-manifest")" = 544e4bec081da2206e56b9a70bcca5298983acabb5e0969fbe4c33ea4a191254 ] || exit 1
[ "$(sha "$input/pack-0")" = 1ffa9f0d3d1f02a5cb51657e12d5bce607478253fa5bfb0dc5ca29a9bbb7e23a ] || exit 1
[ "$(sha "$input/pack-1")" = 654bf3ccb1c1a8424436cadd3641d6f24060ad16de0abe2a75e3b8e888917644 ] || exit 1
mkdir -p "$out/src/awai/fs" "$out/src/zstd" "$out/src/multiformats" "$out/gib-base"
for f in forest_index_write forest_index forest_blocks; do cp "$repo/lib/kotoba.awaiFs/src/awai/fs/$f.kotoba" "$out/src/awai/fs/"; done
cp "$repo/lib/org.ietf.zstd/src/zstd/frame_header.kotoba" "$out/src/zstd/"
for f in sha256 cid byte_cid; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$f.kotoba" "$out/src/multiformats/"; done
cp "$repo/lib/kotoba.awaiFs/test/native_forest_index_write.kotoba" "$out/src/main.kotoba"
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
 ./program.macho > writer.stdout 2> writer.stderr
 [ "$(wc -c < index | tr -d ' ')" = 104 ] || exit 1
 dd if="$input/pack-1" of=gib-base/pack-1 bs=65536 count=16 2>/dev/null
 dd if="$input/pack-1" of=tail.tmp bs=1 skip=1048576 count=242 2>/dev/null
 cat tail.tmp index >> gib-base/pack-1
 cp "$input/pack-0" gib-base/pack-0
 cp "$input/gib-manifest" gib-manifest
 cp "$reader" reader.macho; chmod 700 reader.macho; codesign --verify --strict reader.macho
 ./reader.macho > reader.stdout 2> reader.stderr
)
printf 'Native Forest index write + two-Pack read: pass\n'
