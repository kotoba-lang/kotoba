#!/bin/sh
# Fresh macOS Native reader for the Native-produced GiB fixture.
set -eu
[ "$#" -eq 2 ] || { echo 'usage: gate PINNED_AMU EXISTING_WRITER_OUTPUT' >&2; exit 2; }
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || exit 2
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
amu=$(CDPATH= cd -- "$1" && pwd -P)
out=$(CDPATH= cd -- "$2" && pwd -P)
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
pins="$repo/lib/kotoba.awaiFs/native-inputs.json"
compiler="$amu/seed/bootstrap/aarch64-macos/amu-full-root.macho"
packager="$amu/seed/bootstrap/aarch64-macos/kotoba-packager-root.macho"
for spec in seed/bootstrap/aarch64-macos/amu-full-root.macho seed/bootstrap/aarch64-macos/kotoba-packager-root.macho; do
 p="$amu/$spec"; [ -f "$p" ] && [ ! -L "$p" ] || exit 1
 [ "$(sha "$p")" = "$(jq -er --arg k "$spec" '.files[$k].sha256' "$pins")" ] || exit 1
 codesign --verify --strict "$p"
done
[ "$(sha "$out/manifest")" = 71a79734dfdac0c0c910bc7786fbc579480150f1a5cdefebddb9c88c8c3d85a2 ] || exit 1
sizes=''
i=0
while [ "$i" -lt 64 ]; do
 p="$out/pack-$i"; [ -f "$p" ] && [ ! -L "$p" ] || exit 1
 [ "$(wc -c < "$p" | tr -d ' ')" = 2098986 ] || exit 1
 sizes="$sizes 2098986"; i=$((i+1))
done
mkdir "$out/read-src"
mkdir -p "$out/read-src/awai/fs" "$out/read-src/zstd" "$out/read-src/multiformats" "$out/read-src/ipld"
for f in logical_file forest_view forest_file forest_blocks forest_index; do cp "$repo/lib/kotoba.awaiFs/src/awai/fs/$f.kotoba" "$out/read-src/awai/fs/"; done
cp "$repo/lib/org.ietf.zstd/src/zstd/frame_header.kotoba" "$out/read-src/zstd/"
for f in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$f.kotoba" "$out/read-src/multiformats/"; done
cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$out/read-src/ipld/"
template="$repo/lib/kotoba.awaiFs/test/forest_gib_full.kotoba"
[ "$(grep -c 'bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy' "$template")" = 2 ] || exit 1
sed -e 's/bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy/bafyreidru6ltjx62ydamsef4o6dpxrlzjaavb4nfzxx6xxnzzcgiypmfui/g' \
    -e 's/dd4ec50fea8f5a68daf225da4945af367e25bb870a09346060fa9dc088c001b0/f0add2045c361a831c9298f69c09e65a79c0c83d38bc97bc84bfe9b909dc5d77/g' \
    -e 's@/gib-base/pack-@/pack-@g' -e 's@/gib-manifest@/manifest@g' \
    -e "s/sizes (vector-i64 .*]/sizes (vector-i64$sizes)]/" "$template" > "$out/read-src/main.kotoba"
{
 printf 'KSL1\nentry /read-src/main.kotoba\nroot /read-src\n'
 find "$out/read-src" -type f -name '*.kotoba' | LC_ALL=C sort | while IFS= read -r p; do rel=${p#"$out"}; printf 'file %s %s\n' "$(sha "$p")" "$rel"; done
} > "$out/read-source.ksl"
(
 cd "$out"; exec 3<.
 "$compiler" compile /read-src/main.kotoba --target aarch64-macos --output read.kseed --source-path /read-src --source-lock read-source.ksl --source-lock-sha256 "$(sha read-source.ksl)" > read-compile.stdout 2> read-compile.stderr
 "$compiler" extract-native read.kseed --symbol main --output read.raw > read-extract.stdout 2> read-extract.stderr
 offset=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\1/p' read-extract.stdout)
 length=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\2/p' read-extract.stdout)
 [ -n "$offset" ] && [ "$length" = "$(wc -c < read.raw | tr -d ' ')" ] || exit 1
 "$packager" read-unsigned.macho read.raw fs2-cli-stdio-general "$offset" > read-pack.stdout 2> read-pack.stderr
 cp read-unsigned.macho read.macho; chmod 700 read.macho; codesign --force --sign - read.macho > read-sign.stdout 2> read-sign.stderr
 ./read.macho > read.stdout 2> read.stderr
 cp pack-31 saved-pack-31
 printf '\000' | dd of=pack-31 bs=1 seek=2098970 conv=notrunc 2>/dev/null
 status=0; ./read.macho > corrupt.stdout 2> corrupt.stderr || status=$?
 [ "$status" -eq 41 ] || exit 1
 mv saved-pack-31 pack-31
 mv pack-0 withheld-pack-0
 status=0; ./read.macho > missing.stdout 2> missing.stderr || status=$?
 [ "$status" -eq 10 ] || exit 1
 mv withheld-pack-0 pack-0
)
printf 'Native GiB reader and negative controls: pass\n'
