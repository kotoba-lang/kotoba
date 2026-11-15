#!/bin/sh
# Python-free frozen corpus gate. Native artifacts decide every case verdict.
set -eu
[ "$#" -ge 3 ] && [ "$#" -le 4 ] || { echo 'usage: native_corpus_gate.sh TARGET PINNED_AMU NEW_OUTPUT [PINNED_X86_IO_AMU]' >&2; exit 2; }
target=$1
amu=$(CDPATH= cd -- "$2" && pwd -P)
parent=$(CDPATH= cd -- "$(dirname -- "$3")" && pwd -P)
out="$parent/$(basename -- "$3")"
case "$out" in *[!a-zA-Z0-9_./-]*) echo 'unsupported output path' >&2; exit 2;; esac
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd -P)
lib="$repo/lib/kotoba.awaiFs" pins="$lib/native-inputs.json"
case "$target:$(uname -s):$(uname -m)" in
 macos-arm64:Darwin:arm64) compiler_key=seed/bootstrap/aarch64-macos/amu-full-root.macho; provider_key=seed/bootstrap/aarch64-macos/kotoba-packager-root.macho;;
 linux-arm64:Linux:aarch64) compiler_key=seed/bootstrap/aarch64-linux-static-root.elf; provider_key=seed/x86_64-kx64-runner.kotoba;;
 linux-x86_64:Linux:x86_64) compiler_key=bin/amu-linux-x86_64; provider_key=seed/x86_64-kx64-runner.kotoba;;
 *) echo 'requires declared native host ISA' >&2; exit 2;;
esac
mkdir "$out"
sha() { if command -v sha256sum >/dev/null 2>&1; then sha256sum "$1" | awk '{print $1}'; else shasum -a 256 "$1" | awk '{print $1}'; fi; }
check_pin() {
 path=$1 key=$2
 [ -f "$path" ] && [ ! -L "$path" ] || { echo 'missing or linked artifact' >&2; exit 1; }
 [ "$(sha "$path")" = "$(jq -er --arg k "$key" '.files[$k].sha256' "$pins")" ] || { echo 'artifact pin mismatch' >&2; exit 1; }
 if [ "$target" = macos-arm64 ]; then /usr/bin/codesign --verify --strict "$path"; fi
}
check_pin "$amu/$compiler_key" "$compiler_key"; check_pin "$amu/$provider_key" "$provider_key"
compiler="$out/compiler" provider="$out/provider.kotoba"
if [ "$target" = macos-arm64 ]; then provider="$out/provider"; fi
cp "$amu/$compiler_key" "$compiler"; cp "$amu/$provider_key" "$provider"
check_pin "$compiler" "$compiler_key"; check_pin "$provider" "$provider_key"; chmod 700 "$compiler"
if [ "$target" = macos-arm64 ]; then chmod 700 "$provider"; fi
if [ "$target" = linux-x86_64 ]; then
 [ "$#" -eq 4 ] || { echo 'x86 I/O compiler checkout required' >&2; exit 2; }
 io_amu=$(CDPATH= cd -- "$4" && pwd -P)
 io_revision=$(jq -er '.x86FileCompiler.revision' "$pins")
 io_path=$(jq -er '.x86FileCompiler.path' "$pins")
 [ "$(git -C "$io_amu" rev-parse HEAD)" = "$io_revision" ]
 [ -f "$io_amu/$io_path" ] && [ ! -L "$io_amu/$io_path" ]
 [ "$(wc -c < "$io_amu/$io_path" | tr -d ' ')" = "$(jq -er '.x86FileCompiler.bytes' "$pins")" ]
 [ "$(sha "$io_amu/$io_path")" = "$(jq -er '.x86FileCompiler.sha256' "$pins")" ]
 io_compiler="$out/io-compiler"; cp "$io_amu/$io_path" "$io_compiler"
 [ "$(sha "$io_compiler")" = "$(jq -er '.x86FileCompiler.sha256' "$pins")" ]; chmod 700 "$io_compiler"
fi
for d in lib/kotoba.awaiFs lib/kotoba.ioIpld lib/kotoba.ioMultiformats lib/kotoba.ioIpldCar; do sh "$repo/scripts/check-library-local-changes-pins.sh" --root "$repo/$d"; done > "$out/pin-audit-before.jsonl"
# Keep an independent before/after record of every source and fixture consumed
# by this gate, including the compiler copies, not just the library ledgers.
{
 printf '%s\n' "$pins" "$lib/schema/v1.json" "$lib/corpus/v1.json" "$lib/test/native_corpus_gate.sh" "$lib/test/stage_corpus.sh" "$lib/test/stage_corpus.jq" "$lib/test/stage_corpus.sha256" "$repo/scripts/check-library-local-changes-pins.sh" "$amu/$compiler_key" "$amu/$provider_key" "$compiler" "$provider"
 for d in lib/kotoba.awaiFs lib/kotoba.ioIpld lib/kotoba.ioMultiformats lib/kotoba.ioIpldCar; do printf '%s\n' "$repo/$d/local-changes.json"; done
 for f in "$lib"/src/awai/fs/*.kotoba "$lib"/test/*.kotoba "$lib"/test/fixtures/* "$repo"/lib/kotoba.ioIpld/src/ipld/*.kotoba "$repo"/lib/kotoba.ioIpldCar/src/ipld/car/*.kotoba "$repo"/lib/kotoba.ioMultiformats/src/multiformats/*.kotoba "$repo"/lib/org.ietf.cbor/src/cbor/*.kotoba "$repo"/lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba "$repo"/lib/org.ietf.zstd/src/zstd/*.kotoba "$repo"/lib/org.ietf.zstd/test/zstd/frame_header_test.kotoba "$repo"/lib/org.ietf.deflate/src/deflate/*.kotoba "$repo"/lib/org.ietf.deflate/test/deflate/*_test.kotoba; do [ -f "$f" ] && printf '%s\n' "$f"; done
 if [ "$target" = linux-x86_64 ]; then printf '%s\n' "$io_amu/$io_path" "$io_compiler"; fi
} | LC_ALL=C sort -u > "$out/input-paths.txt"
while IFS= read -r watched_path; do
 [ -f "$watched_path" ] && [ ! -L "$watched_path" ] || { echo 'missing or linked input' >&2; exit 1; }
 printf '%s %s\n' "$(sha "$watched_path")" "$watched_path"
done < "$out/input-paths.txt" > "$out/input-sha256.txt"
printf 'case\tresult\tsource_lock_sha256\tartifact_sha256\n' > "$out/results.tsv"
sh "$lib/test/stage_corpus.sh" "$lib/corpus/v1.json" "$out/fixtures" > "$out/stage.stdout"
jq -e '(.positive|length)==11 and (.negative|length)==36 and (.legacyPacks.cases|length)==6' "$lib/corpus/v1.json" >/dev/null
if command -v sha256sum >/dev/null 2>&1; then (cd "$out/fixtures" && sha256sum -c "$lib/test/stage_corpus.sha256") > "$out/goldens.stdout"
else (cd "$out/fixtures" && shasum -a 256 -c "$lib/test/stage_corpus.sha256") > "$out/goldens.stdout"; fi
if [ "$target" = linux-x86_64 ]; then
 env -i PATH=/nonexistent LANG=C KEXE_STACK_BYTES=8388608 KEXE_CAP_RESOURCES_35="$out" "$compiler" compile "$provider" --target x86_64-linux --output "$out/runner.elf" --format kx64-runner > "$out/runner.stdout" 2> "$out/runner.stderr"
 [ ! -s "$out/runner.stderr" ]; chmod 700 "$out/runner.elf"
fi
# Replace exactly one literal anchor; source mutation is confined to test output.
replace_once() {
 file=$1 needle=$2 replacement=$3
 awk -v needle="$needle" -v repl="$replacement" 'BEGIN {n=0} {p=index($0,needle); if(p){n++; rest=substr($0,p+length(needle)); if(index(rest,needle)) n++; $0=substr($0,1,p-1) repl rest} print} END {if(n!=1) exit 1}' "$file" > "$file.changed"
 mv "$file.changed" "$file"
}
copy_fixture() {
 cf_source=$1 cf_dest=$2 cf_expected=$3
 [ -f "$cf_source" ] && [ ! -L "$cf_source" ] && [ "$(sha "$cf_source")" = "$cf_expected" ] || { echo 'fixture pin mismatch' >&2; exit 1; }
 cp "$cf_source" "$cf_dest"
 [ "$(sha "$cf_dest")" = "$cf_expected" ] || { echo 'fixture changed while copying' >&2; exit 1; }
}
flip_byte() {
 file=$1 offset=$2
 value=$(od -An -tu1 -j "$offset" -N 1 "$file" | tr -d ' ')
 [ -n "$value" ] || { echo 'mutation outside fixture' >&2; exit 1; }
 printf "\\$(printf '%03o' "$((value ^ 1))")" | dd of="$file" bs=1 seek="$offset" conv=notrunc 2>/dev/null
}
stage_io_fixtures() {
 dir=$1 control=$2 base="$lib/test/fixtures"
 copy_fixture "$base/forest-part0.car.zst" "$dir/fixture" 87a1d2773c099ef49af8fc7b9b00b43123a4e83ab1bc3f1f2b3fca0278fb62df
 copy_fixture "$base/forest-part1.car.zst" "$dir/fixture-second" 33469df01bb4f837d655da9b232a366910ab4a575094235ffc875029f46ad206
 copy_fixture "$base/forest-large-index.car.zst" "$dir/fixture-large" eea07036e8a76dd891f675a198a3da90afa4181f31794c910f376fe27b7bd39f
 copy_fixture "$base/forest-megaframe.car.zst" "$dir/fixture-mega" ee5c2c5c601e5f24cbf087ac73f8e9cfdd3bfa3002445e426b48a9756e6c0d50
 copy_fixture "$base/forest-gib-pack0.car.zst" "$dir/fixture-gib-0" 932d89b5e28f61bba5a2fd644b04e8201186218afa90ae5194d8434dbabe6b4f
 copy_fixture "$base/forest-gib-pack1.car.zst" "$dir/fixture-gib-1" aa2f7daab2da7bc8f145e439748589e64d7ea1c72b716de0532738a40627bdfc
 copy_fixture "$base/gib-manifest.cbor" "$dir/gib-manifest" 1760ba196e18e6b1ed18477b2a42ed7eee248c191000c41ef2629fc6ebf48d1e
 cp "$dir/fixture" "$dir/fixture-corrupt"; flip_byte "$dir/fixture-corrupt" 119
 cp "$dir/fixture" "$dir/fixture-hidden"; flip_byte "$dir/fixture-hidden" 1639
 cp "$dir/fixture" "$dir/fixture-badfooter"; flip_byte "$dir/fixture-badfooter" 1751
 head -c 1766 "$dir/fixture" > "$dir/fixture-short"
 cp "$dir/fixture-large" "$dir/fixture-large-bad-index"; flip_byte "$dir/fixture-large-bad-index" 1154951
 cp "$dir/fixture-mega" "$dir/fixture-mega-corrupt"; flip_byte "$dir/fixture-mega-corrupt" 524288
 if [ "$control" = tampered-gib-manifest ]; then
  marker=6ffb6ccd5ca18062fb3e6175f6682800e623056b77256e074f1fef9ceb10b900
  hex=$(od -An -v -tx1 "$dir/gib-manifest" | tr -d ' \n')
  before=${hex%%"$marker"*}; rest=${hex#*"$marker"}
  [ "$before" != "$hex" ] && [ "${rest#*"$marker"}" = "$rest" ] || { echo 'manifest mutation anchor differs' >&2; exit 1; }
  [ $((${#before} % 2)) -eq 0 ]; flip_byte "$dir/gib-manifest" $((${#before}/2))
 fi
}
run_case() {
 kind=$1 index=$2 control=$3 expected=$4
 name="$kind-$index"; [ "$control" = none ] || name="$name-$control"
 dir="$out/$name"; src="$dir/src"; mkdir -p "$src/awai/fs" "$src/ipld" "$src/multiformats"
 file_case=false
 if [ "$kind" = primitive ] && { [ "$index" = forest_file_io ] || [ "$index" = forest_manifest_io ] || [ "$index" = native_prolly_checkpoint_io ]; }; then file_case=true; fi
 if [ "$kind" = primitive ]; then
  if [ "${index#deflate_}" != "$index" ]; then
   cp "$repo/lib/org.ietf.deflate/test/deflate/${index#deflate_}_test.kotoba" "$src/corpus.kotoba"
  elif [ "$index" = zstd_header ]; then
   cp "$repo/lib/org.ietf.zstd/test/zstd/frame_header_test.kotoba" "$src/corpus.kotoba"
  else cp "$lib/test/$index.kotoba" "$src/corpus.kotoba"; fi
 else cp "$out/fixtures/$kind-$index.kotoba" "$src/corpus.kotoba"; fi
 if [ "$kind" = primitive ] && [ "${index#deflate_}" != "$index" ]; then
  mkdir "$src/deflate"
  case "$index" in
   deflate_bit_reader) modules='bit_reader';;
   deflate_huffman_reader) modules='bit_reader huffman_reader';;
   deflate_dynamic_tables) modules='bit_reader huffman_reader dynamic_tables';;
   deflate_huffman_block) modules='bit_reader huffman_reader huffman_block';;
   deflate_zlib_single) modules='bit_reader huffman_reader dynamic_tables huffman_block zlib_single';;
   *) exit 1;;
  esac
  for mod in $modules; do cp "$repo/lib/org.ietf.deflate/src/deflate/$mod.kotoba" "$src/deflate/"; done
 elif [ "$kind" = primitive ] && { [ "$index" = native_logical_signature ] || [ "$index" = native_logical_commit_test ] || [ "$index" = native_one_parent_basis ]; }; then
  case "$index" in
   native_logical_signature) modules='logical_signature';;
   native_logical_commit_test) modules='logical_commit';;
   native_one_parent_basis) modules='basis_edn logical_commit logical_signature basis_verify';;
  esac
  for mod in $modules; do cp "$lib/src/awai/fs/$mod.kotoba" "$src/awai/fs/"; done
  if [ "$index" != native_logical_signature ]; then cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/sha256.kotoba" "$src/multiformats/"; fi
  if [ "$index" != native_logical_commit_test ]; then mkdir "$src/ed25519"; cp "$repo/lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba" "$src/ed25519/"; fi
 elif [ "$kind" = primitive ] && [ "$index" = native_prolly_checkpoint_io ]; then
  mkdir "$src/cbor" "$src/zstd" "$src/ed25519"
  cp "$repo/lib/org.ietf.ed25519/kotoba/ed25519/selfhost.kotoba" "$src/ed25519/"
  for mod in codec value fragment; do cp "$repo/lib/org.ietf.cbor/src/cbor/$mod.kotoba" "$src/cbor/"; done
  for mod in frame_header forest_frame literal_header fse_description fse_weights huffman_tree huffman_literals sequence_offset; do cp "$repo/lib/org.ietf.zstd/src/zstd/$mod.kotoba" "$src/zstd/"; done
  for mod in forest_blocks forest_index forest_file prolly_branch prolly_leaf prolly_checkpoint prolly_checkpoint_tree basis_edn logical_commit logical_signature basis_verify basis_checkpoint_tree basis_snapshot; do cp "$lib/src/awai/fs/$mod.kotoba" "$src/awai/fs/"; done
  for mod in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$mod.kotoba" "$src/multiformats/"; done
 elif [ "$kind" = primitive ] && [ "$index" = writer ]; then
  cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$src/ipld/"
  cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/cid.kotoba" "$src/multiformats/"
 elif [ "$kind" = primitive ] && { [ "$index" = zstd_header ] || [ "$index" = forest_file_io ]; }; then
  mkdir "$src/zstd"
  for mod in frame_header forest_frame literal_header fse_description fse_weights huffman_tree huffman_literals sequence_offset; do cp "$repo/lib/org.ietf.zstd/src/zstd/$mod.kotoba" "$src/zstd/"; done
  for mod in forest_blocks forest_index; do cp "$lib/src/awai/fs/$mod.kotoba" "$src/awai/fs/"; done
  for mod in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$mod.kotoba" "$src/multiformats/"; done
  if [ "$index" = forest_file_io ]; then cp "$lib/src/awai/fs/forest_file.kotoba" "$src/awai/fs/"; fi
 else
  if [ "$index" != pack_values ]; then cp "$lib/src/awai/fs/logical_file.kotoba" "$src/awai/fs/"; fi
  if [ "$index" = chunk_plan_values ]; then cp "$lib/src/awai/fs/chunk_plan.kotoba" "$src/awai/fs/"; fi
  cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$src/ipld/"
  for mod in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$mod.kotoba" "$src/multiformats/"; done
  if [ "$kind" = pack ] || [ "$index" = pack_values ]; then mkdir "$src/ipld/car"; cp "$repo/lib/kotoba.ioIpldCar/src/ipld/car/pack.kotoba" "$src/ipld/car/"; fi
  if [ "$index" = forest_manifest_io ]; then
   mkdir "$src/zstd"; for mod in frame_header forest_frame literal_header fse_description fse_weights huffman_tree huffman_literals sequence_offset; do cp "$repo/lib/org.ietf.zstd/src/zstd/$mod.kotoba" "$src/zstd/"; done
   for mod in forest_blocks forest_index forest_file forest_view; do cp "$lib/src/awai/fs/$mod.kotoba" "$src/awai/fs/"; done
  fi
 fi
 if [ "$file_case" = true ]; then
  stage_io_fixtures "$dir" "$control"
  if [ "$index" = native_prolly_checkpoint_io ]; then
   copy_fixture "$lib/test/fixtures/native-snapshot-pack.forest" "$dir/fixture-snapshot" 5fefcde7d85a4a6a24b526856b2fa7d65561478b839f6ea9161d15608a1fe0b8
   copy_fixture "$lib/test/fixtures/native-two-leaf.forest" "$dir/fixture-prolly" 7f1b770465aec12793110b30cc38b1705137ae863db1f4109bfc9a28e356ddf8
   copy_fixture "$lib/test/fixtures/native-two-leaf-bad-range.forest" "$dir/fixture-prolly-bad" 811e65afc12e358e1cc8a9c5e4b9f938ce7f330ff41d3232c5ad12d3821749ee
  fi
  if [ "$target" != macos-arm64 ]; then
   for fixture in fixture-snapshot fixture-prolly-bad fixture-prolly gib-manifest fixture fixture-second fixture-large fixture-large-bad-index fixture-mega fixture-mega-corrupt fixture-gib-0 fixture-gib-1 fixture-corrupt fixture-hidden fixture-badfooter fixture-short fixture-missing; do
    sed "s@\"/$fixture\"@\"$dir/$fixture\"@g" "$src/corpus.kotoba" > "$dir/paths.tmp"; mv "$dir/paths.tmp" "$src/corpus.kotoba"
   done
  fi
 fi
 case "$control" in
  allow-missing-snapshot) replace_once "$src/corpus.kotoba" '(result-ok?-of [:result :bool :keyword] snapshot-missing)' '(not (result-ok?-of [:result :bool :keyword] snapshot-missing))';;
  wrong-manifest-database) replace_once "$src/awai/fs/basis_snapshot.kotoba" '(value/text database)' '"different/database"';;
  wrong-manifest-epoch) replace_once "$src/awai/fs/basis_snapshot.kotoba" '(string-from-i64 (value/number basis-t))' '"999"';;
  wrong-snapshot-schema) replace_once "$src/awai/fs/basis_snapshot.kotoba" '(= (value/number schema) 2)' '(= (value/number schema) 3)';;
  wrong-prolly-checkpoint) replace_once "$src/corpus.kotoba" '(result-value-of [:result :string :keyword] good "") "994bf8778ef21d93f873dd5cfc759a543c0c1fea1066558419933bed649749a9"' '(result-value-of [:result :string :keyword] good "") "094bf8778ef21d93f873dd5cfc759a543c0c1fea1066558419933bed649749a9"';;
  wrong-logical-root) replace_once "$src/corpus.kotoba" '1fb3a3396ad238892be6df1e12f59a4e6866efdcc43ea5c243a6c07db1ee612e' '0fb3a3396ad238892be6df1e12f59a4e6866efdcc43ea5c243a6c07db1ee612e';;
  wrong-basis-issuer) replace_once "$src/corpus.kotoba" 'good (verify/verify (proof) "did:key:fixture-issuer" "fixture-key" pub)' 'good (verify/verify (proof) "did:key:wrong" "fixture-key" pub)';;
  wrong-signature-payload) replace_once "$src/corpus.kotoba" '[:domain :signature] [:value [:map' '[:domain :wrong] [:value [:map';;
  wrong-deflate-bit) replace_once "$src/corpus.kotoba" ':value) 2) 2' ':value) 3) 2';;
  wrong-deflate-huffman) replace_once "$src/corpus.kotoba" ':symbol) 1) 2' ':symbol) 2) 2';;
  wrong-deflate-zlib) replace_once "$src/corpus.kotoba" ':invalid-header) 2' ':invalid-byte) 2';;
  wrong-cid)
   old=$(jq -er '.positive[0].cid' "$lib/corpus/v1.json"); suffix=${old#"${old%?}"}; if [ "$suffix" = a ]; then new="${old%?}b"; else new="${old%?}a"; fi
   # The CID occurs twice in the positive fixture, and both checks must change.
   [ "$(grep -o -F "$old" "$src/corpus.kotoba" | wc -l | tr -d ' ')" = 2 ]
   sed "s/$old/$new/g" "$src/corpus.kotoba" > "$dir/mutated"; mv "$dir/mutated" "$src/corpus.kotoba";;
  allow-file-version) replace_once "$src/awai/fs/logical_file.kotoba" '(not= (record-get [:ref :awai.fs/file] f :version) 1)' false;;
  allow-link-codec) replace_once "$src/awai/fs/logical_file.kotoba" '(= (record-get [:ref :multiformats.cid/parts] p :codec) 85)' true;;
  allow-plan-overflow) replace_once "$src/awai/fs/chunk_plan.kotoba" '(> count 1024)' false;;
  wrong-zstd-window) replace_once "$src/corpus.kotoba" '(not= (record-get [:ref :zstd/header] forest :window-size) 2097152)' '(not= (record-get [:ref :zstd/header] forest :window-size) 2097151)';;
  wrong-zstd-block-size) replace_once "$src/corpus.kotoba" '(not= (record-get [:ref :zstd/block-header] first-block :size) 59)' '(not= (record-get [:ref :zstd/block-header] first-block :size) 58)';;
  wrong-zstd-raw-byte) replace_once "$src/corpus.kotoba" '(vector-i64 58 162 101 114 111 111 116 115' '(vector-i64 57 162 101 114 111 111 116 115';;
  wrong-zstd-literal-byte) replace_once "$src/corpus.kotoba" '(vector-i64 164 128 4 1 85 18 32 136' '(vector-i64 165 128 4 1 85 18 32 136';;
  wrong-zstd-sequence-count) replace_once "$src/corpus.kotoba" '(not= (record-get [:ref :zstd/sequences] sequences :count) 16)' '(not= (record-get [:ref :zstd/sequences] sequences :count) 15)';;
  wrong-zstd-fse-table) replace_once "$src/corpus.kotoba" '(vector-i64 0 4 0 0 4 16 1 5 32 3 5 0 4 5 0 6 5 0' '(vector-i64 0 4 1 0 4 16 1 5 32 3 5 0 4 5 0 6 5 0';;
  wrong-zstd-sequence-value) replace_once "$src/corpus.kotoba" '(vector-i64 295 7935 259 0 8165 8168' '(vector-i64 294 7935 259 0 8165 8168';;
  wrong-zstd-block-digest) replace_once "$src/corpus.kotoba" '(sha/digest-hex (record-get [:ref :zstd/execution] executed :bytes)) "3a3d9308758b3a794400d6d5c9e219ee38a15333bd83ddcf502ca65ef369e435"' '(sha/digest-hex (record-get [:ref :zstd/execution] executed :bytes)) "0a3d9308758b3a794400d6d5c9e219ee38a15333bd83ddcf502ca65ef369e435"';;
  wrong-zstd-integrated-digest) replace_once "$src/corpus.kotoba" '(sha/digest-hex (record-get [:ref :zstd/decoded-block] integrated :bytes)) "3a3d9308758b3a794400d6d5c9e219ee38a15333bd83ddcf502ca65ef369e435"' '(sha/digest-hex (record-get [:ref :zstd/decoded-block] integrated :bytes)) "0a3d9308758b3a794400d6d5c9e219ee38a15333bd83ddcf502ca65ef369e435"';;
  wrong-zstd-frame-digest) replace_once "$src/corpus.kotoba" 'f1d148ea23e71ce7a3578d639382ba4d491a57b9d131409f6ce881c19bb576ba' '01d148ea23e71ce7a3578d639382ba4d491a57b9d131409f6ce881c19bb576ba';;
  wrong-forest-block-digest) replace_once "$src/corpus.kotoba" '(sha/digest-hex (result-value-of [:result :vector-i64 :keyword] found (vector-i64))) "88493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd"' '(sha/digest-hex (result-value-of [:result :vector-i64 :keyword] found (vector-i64))) "08493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd"';;
  wrong-forest-indexed-digest) replace_once "$src/corpus.kotoba" '(sha/digest-hex (result-value-of [:result :vector-i64 :keyword] indexed (vector-i64))) "88493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd"' '(sha/digest-hex (result-value-of [:result :vector-i64 :keyword] indexed (vector-i64))) "08493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd"';;
  wrong-forest-file-digest) replace_once "$src/corpus.kotoba" '88493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd' '08493684995be5fa456234a868ebd583db8a1c23575861f41937e14dedd4ecfd';;
  wrong-second-forest-digest) replace_once "$src/corpus.kotoba" '7786c19371f6b8a948e551624e0dd2993ca6c21439bf876f67a14821807b8c88' '0786c19371f6b8a948e551624e0dd2993ca6c21439bf876f67a14821807b8c88';;
  wrong-megaframe-digest) replace_once "$src/corpus.kotoba" 'ef25f52bde3a24316912f2214e179ca2e56c21e78cd3ea76a06296e96ff2349e' '0f25f52bde3a24316912f2214e179ca2e56c21e78cd3ea76a06296e96ff2349e';;
  wrong-gib-pack-digest) replace_once "$src/corpus.kotoba" 'ad1925fe80c09fb367e0a7b3630232403b03161c78f50e432b48dc723258f4c0' '0d1925fe80c09fb367e0a7b3630232403b03161c78f50e432b48dc723258f4c0';;
  allow-group-error-fallback) replace_once "$src/awai/fs/forest_file.kotoba" '(recur (+ i 1)) r)' '(recur (+ i 1)) (recur (+ i 1)))';;
  wrong-gib-manifest-cid) replace_once "$src/corpus.kotoba" 'bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5endy' 'bafyreiaxmc5bs3qy42y62gchpmvef3l65ysiygiqadcb54tct7dox5enda';;
  tampered-gib-manifest) :;;
  ignore-view-manifest-cid) replace_once "$src/awai/fs/forest_view.kotoba" '(not (string=? expected-cid (hash/cidv1-dag-cbor-bytes wire)))' false;;
  none) :;; *) exit 2;;
 esac
 if [ "$target" = macos-arm64 ]; then entry=/src/corpus.kotoba; source_root=/src; else entry="$src/corpus.kotoba"; source_root="$src"; fi
 { printf 'KSL1\nentry %s\nroot %s\n' "$entry" "$source_root"
   find "$src" -name '*.kotoba' -type f | LC_ALL=C sort | while IFS= read -r path; do
    if [ "$target" = macos-arm64 ]; then locked="/${path#"$dir"/}"; else locked=$path; fi
    printf 'file %s %s\n' "$(sha "$path")" "$locked"
   done
 } > "$dir/source.ksl"
 lock=$(sha "$dir/source.ksl")
 if [ "$target" = macos-arm64 ]; then
  (
   cd "$dir"; exec 3<.
   env -i PATH=/nonexistent LANG=C "$compiler" compile "$entry" --target aarch64-macos --output program.kseed --source-path "$source_root" --source-lock source.ksl --source-lock-sha256 "$lock" > compile.stdout 2> compile.stderr
   env -i PATH=/nonexistent LANG=C "$compiler" extract-native program.kseed --symbol main --output program.raw > extract.stdout 2> extract.stderr
   offset=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\1/p' extract.stdout)
   length=$(sed -n 's/.*:offset \([0-9][0-9]*\), :length \([0-9][0-9]*\), :arity 0}.*/\2/p' extract.stdout)
   [ -n "$offset" ] && [ -n "$length" ] && [ "$length" = "$(wc -c < program.raw | tr -d ' ')" ]
   env -i PATH=/nonexistent LANG=C "$provider" unsigned.macho program.raw fs2-cli-stdio-general "$offset" > pack.stdout 2> pack.stderr
   cp unsigned.macho program.macho; chmod 700 program.macho; /usr/bin/codesign --force --sign - program.macho > sign.stdout 2> sign.stderr
   status=0; env -i PATH=/nonexistent LANG=C ./program.macho > run.stdout 2> run.stderr || status=$?
   [ "$status" -eq "$expected" ]
   [ ! -s run.stderr ]
  )
 elif [ "$target" = linux-arm64 ]; then
  env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608 "$compiler" compile "$entry" --target aarch64-macos --output "$dir/program.kseed" --source-path "$source_root" --source-lock "$dir/source.ksl" --source-lock-sha256 "$lock" > "$dir/compile.stdout" 2> "$dir/compile.stderr"
  env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608 "$compiler" compile "$provider" --target aarch64-linux --output "$dir/program.elf" --format packed --payload "$dir/program.kseed" > "$dir/pack.stdout" 2> "$dir/pack.stderr"
  chmod 700 "$dir/program.elf"
  if [ "$file_case" = true ]; then
   env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35 KEXE_CAP_RESOURCES_35="$dir" KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456 "$dir/program.elf" > "$dir/run.stdout" 2> "$dir/run.stderr"
  else env -i PATH=/nonexistent LANG=C KEXE_ALLOW=- KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456 "$dir/program.elf" > "$dir/run.stdout" 2> "$dir/run.stderr"; fi
  grep -Eq ":status :ok[[:space:]]+:result $expected([^0-9]|$)" "$dir/run.stdout"
  [ ! -s "$dir/run.stderr" ]
 else
  if [ "$file_case" = true ]; then
   if env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608 "$io_compiler" compile "$entry" --target x86_64-linux --output "$dir/program.kx64" --format kx64-v1 --source-path "$source_root" --source-lock "$dir/source.ksl" --source-lock-sha256 "$lock" > "$dir/compile-denied.stdout" 2> "$dir/compile-denied.stderr"; then echo 'x86 missing-capability control accepted' >&2; exit 1; fi
   cat "$dir/compile-denied.stdout" "$dir/compile-denied.stderr" | grep -q E7101
   [ ! -e "$dir/program.kx64" ]
   env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608 "$io_compiler" compile "$entry" --target x86_64-linux --output "$dir/program.kx64" --format kx64-v1 --source-path "$source_root" --source-lock "$dir/source.ksl" --source-lock-sha256 "$lock" --project-capabilities 35 > "$dir/compile.stdout" 2> "$dir/compile.stderr"
  else
   env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608 "$compiler" compile "$entry" --target x86_64-linux --output "$dir/program.kx64" --format kx64-v1 --source-path "$source_root" --source-lock "$dir/source.ksl" --source-lock-sha256 "$lock" > "$dir/compile.stdout" 2> "$dir/compile.stderr"
  fi
  header=$(head -n 1 "$dir/program.kx64")
  printf '%s\n' "$header" | grep -Eq '^KX64V1 x86_64-linux sysv-ctx-v11 [0-9]+ 0$'
  size=$(printf '%s\n' "$header" | awk '{print $4}'); skip=$((${#header}+2))
  tail -c "+$((skip+1))" "$dir/program.kx64" > "$dir/program.bin"
  [ "$(wc -c < "$dir/program.bin" | tr -d ' ')" = "$size" ]
  [ "$(od -An -tu1 -N1 "$dir/program.bin" | tr -d ' ')" = 233 ]
  if [ "$file_case" = true ]; then
   env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35 KEXE_CAP_RESOURCES_35="$dir" KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456 "$out/runner.elf" "$dir/program.bin" 0 0 x86_64 35 -- > "$dir/run.stdout" 2> "$dir/run.stderr"
  else env -i PATH=/nonexistent LANG=C KEXE_ALLOW=- KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456 "$out/runner.elf" "$dir/program.bin" 0 0 x86_64 - -- > "$dir/run.stdout" 2> "$dir/run.stderr"; fi
  grep -Eq ":status :ok[[:space:]]+:result $expected([^0-9]|$)" "$dir/run.stdout"
  [ ! -s "$dir/run.stderr" ]
 fi
 [ ! -s "$dir/compile.stderr" ] && [ ! -s "$dir/pack.stderr" ] && [ ! -s "$dir/extract.stderr" ] || { echo "$name compiler diagnostics" >&2; exit 1; }
 case "$target" in macos-arm64) artifact="$dir/program.macho";; linux-arm64) artifact="$dir/program.elf";; linux-x86_64) artifact="$dir/program.kx64";; esac
 printf '%s\t%s\t%s\t%s\n' "$name" "$expected" "$lock" "$(sha "$artifact")" >> "$out/results.tsv"
 printf 'PASS %s native-result=%s\n' "$name" "$expected"
}
for kind in positive negative pack; do
 case "$kind" in positive) count=11;; negative) count=36;; pack) count=6;; esac
 i=0; while [ "$i" -lt "$count" ]; do run_case "$kind" "$i" none 0; i=$((i+1)); done
done
run_case positive 0 wrong-cid 5
run_case negative 0 allow-file-version 1
run_case negative 23 allow-link-codec 1
for primitive in writer values pack_values chunk_plan_values zstd_header; do run_case primitive "$primitive" none 0; done
for primitive in native_logical_signature native_logical_commit_test native_one_parent_basis; do run_case primitive "$primitive" none 0; done
run_case primitive native_logical_signature wrong-signature-payload 2
run_case primitive native_logical_commit_test wrong-logical-root 2
run_case primitive native_one_parent_basis wrong-basis-issuer 1
for primitive in deflate_bit_reader deflate_huffman_reader deflate_dynamic_tables deflate_huffman_block deflate_zlib_single; do run_case primitive "$primitive" none 0; done
run_case primitive deflate_bit_reader wrong-deflate-bit 2
run_case primitive deflate_huffman_reader wrong-deflate-huffman 2
run_case primitive deflate_zlib_single wrong-deflate-zlib 2
run_case primitive chunk_plan_values allow-plan-overflow 8
run_case primitive zstd_header wrong-zstd-window 12
run_case primitive zstd_header wrong-zstd-block-size 28
run_case primitive zstd_header wrong-zstd-raw-byte 42
run_case primitive zstd_header wrong-zstd-literal-byte 52
run_case primitive zstd_header wrong-zstd-sequence-count 62
run_case primitive zstd_header wrong-zstd-fse-table 78
run_case primitive zstd_header wrong-zstd-sequence-value 85
run_case primitive zstd_header wrong-zstd-block-digest 94
run_case primitive zstd_header wrong-zstd-integrated-digest 108
run_case primitive zstd_header wrong-zstd-frame-digest 118
run_case primitive zstd_header wrong-forest-block-digest 128
run_case primitive zstd_header wrong-forest-indexed-digest 137
run_case primitive native_prolly_checkpoint_io none 0
run_case primitive native_prolly_checkpoint_io wrong-prolly-checkpoint 2
run_case primitive native_prolly_checkpoint_io wrong-snapshot-schema 7
run_case primitive native_prolly_checkpoint_io wrong-manifest-database 7
run_case primitive native_prolly_checkpoint_io wrong-manifest-epoch 7
run_case primitive native_prolly_checkpoint_io allow-missing-snapshot 13
run_case primitive forest_file_io none 0
run_case primitive forest_file_io wrong-forest-file-digest 3
run_case primitive forest_file_io wrong-second-forest-digest 13
run_case primitive forest_file_io wrong-megaframe-digest 31
run_case primitive forest_file_io wrong-gib-pack-digest 38
run_case primitive forest_file_io allow-group-error-fallback 20
run_case primitive forest_manifest_io none 0
run_case primitive forest_manifest_io wrong-gib-manifest-cid 4
run_case primitive forest_manifest_io tampered-gib-manifest 4
run_case primitive forest_manifest_io ignore-view-manifest-cid 10
if [ "$target" = linux-x86_64 ]; then
 [ "$(git -C "$io_amu" rev-parse HEAD)" = "$io_revision" ]
 [ ! -L "$io_amu/$io_path" ] && [ "$(sha "$io_amu/$io_path")" = "$(jq -er '.x86FileCompiler.sha256' "$pins")" ]
fi
for d in lib/kotoba.awaiFs lib/kotoba.ioIpld lib/kotoba.ioMultiformats lib/kotoba.ioIpldCar; do sh "$repo/scripts/check-library-local-changes-pins.sh" --root "$repo/$d"; done > "$out/pin-audit-after.jsonl"
[ "$(wc -l < "$out/results.tsv" | tr -d ' ')" = 105 ] || { echo 'result count mismatch' >&2; exit 1; }
while IFS=' ' read -r expected_hash watched_path; do
 [ -f "$watched_path" ] && [ ! -L "$watched_path" ] && [ "$(sha "$watched_path")" = "$expected_hash" ] || { echo "input drift: $watched_path" >&2; exit 1; }
done < "$out/input-sha256.txt"
printf 'Native frozen corpus 53 + 16 primitives + 35 negative controls passed on %s\n' "$target"
