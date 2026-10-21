#!/usr/bin/env bash
# Build the pinned Amu seed compiler with itself. This does not build the
# public kotoba launcher, whose native command/target parity is a separate gate.
set -euo pipefail
root=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd -P)
# This repository-owned file is reviewed code, not an external environment file.
source "$root/scripts/native-toolchain.env"
amu_source=
output=
while [ "$#" -gt 0 ]; do
  case "$1" in
    --amu-source|--output)
      [ "$#" -ge 2 ] || { echo "missing value for $1" >&2; exit 64; }
      case "$1" in --amu-source) amu_source=$2 ;; --output) output=$2 ;; esac
      shift 2 ;;
    *) echo "usage: build-selfhost-toolchain.sh --amu-source DIR --output NEW_DIR" >&2; exit 64 ;;
  esac
done
[ -n "$amu_source" ] && [ -n "$output" ] || {
  echo "--amu-source and --output are required" >&2; exit 64;
}
[ "$(uname -s)/$(uname -m)" = Darwin/arm64 ] || {
  echo "the pinned native bootstrap is qualified only for macOS arm64" >&2; exit 69;
}
amu_source=$(CDPATH= cd -- "$amu_source" && pwd -P)
[ "$(git -C "$amu_source" rev-parse HEAD)" = "$AMU_REVISION" ] || {
  echo "Amu source revision differs from native-toolchain.env" >&2; exit 65;
}
# Never repair/reset an input checkout, reuse an old output or weaken a pin.
[ ! -e "$output" ] || { echo "output already exists: $output" >&2; exit 73; }
mkdir -p -- "$output"
output=$(CDPATH= cd -- "$output" && pwd -P)
mkdir "$output/host" "$output/artifacts"
artifacts=$output/artifacts
case "$artifacts" in *:*|*$'\n'*) echo "output path cannot contain colon/newline" >&2; exit 65 ;; esac
loader=$output/host/kexe-loader
unity=$artifacts/seed-unity.kotoba
bootstrap=$amu_source/seed/bootstrap/adopted-20261012.bin
loader_source=$amu_source/seed/bootstrap/adopted-loader-20261012.c
sha() { shasum -a 256 "$1" | awk '{print $1}'; }
verify() {
  [ "$(sha "$1")" = "$2" ] || { echo "digest mismatch: $1" >&2; exit 65; }
}
verify "$amu_source/seed/MANIFEST" "$MANIFEST_SHA256"
verify "$bootstrap" "$BOOTSTRAP_SHA256"
verify "$loader_source" "$LOADER_SOURCE_SHA256"
: > "$unity"
modules=0
while IFS= read -r file || [ -n "$file" ]; do
  case "$file" in ''|'#'*) continue ;; esac
  case "$file" in seed/*.kotoba) ;; *) echo "invalid manifest entry: $file" >&2; exit 65 ;; esac
  case "/$file/" in *'/../'*|*'/./'*) echo "invalid manifest path" >&2; exit 65 ;; esac
  git -C "$amu_source" diff --quiet HEAD -- "$file" || {
    echo "modified Amu source: $file" >&2; exit 65;
  }
  cat "$amu_source/$file" >> "$unity"
  printf '\n' >> "$unity"
  modules=$((modules + 1))
done < "$amu_source/seed/MANIFEST"
[ "$modules" -eq 16 ] || { echo "seed closure must have 16 modules" >&2; exit 65; }
verify "$unity" "$UNITY_SHA256"
clang -std=c11 -O2 "$loader_source" -o "$loader"
verify "$loader_source" "$LOADER_SOURCE_SHA256"
loader_sha=$(sha "$loader")
producer=$bootstrap
producer_sha=$BOOTSTRAP_SHA256
invoke() {
  local name=$1
  shift
  verify "$producer" "$producer_sha"
  verify "$loader" "$loader_sha"
  verify "$unity" "$UNITY_SHA256"
  # No inherited KEXE_* / DYLD_* / runtime overrides. Only compiler I/O inside
  # artifacts is granted. Fuel is off for self-build, with finite arena,
  # output, CPU and wall limits enforced by the trusted C supervisor.
  env -i PATH="$PATH" TMPDIR="$artifacts" \
    KEXE_COMMAND=1 KEXE_CAP_RESOURCES_35="$artifacts" KEXE_FUEL=off \
    KEXE_VECTORS=4194304 KEXE_VECTOR_ITEMS=134217728 \
    KEXE_STRING_POOL=268435456 KEXE_PAIRS=16777216 \
    KEXE_CPU_SECONDS=1800 KEXE_WALL_SECONDS=1800 \
    "$loader" "$producer" 0 0 aarch64 35,37,38,39 -- "$@" \
    > "$output/host/$name.stdout" 2> "$output/host/$name.stderr"
  verify "$producer" "$producer_sha"
  verify "$loader" "$loader_sha"
  verify "$unity" "$UNITY_SHA256"
}
for generation in 1 2 3; do
  invoke "G$generation-compile" compile "$unity" --target aarch64-macos \
    --output "$artifacts/G$generation.kseed"
  invoke "G$generation-extract" extract-native "$artifacts/G$generation.kseed" \
    --symbol main --output "$artifacts/G$generation.bin"
  verify "$artifacts/G$generation.bin" "$FIXED_IMAGE_SHA256"
  producer=$artifacts/G$generation.bin
  producer_sha=$FIXED_IMAGE_SHA256
  printf 'native self-build generation %s verified\n' "$generation"
done
cmp "$artifacts/G2.bin" "$artifacts/G3.bin"
cmp "$artifacts/G2.kseed" "$artifacts/G3.kseed"
printf '{"status":"pass","scope":"amu-seed-self-rebuild","amu_revision":"%s","source_sha256":"%s","compiler_sha256":"%s","loader_sha256":"%s","generations":3,"fixed_point":true,"trusted_c_supervisor":true,"public_cli_migrated":false}\n' \
  "$AMU_REVISION" "$UNITY_SHA256" "$FIXED_IMAGE_SHA256" "$loader_sha" > "$output/report.json"
cat "$output/report.json"
