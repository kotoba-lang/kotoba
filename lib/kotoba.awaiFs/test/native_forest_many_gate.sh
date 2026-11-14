#!/bin/sh
# Local macOS Native multi-Pack Forest writer; no host codec in this gate.
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
for f in forest_write forest_index_write forest_index forest_blocks logical_file; do cp "$repo/lib/kotoba.awaiFs/src/awai/fs/$f.kotoba" "$out/src/awai/fs/"; done
for f in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$f.kotoba" "$out/src/multiformats/"; done
cp "$repo/lib/kotoba.ioIpldCar/src/ipld/car/pack.kotoba" "$out/src/ipld/car/"
cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$out/src/ipld/"
cp "$repo/lib/kotoba.awaiFs/test/native_forest_many_write.kotoba" "$out/src/main.kotoba"
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
printf 'Native Forest 17 Pack writer: pass\n'
# Fresh Native reader, using a known independently verified logical manifest CID.
mkdir -p "$out/read-src/awai/fs" "$out/read-src/zstd" "$out/read-src/multiformats" "$out/read-src/ipld"
for f in logical_file forest_view forest_file forest_blocks forest_index; do cp "$repo/lib/kotoba.awaiFs/src/awai/fs/$f.kotoba" "$out/read-src/awai/fs/"; done
cp "$repo/lib/org.ietf.zstd/src/zstd/frame_header.kotoba" "$out/read-src/zstd/"
for f in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$f.kotoba" "$out/read-src/multiformats/"; done
cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$out/read-src/ipld/"
sizes='1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913 1048913'
template="$repo/lib/kotoba.awaiFs/test/forest_gib_search.kotoba"
[ "$(grep -c 'bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy' "$template")" = 2 ] || exit 1
sed -e 's/bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy/bafyreibm3flucfif36n3vnyhnv3vdmqrjg4rmmrftagn6g7hbicbmv3kni/g' \
    -e 's/dd4ec50fea8f5a68daf225da4945af367e25bb870a09346060fa9dc088c001b0/3bc244af7f35c24af1098f036eb25d20f95c7a4e9cfc137e173d438de3451133/g' \
    -e 's@/gib-base/pack-@/pack-@g' -e 's@/gib-manifest@/manifest@g' \
    -e 's/(= j 64)/(= j 17)/g' -e 's/71783/1291/g' -e 's/71788/1296/g' \
    -e 's/1073741824/17825792/g' -e 's/1024 38/17 38/g' -e 's/(= i 1024)/(= i 17)/g' \
    -e "s/sizes (vector-i64 .*]/sizes (vector-i64 $sizes)]/" "$template" > "$out/read-src/main.kotoba"
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
 cp pack-8 saved-pack-8
 printf '\000' | dd of=pack-8 bs=1 seek=1048897 conv=notrunc 2>/dev/null
 status=0; ./read.macho > corrupt.stdout 2> corrupt.stderr || status=$?
 [ "$status" -eq 10 ] || exit 1
 mv saved-pack-8 pack-8
 mv pack-8 withheld-pack-8
 status=0; ./read.macho > missing.stdout 2> missing.stderr || status=$?
 [ "$status" -eq 10 ] || exit 1
 mv withheld-pack-8 pack-8
)
printf 'Native Forest 17 Pack writer + fresh reader + negative controls: pass\n'
