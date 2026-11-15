#!/bin/sh
set -eu
[ "$#" -eq 1 ] || { echo 'usage: test_stage_corpus.sh NEW_OUTPUT' >&2; exit 2; }
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
corpus="$here/../corpus/v1.json" out=$1
mkdir "$out"
sh "$here/stage_corpus.sh" "$corpus" "$out/positive" > "$out/positive.stdout"
[ "$(find "$out/positive" -type f -name '*.kotoba' | wc -l | tr -d ' ')" -eq 53 ]
out=$(CDPATH= cd -- "$out" && pwd -P)
if command -v sha256sum >/dev/null 2>&1; then
 (cd "$out/positive" && sha256sum -c "$here/stage_corpus.sha256") > "$out/goldens.stdout"
else
 (cd "$out/positive" && shasum -a 256 -c "$here/stage_corpus.sha256") > "$out/goldens.stdout"
fi
reject() { if sh "$here/stage_corpus.sh" "$out/$1.json" "$out/$1-out" > "$out/$1.stdout" 2> "$out/$1.stderr"; then echo "$1 unexpectedly accepted" >&2; exit 1; fi; }
jq '.positive=[.positive[0]] | .positive[0].wireHex="0" | .negative=[] | .legacyPacks.cases=[]' "$corpus" > "$out/odd.json"; reject odd
jq '.positive=[] | .negative=[.negative[0]] | .negative[0].wireHex="GG" | .legacyPacks.cases=[]' "$corpus" > "$out/nonhex.json"; reject nonhex
jq '.positive=[.positive[0]] | .positive[0].input.version=null | .negative=[] | .legacyPacks.cases=[]' "$corpus" > "$out/invalid-positive.json"; reject invalid-positive
jq '.positive=[] | .negative=[] | .legacyPacks.cases=[.legacyPacks.cases[0]] | .legacyPacks.cases[0].inputHex=["0x"]' "$corpus" > "$out/invalid-pack.json"; reject invalid-pack
jq '.positive="bad"' "$corpus" > "$out/invalid-array.json"; reject invalid-array
dd if=/dev/zero of="$out/oversize.json" bs=1048576 count=9 2>/dev/null; reject oversize
if sh "$here/stage_corpus.sh" "$corpus" "$out/positive" > "$out/existing.stdout" 2> "$out/existing.stderr"; then echo 'existing output unexpectedly accepted' >&2; exit 1; fi
printf '53 corpus fixtures and 7 refusal controls passed\n'
