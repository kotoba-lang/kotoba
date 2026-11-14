#!/bin/sh
# Linux arm64 Native commit/export gate. Inputs and private output are pinned.
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
mkdir -p "$out/src/awai/fs" "$out/src/ipld" "$out/src/multiformats" "$out/src/zstd" "$out/store" "$out/exports"
for file in forest_blocks forest_commit forest_export forest_file forest_generation_verify forest_head forest_index forest_index_write forest_source_stage forest_stream forest_verified_publish forest_view logical_file source_file; do
 cp "$repo/lib/kotoba.awaiFs/src/awai/fs/$file.kotoba" "$out/src/awai/fs/"
done
cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$out/src/ipld/"
for file in byte_cid cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$file.kotoba" "$out/src/multiformats/"; done
for file in frame_header frame_write; do cp "$repo/lib/org.ietf.zstd/src/zstd/$file.kotoba" "$out/src/zstd/"; done
printf '\255' > "$out/input"
sed -e "s@PARENT@$out/store@g" -e "s@OUT@$out/exports@g" -e "s@INPUT@$out/input@g" "$repo/lib/kotoba.awaiFs/test/native_forest_export_gate.kotoba" > "$out/src/main.kotoba"
{ printf 'KSL1\nentry %s/src/main.kotoba\nroot %s/src\n' "$out" "$out"; find "$out/src" -name '*.kotoba' -type f | LC_ALL=C sort | while IFS= read -r p; do printf 'file %s %s\n' "$(sha256sum "$p" | cut -d' ' -f1)" "$p"; done; } > "$out/source.ksl"
export KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608
"$compiler" compile "$out/src/main.kotoba" --target aarch64-macos --output "$out/program.kseed" --source-path "$out/src" --source-lock "$out/source.ksl" --source-lock-sha256 "$(sha256sum "$out/source.ksl" | cut -d' ' -f1)" > "$out/compile.stdout" 2> "$out/compile.stderr"
"$compiler" compile "$provider" --target aarch64-linux --output "$out/program.elf" --format packed --payload "$out/program.kseed" > "$out/pack.stdout" 2> "$out/pack.stderr"
chmod 700 "$out/program.elf"
export KEXE_ALLOW=35 KEXE_CAP_RESOURCES_35="$out" KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456
"$out/program.elf" > "$out/run.stdout" 2> "$out/run.stderr"
grep -Eq ':status :ok[[:space:]]+:result 0([^0-9]|$)' "$out/run.stdout"
cmp "$out/input" "$out/exports/file-gate"
test ! -e "$out/exports/file-wrong"
printf 'Native cooperative commit/export and negative controls passed\n'
