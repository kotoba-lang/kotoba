#!/bin/sh
# Materialize fixed corpus literals only; does not implement codec or verdicts.
set -eu
[ "$#" -eq 2 ] || { echo 'usage: stage_corpus.sh CORPUS NEW_OUTPUT' >&2; exit 2; }
corpus=$1 out=$2
here=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd -P)
[ -f "$corpus" ] && [ ! -L "$corpus" ] || { echo 'corpus missing or linked' >&2; exit 1; }
bytes=$(wc -c < "$corpus" | tr -d ' ')
[ "$bytes" -le 8388608 ] || { echo 'corpus exceeds 8 MiB' >&2; exit 1; }
command -v jq >/dev/null 2>&1 || { echo 'jq unavailable' >&2; exit 1; }
jq -e '(.positive|type=="array" and length<=4096) and (.negative|type=="array" and length<=4096) and (.legacyPacks.cases|type=="array" and length<=4096)' "$corpus" >/dev/null
mkdir "$out"
for kind in positive negative pack; do
 case "$kind" in positive) filter='.positive|length';; negative) filter='.negative|length';; pack) filter='.legacyPacks.cases|length';; esac
 n=$(jq -er "$filter" "$corpus")
 i=0
 while [ "$i" -lt "$n" ]; do
  jq -erj --arg kind "$kind" --argjson index "$i" -f "$here/stage_corpus.jq" "$corpus" > "$out/$kind-$i.kotoba"
  i=$((i+1))
 done
done
printf 'staged positive=%s negative=%s pack=%s\n' "$(jq '.positive|length' "$corpus")" "$(jq '.negative|length' "$corpus")" "$(jq '.legacyPacks.cases|length' "$corpus")"
