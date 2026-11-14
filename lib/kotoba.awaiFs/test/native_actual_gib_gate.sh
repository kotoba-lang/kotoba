#!/bin/sh
# Native macOS arm64: actual Otehon-generated 1 GiB Forest set. No host decoder.
set -eu
[ "$#" -eq 3 ] || { echo 'usage: gate <pinned-amu> <extracted-input> <new-output>' >&2; exit 2; }
[ "$(uname -s)" = Darwin ] && [ "$(uname -m)" = arm64 ] || exit 2
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
amu=$(CDPATH= cd -- "$1" && pwd -P)
input=$(CDPATH= cd -- "$2" && pwd -P)
parent=$(CDPATH= cd -- "$(dirname -- "$3")" && pwd -P)
out="$parent/$(basename -- "$3")"
mkdir "$out"
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
pins="$repo/lib/kotoba.awaiFs/native-inputs.json"
compiler="$amu/seed/bootstrap/aarch64-macos/amu-full-root.macho"
packager="$amu/seed/bootstrap/aarch64-macos/kotoba-packager-root.macho"
for spec in 'seed/bootstrap/aarch64-macos/amu-full-root.macho' 'seed/bootstrap/aarch64-macos/kotoba-packager-root.macho'; do
 p="$amu/$spec"; [ -f "$p" ] && [ ! -L "$p" ] || exit 1
 [ "$(sha "$p")" = "$(jq -er --arg k "$spec" '.files[$k].sha256' "$pins")" ] || exit 1
 codesign --verify --strict "$p"
done
[ "$(sha "$input/gib-manifest")" = '6ad8ee19460070aa33963ed713c6ffb5f0c66660a65629ae676b44566e813c37' ] || exit 1
list="$repo/lib/kotoba.awaiFs/test/actual-gib-packs.tsv"
[ "$(wc -l < "$list" | tr -d ' ')" = 64 ] || exit 1
mkdir -p "$out/src/awai/fs" "$out/src/ipld" "$out/src/zstd" "$out/src/multiformats" "$out/gib-base"
for f in logical_file forest_view forest_file forest_blocks forest_index; do cp "$repo/lib/kotoba.awaiFs/src/awai/fs/$f.kotoba" "$out/src/awai/fs/$f.kotoba"; done
cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$out/src/ipld/dag_cbor_write.kotoba"
cp "$repo/lib/org.ietf.zstd/src/zstd/frame_header.kotoba" "$out/src/zstd/frame_header.kotoba"
for f in sha256 cid byte_cid; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$f.kotoba" "$out/src/multiformats/$f.kotoba"; done
cp "$input/gib-manifest" "$out/gib-manifest"
i=0
while IFS="$(printf '\t')" read -r index size digest; do
 [ "$index" = "$i" ] || exit 1
 p="$input/pack-$i"; [ -f "$p" ] && [ ! -L "$p" ] || exit 1
 [ "$(wc -c < "$p" | tr -d ' ')" = "$size" ] && [ "$(sha "$p")" = "$digest" ] || exit 1
 cp "$p" "$out/gib-base/pack-$i"
 [ "$(sha "$out/gib-base/pack-$i")" = "$digest" ] || exit 1
 i=$((i+1))
done < "$list"
[ "$i" = 64 ] || exit 1
sizes=$(awk '{printf "%s%s", (NR==1?"":" "), $2}' "$list")
template="$repo/lib/kotoba.awaiFs/test/forest_gib_full.kotoba"
[ "$(grep -c 'bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy' "$template")" = 2 ] || exit 1
[ "$(grep -c 'dd4ec50fea8f5a68daf225da4945af367e25bb870a09346060fa9dc088c001b0' "$template")" = 1 ] || exit 1
[ "$(grep -c 'sizes (vector-i64 ' "$template")" = 1 ] || exit 1
sed -e 's/bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy/bafyreidk3dxbsrqaocvdhfr624j4n75v6ddgmyfgkyu24z3lirlg5aj4g4/g' \
    -e 's/dd4ec50fea8f5a68daf225da4945af367e25bb870a09346060fa9dc088c001b0/1f7e0c0d3fefe5579e556a04f7796b7de01278916e49a6d31df864e16adf1708/g' \
    -e "s/sizes (vector-i64 .*]/sizes (vector-i64 $sizes)]/" \
    "$template" > "$out/src/corpus.kotoba"
{
 printf 'KSL1\nentry /src/corpus.kotoba\nroot /src\n'
 find "$out/src" -type f -name '*.kotoba' -print | LC_ALL=C sort | while IFS= read -r p; do
   rel=${p#"$out"}; printf 'file %s %s\n' "$(sha "$p")" "$rel"
 done
} > "$out/source.ksl"
lock=$(sha "$out/source.ksl")
(
 cd "$out"; exec 3<.
 "$compiler" compile /src/corpus.kotoba --target aarch64-macos --output program.kseed --source-path /src --source-lock source.ksl --source-lock-sha256 "$lock" > compile.stdout 2> compile.stderr
 "$compiler" extract-native program.kseed --symbol main --output program.raw > extract.stdout 2> extract.stderr
 offset=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\1/p' extract.stdout)
 length=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\2/p' extract.stdout)
 [ -n "$offset" ] && [ "$length" = "$(wc -c < program.raw | tr -d ' ')" ] || exit 1
 "$packager" unsigned.macho program.raw fs2-cli-stdio-general "$offset" > pack.stdout 2> pack.stderr
 cp unsigned.macho program.macho; chmod 700 program.macho; codesign --force --sign - program.macho > sign.stdout 2> sign.stderr
 ./program.macho > positive.stdout 2> positive.stderr
 printf '0\n' > positive.exit
 # A distinct saved copy remains intact; corrupt only the staged Pack 31.
 byte=$(od -An -tu1 -j 100 -N 1 gib-base/pack-31 | tr -d ' ')
 if [ "$byte" = 0 ]; then printf '\001' | dd of=gib-base/pack-31 bs=1 seek=100 conv=notrunc 2>/dev/null; else printf '\000' | dd of=gib-base/pack-31 bs=1 seek=100 conv=notrunc 2>/dev/null; fi
 status=0; ./program.macho > negative.stdout 2> negative.stderr || status=$?
 printf '%s\n' "$status" > negative.exit
 [ "$status" -eq 41 ]
 cp "$input/pack-31" gib-base/pack-31
 mv gib-base/pack-31 missing-pack-31.saved
 status=0; ./program.macho > missing.stdout 2> missing.stderr || status=$?
 printf '%s\n' "$status" > missing.exit
 [ "$status" -eq 41 ]
)
printf 'actual Otehon 1 GiB Native read: positive=0 corrupt-Pack-31=41 missing-Pack-31=41\n'
