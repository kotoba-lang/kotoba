#!/usr/bin/env bash
# Compile the bundled library closures with the pinned self-built compiler.
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
source "$root/scripts/native-toolchain.env"
toolchain=${1:?usage: test-native-libraries.sh TOOLCHAIN NEW_OUTPUT}
output=${2:?missing fresh output directory}
[ ! -e "$output" ] || { echo "output already exists" >&2; exit 73; }
toolchain=$(CDPATH= cd -- "$toolchain" && pwd -P)
mkdir -p -- "$output"
output=$(CDPATH= cd -- "$output" && pwd -P)
compiler=$toolchain/artifacts/G3.bin
loader=$toolchain/host/kexe-loader
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
[ "$(sha "$compiler")" = "$FIXED_IMAGE_SHA256" ] || { echo "compiler pin mismatch" >&2; exit 65; }
loader_sha=$(sha "$loader")
roots=("$root/test/fixtures/library-native")
for library in io json text process edn async; do
  roots+=("$root/lib/kotoba.$library/src")
done
scopes=$output
options=()
for directory in "${roots[@]}"; do
  case "$directory" in *:*|*$'\n'*) echo "invalid source path" >&2; exit 65 ;; esac
  scopes=$scopes:$directory
  options+=(--source-path "$directory")
done
invoke() {
  local label=$1
  shift
  [ "$(sha "$compiler")" = "$FIXED_IMAGE_SHA256" ]
  [ "$(sha "$loader")" = "$loader_sha" ]
  env -i PATH="$PATH" TMPDIR="$current" KEXE_COMMAND=1 \
    KEXE_CAP_RESOURCES_35="$scopes" KEXE_FUEL=500000000 \
    KEXE_PAIRS=16777216 KEXE_VECTORS=4194304 \
    KEXE_VECTOR_ITEMS=134217728 KEXE_STRING_POOL=268435456 \
    KEXE_CPU_SECONDS=120 KEXE_WALL_SECONDS=120 \
    "$loader" "$compiler" 0 0 aarch64 3,35,37,38,39 -- "$@" \
    > "$current/logs/$label.stdout" 2> "$current/logs/$label.stderr"
}
execute() {
  local fuel=$1
  env -i PATH="$PATH" KEXE_STRUCTURED_REPORT=1 KEXE_ARENA_USE=1 \
    KEXE_FUEL="$fuel" KEXE_PAIRS=1048576 KEXE_VECTORS=262144 \
    KEXE_VECTOR_ITEMS=4194304 KEXE_STRING_POOL=16777216 \
    KEXE_CPU_SECONDS=30 KEXE_WALL_SECONDS=30 \
    "$loader" "$image" "$offset" 0 aarch64 -
}
for name in io codecs; do
  case "$name" in io) expected=63; modules=13 ;; codecs) expected=31; modules=13 ;; esac
  current=$output/$name
  mkdir -p "$current/objects" "$current/logs"
  fixture=$root/test/fixtures/library-native/$name.kotoba
  invoke modules modules "$fixture" "${options[@]}" --unpinned
  : > "$current/sources.sha256"
  count=0
  entry=
  while IFS=' ' read -r namespace file; do
    [[ "$namespace" =~ ^[a-zA-Z0-9_.-]+$ ]] || { echo "invalid namespace" >&2; exit 65; }
    case "$file" in "$root/lib/"*|"$root/test/fixtures/library-native/"*) ;; *) echo "source outside reviewed roots" >&2; exit 65 ;; esac
    shasum -a 256 "$file" >> "$current/sources.sha256"
    arguments=(compile "$file" --emit-module --object-dir "$current/objects" \
      --output "$current/objects/$namespace.kso")
    if [ "$file" = "$fixture" ]; then
      entry=$namespace
      arguments+=(--entry)
    fi
    invoke "compile-$count" "${arguments[@]}"
    count=$((count + 1))
  done < "$current/logs/modules.stdout"
  [ "$count" -eq "$modules" ] && [ -n "$entry" ] || { echo "incomplete library closure" >&2; exit 65; }
  invoke link link "$current/objects/$entry.kso" --object-dir "$current/objects" --output "$current/program.kseed"
  invoke extract extract-native "$current/program.kseed" --symbol main --output "$current/program.bin"
  offset=$(sed -n 's/.*:offset \([0-9][0-9]*\).*/\1/p' "$current/logs/extract.stdout")
  [[ "$offset" =~ ^[0-9]+$ ]] || { echo "missing entry offset" >&2; exit 65; }
  image=$current/program.bin
  execute 20000000 > "$current/logs/execute.stdout" 2> "$current/logs/execute.stderr"
  grep -Eq ":status :ok :result $expected([ }]|$)" "$current/logs/execute.stdout"
  if execute 1 > "$current/logs/fuel.stdout" 2> "$current/logs/fuel.stderr"; then
    echo "expected fuel refusal" >&2; exit 1
  fi
  grep -q ':status :trap' "$current/logs/fuel.stdout"
  grep -q ':fuel {:initial 1 :remaining 0}' "$current/logs/fuel.stdout"
  if [ "$name" = codecs ]; then
    for symbol in invalid-capacity invalid-scope; do
      image=$current/$symbol.bin
      invoke "$symbol-extract" extract-native "$current/program.kseed" --symbol "$symbol" --output "$image"
      offset=$(sed -n 's/.*:offset \([0-9][0-9]*\).*/\1/p' "$current/logs/$symbol-extract.stdout")
      [[ "$offset" =~ ^[0-9]+$ ]] || { echo "missing refusal entry" >&2; exit 65; }
      if execute 20000000 > "$current/logs/$symbol.stdout" 2> "$current/logs/$symbol.stderr"; then
        echo "expected $symbol refusal" >&2; exit 1
      fi
      grep -q ':status :trap' "$current/logs/$symbol.stdout"
    done
  fi
  shasum -a 256 -c "$current/sources.sha256" > "$current/logs/source-readback.stdout"
  printf '{"scope":"%s","modules":%s,"result":%s,"fuel_refusal":true,"image_sha256":"%s"}\n' \
    "$name" "$count" "$expected" "$(sha "$current/program.bin")" > "$current/report.json"
  cat "$current/report.json"
done
[ "$(sha "$compiler")" = "$FIXED_IMAGE_SHA256" ]
[ "$(sha "$loader")" = "$loader_sha" ]
