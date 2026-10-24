#!/usr/bin/env bash
# Execute Kotoba's runtime source graph using the freshly self-built compiler.
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
source "$root/scripts/native-toolchain.env"
toolchain=${1:?usage: test-selfhost-runtime.sh TOOLCHAIN AMU_NATIVE_SOURCES BYTES_SOURCES NEW_OUTPUT}
compiler_sources=${2:?missing Amu native source snapshot}
bytes_sources=${3:?missing bytes source snapshot}
output=${4:?missing fresh output directory}
[ ! -e "$output" ] || { echo "output already exists" >&2; exit 73; }
toolchain=$(CDPATH= cd -- "$toolchain" && pwd -P)
compiler_sources=$(CDPATH= cd -- "$compiler_sources" && pwd -P)
bytes_sources=$(CDPATH= cd -- "$bytes_sources" && pwd -P)
mkdir -p -- "$output"
output=$(CDPATH= cd -- "$output" && pwd -P)
mkdir "$output/objects" "$output/logs"
compiler=$toolchain/artifacts/G3.bin
loader=$toolchain/host/kexe-loader
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
[ "$(sha "$compiler")" = "$FIXED_IMAGE_SHA256" ] || { echo "compiler pin mismatch" >&2; exit 65; }
# The immutable historical source snapshots are supplied by the workflow (git
# archive at exact revisions), not mutable sibling checkouts or classpaths.
roots=("$root/src" "$root/test/fixtures" "$root/vendor/grammar/src" "$compiler_sources" "$bytes_sources")
scopes=$output
options=()
for path in "${roots[@]}"; do
  case "$path" in *:*|*$'\n'*) echo "source path cannot contain colon/newline" >&2; exit 65 ;; esac
  scopes=$scopes:$path
  options+=(--source-path "$path")
done
loader_sha=$(sha "$loader")
invoke() {
  local name=$1
  shift
  [ "$(sha "$compiler")" = "$FIXED_IMAGE_SHA256" ]
  [ "$(sha "$loader")" = "$loader_sha" ]
  env -i PATH="$PATH" TMPDIR="$output" \
    KEXE_COMMAND=1 KEXE_CAP_RESOURCES_35="$scopes" KEXE_FUEL=500000000 \
    KEXE_PAIRS=16777216 KEXE_VECTORS=4194304 KEXE_VECTOR_ITEMS=134217728 \
    KEXE_STRING_POOL=268435456 KEXE_CPU_SECONDS=300 KEXE_WALL_SECONDS=300 \
    "$loader" "$compiler" 0 0 aarch64 3,35,37,38,39 -- "$@" \
    > "$output/logs/$name.stdout" 2> "$output/logs/$name.stderr"
}
fixture=$root/test/fixtures/native-runtime-values.kotoba
invoke modules modules "$fixture" "${options[@]}" --unpinned
: > "$output/sources.sha256"
count=0
entry=
while IFS=' ' read -r namespace file; do
  [[ "$namespace" =~ ^[a-zA-Z0-9_.-]+$ ]] || { echo "invalid module name" >&2; exit 65; }
  shasum -a 256 "$file" >> "$output/sources.sha256"
  if [ "$file" = "$fixture" ]; then
    entry=$namespace
    invoke "compile-$count" compile "$file" --emit-module --entry \
      --object-dir "$output/objects" --output "$output/objects/$namespace.kso"
  else
    invoke "compile-$count" compile "$file" --emit-module \
      --object-dir "$output/objects" --output "$output/objects/$namespace.kso"
  fi
  count=$((count + 1))
done < "$output/logs/modules.stdout"
[ "$count" -eq 19 ] && [ -n "$entry" ] || {
  echo "unexpected runtime closure: $count modules" >&2; exit 65;
}
invoke link link "$output/objects/$entry.kso" --object-dir "$output/objects" \
  --output "$output/runtime.kseed"
invoke extract extract-native "$output/runtime.kseed" --symbol main --output "$output/runtime.bin"
offset=$(sed -n 's/.*:offset \([0-9][0-9]*\).*/\1/p' "$output/logs/extract.stdout")
[[ "$offset" =~ ^[0-9]+$ ]] || { echo "missing entry offset" >&2; exit 65; }
execute() {
  local fuel=$1
  env -i PATH="$PATH" KEXE_STRUCTURED_REPORT=1 KEXE_ARENA_USE=1 \
    KEXE_FUEL="$fuel" KEXE_PAIRS=1048576 KEXE_VECTORS=262144 \
    KEXE_VECTOR_ITEMS=4194304 KEXE_STRING_POOL=16777216 \
    KEXE_CPU_SECONDS=30 KEXE_WALL_SECONDS=30 \
    "$loader" "$output/runtime.bin" "$offset" 0 aarch64 -
}
execute 5000000 > "$output/logs/execute.stdout" 2> "$output/logs/execute.stderr"
grep -Eq ':status :ok :result 127([ }]|$)' "$output/logs/execute.stdout"
if execute 1 > "$output/logs/fuel.stdout" 2> "$output/logs/fuel.stderr"; then
  echo "expected native fuel exhaustion" >&2; exit 1
fi
grep -q ':status :trap' "$output/logs/fuel.stdout"
grep -q ':fuel {:initial 1 :remaining 0}' "$output/logs/fuel.stdout"
# Unavailable target/policy routes must refuse; they must not use a hosted
# compiler or create an artifact under another target name.
if invoke refused-target compile "$fixture" --target wasm32 --output "$output/refused.wasm"; then
  echo "expected unsupported native target refusal" >&2; exit 1
fi
grep -q 'unsupported target' "$output/logs/refused-target.stderr"
[ ! -e "$output/refused.wasm" ]
if invoke refused-policy check "$fixture" "${options[@]}" --unpinned --policy; then
  echo "expected policy refusal" >&2; exit 1
fi
grep -q E2170 "$output/logs/refused-policy.stderr"
shasum -a 256 -c "$output/sources.sha256" > "$output/logs/source-readback.stdout"
[ "$(sha "$compiler")" = "$FIXED_IMAGE_SHA256" ]
[ "$(sha "$loader")" = "$loader_sha" ]
printf '{"status":"pass","scope":"native-runtime-fixture","modules":19,"value_checks":7,"result":127,"fuel_refusal":true,"target_refusal":true,"policy_refusal":true,"compiler_sha256":"%s","image_sha256":"%s","public_cli_migrated":false}\n' \
  "$FIXED_IMAGE_SHA256" "$(sha "$output/runtime.bin")" > "$output/report.json"
cat "$output/report.json"
