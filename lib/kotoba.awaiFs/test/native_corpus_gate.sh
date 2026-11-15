#!/bin/sh
# Python-free frozen corpus gate. Native artifacts decide every case verdict.
set -eu
[ "$#" -eq 3 ] || { echo 'usage: native_corpus_gate.sh TARGET PINNED_AMU NEW_OUTPUT' >&2; exit 2; }
target=$1
amu=$(CDPATH= cd -- "$2" && pwd -P)
parent=$(CDPATH= cd -- "$(dirname -- "$3")" && pwd -P)
out="$parent/$(basename -- "$3")"
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
for d in lib/kotoba.awaiFs lib/kotoba.ioIpld lib/kotoba.ioMultiformats lib/kotoba.ioIpldCar; do sh "$repo/scripts/check-library-local-changes-pins.sh" --root "$repo/$d"; done > "$out/pin-audit-before.jsonl"
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
 awk -v needle="$needle" -v repl="$replacement" 'BEGIN {n=0} {p=index($0,needle); if(p){n++; $0=substr($0,1,p-1) repl substr($0,p+length(needle))} print} END {if(n!=1) exit 1}' "$file" > "$file.changed"
 mv "$file.changed" "$file"
}
run_case() {
 kind=$1 index=$2 control=$3 expected=$4
 name="$kind-$index"; [ "$control" = none ] || name="$name-$control"
 dir="$out/$name"; src="$dir/src"; mkdir -p "$src/awai/fs" "$src/ipld" "$src/multiformats"
 cp "$out/fixtures/$kind-$index.kotoba" "$src/corpus.kotoba"
 cp "$lib/src/awai/fs/logical_file.kotoba" "$src/awai/fs/"
 cp "$repo/lib/kotoba.ioIpld/src/ipld/dag_cbor_write.kotoba" "$src/ipld/"
 for mod in cid byte_cid sha256; do cp "$repo/lib/kotoba.ioMultiformats/src/multiformats/$mod.kotoba" "$src/multiformats/"; done
 if [ "$kind" = pack ]; then mkdir "$src/ipld/car"; cp "$repo/lib/kotoba.ioIpldCar/src/ipld/car/pack.kotoba" "$src/ipld/car/"; fi
 case "$control" in
  wrong-cid)
   old=$(jq -er '.positive[0].cid' "$lib/corpus/v1.json"); suffix=${old#"${old%?}"}; if [ "$suffix" = a ]; then new="${old%?}b"; else new="${old%?}a"; fi
   # The CID occurs twice in the positive fixture, and both checks must change.
   [ "$(grep -o -F "$old" "$src/corpus.kotoba" | wc -l | tr -d ' ')" = 2 ]
   sed "s/$old/$new/g" "$src/corpus.kotoba" > "$dir/mutated"; mv "$dir/mutated" "$src/corpus.kotoba";;
  allow-file-version) replace_once "$src/awai/fs/logical_file.kotoba" '(not= (record-get [:ref :awai.fs/file] f :version) 1)' false;;
  allow-link-codec) replace_once "$src/awai/fs/logical_file.kotoba" '(= (record-get [:ref :multiformats.cid/parts] p :codec) 85)' true;;
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
  env -i PATH=/nonexistent LANG=C KEXE_ALLOW=- KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456 "$dir/program.elf" > "$dir/run.stdout" 2> "$dir/run.stderr"
  grep -Eq ":status :ok[[:space:]]+:result $expected([^0-9]|$)" "$dir/run.stdout"
  [ ! -s "$dir/run.stderr" ]
 else
  env -i PATH=/nonexistent LANG=C KEXE_ALLOW=35,37,38,39 KEXE_CAP_RESOURCES_35="$out:$amu" KEXE_STACK_BYTES=8388608 "$compiler" compile "$entry" --target x86_64-linux --output "$dir/program.kx64" --format kx64-v1 --source-path "$source_root" --source-lock "$dir/source.ksl" --source-lock-sha256 "$lock" > "$dir/compile.stdout" 2> "$dir/compile.stderr"
  header=$(head -n 1 "$dir/program.kx64")
  printf '%s\n' "$header" | grep -Eq '^KX64V1 x86_64-linux sysv-ctx-v11 [0-9]+ 0$'
  size=$(printf '%s\n' "$header" | awk '{print $4}'); skip=$((${#header}+2))
  tail -c "+$((skip+1))" "$dir/program.kx64" > "$dir/program.bin"
  [ "$(wc -c < "$dir/program.bin" | tr -d ' ')" = "$size" ]
  [ "$(od -An -tu1 -N1 "$dir/program.bin" | tr -d ' ')" = 233 ]
  env -i PATH=/nonexistent LANG=C KEXE_ALLOW=- KEXE_FUEL=off KEXE_STRUCTURED_REPORT=1 KEXE_STRING_POOL=268435456 "$out/runner.elf" "$dir/program.bin" 0 0 x86_64 - -- > "$dir/run.stdout" 2> "$dir/run.stderr"
  grep -Eq ":status :ok[[:space:]]+:result $expected([^0-9]|$)" "$dir/run.stdout"
  [ ! -s "$dir/run.stderr" ]
 fi
 [ ! -s "$dir/compile.stderr" ] && [ ! -s "$dir/pack.stderr" ] || { echo "$name compiler diagnostics" >&2; exit 1; }
 printf 'PASS %s native-result=%s\n' "$name" "$expected"
}
for kind in positive negative pack; do
 case "$kind" in positive) count=11;; negative) count=36;; pack) count=6;; esac
 i=0; while [ "$i" -lt "$count" ]; do run_case "$kind" "$i" none 0; i=$((i+1)); done
done
run_case positive 0 wrong-cid 5
run_case negative 0 allow-file-version 1
run_case negative 23 allow-link-codec 1
for d in lib/kotoba.awaiFs lib/kotoba.ioIpld lib/kotoba.ioMultiformats lib/kotoba.ioIpldCar; do sh "$repo/scripts/check-library-local-changes-pins.sh" --root "$repo/$d"; done > "$out/pin-audit-after.jsonl"
printf 'Native frozen corpus 53 + 3 negative controls passed on %s\n' "$target"
