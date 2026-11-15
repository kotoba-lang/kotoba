#!/bin/sh
# Disposable negative controls for the source ledger auditor.
set -eu
[ "$#" -eq 1 ] || { echo 'usage: test NEW_OUTPUT_DIRECTORY' >&2; exit 2; }
repo=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
out=$1
mkdir "$out"
mkdir "$out/root" "$out/root/sub"
printf 'ledger fixture\n' > "$out/root/sub/file"
if command -v sha256sum >/dev/null 2>&1; then h=$(sha256sum "$out/root/sub/file"); else h=$(shasum -a 256 "$out/root/sub/file"); fi
h=${h%% *}
jq -n --arg h "$h" '{schema:"kotoba.library-local-changes.v1",files:{"sub/file":{sha256:$h}},added:{}}' > "$out/root/local-changes.json"
"$repo/scripts/check-library-local-changes-pins.sh" --root "$out/root" > "$out/positive.stdout"
reject() { if "$repo/scripts/check-library-local-changes-pins.sh" --root "$out/root" --manifest "$out/$1.json" > "$out/$1.stdout" 2> "$out/$1.stderr"; then echo "$1 unexpectedly accepted" >&2; exit 1; fi; }
jq '.schema="other"' "$out/root/local-changes.json" > "$out/schema.json"; reject schema
jq '.files["sub/file"].sha256="bad"' "$out/root/local-changes.json" > "$out/hash-format.json"; reject hash-format
jq '.files["sub/file"].sha256="0000000000000000000000000000000000000000000000000000000000000000"' "$out/root/local-changes.json" > "$out/stale.json"; reject stale
jq --arg h "$h" '.files={"../escape":{sha256:$h}}' "$out/root/local-changes.json" > "$out/traversal.json"; reject traversal
jq --arg h "$h" '.files={"missing":{sha256:$h}}' "$out/root/local-changes.json" > "$out/missing.json"; reject missing
jq --arg h "$h" '.added={"sub/file":{sha256:("0"*64)}}' "$out/root/local-changes.json" > "$out/conflict.json"; reject conflict
ln -s sub/file "$out/root/link"
jq --arg h "$h" '.files={"link":{sha256:$h}}' "$out/root/local-changes.json" > "$out/leaf-link.json"; reject leaf-link
ln -s sub "$out/root/dirlink"
jq --arg h "$h" '.files={"dirlink/file":{sha256:$h}}' "$out/root/local-changes.json" > "$out/parent-link.json"; reject parent-link
printf 'source pin audit positive and 8 negative controls passed\n'
