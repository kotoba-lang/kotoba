#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
output=${1:-"$repo_dir/target/kotoba-infer"}
target=${KOTOBA_NATIVE_DENO_TARGET:-x86_64-unknown-linux-gnu}

cd "$repo_dir"
kbb -M:native-server-build
deno compile --target "$target" --allow-all --output "$output" \
  target/native-server.cjs
printf '{:ok true :output "%s" :target %s :runtime-jvm false}\n' "$output" "$target"
