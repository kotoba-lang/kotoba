#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
output=${1:-"$repo_dir/target/kotoba-b70-probe"}
mkdir -p "$(dirname "$output")"
deno compile --target x86_64-unknown-linux-gnu --allow-all \
  --output "$output" \
  "$repo_dir/verify/b70_webgpu.js" --require-b70
printf '{:ok true :output "%s" :target x86_64-unknown-linux-gnu :runtime-jvm false}\n' "$output"
