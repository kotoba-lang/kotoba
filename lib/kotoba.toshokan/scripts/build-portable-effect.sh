#!/bin/sh
set -eu

repo_dir=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
compiler_dir=${KOTOBA_COMPILER_DIR:-"$repo_dir/../compiler"}
output_dir="$repo_dir/workerd/generated"

mkdir -p "$output_dir"
cd "$compiler_dir"
kbb -M:run compile \
  "$repo_dir/src/toshokan/portable_effect.kotoba" \
  --target javascript \
  --output "$output_dir/portable-effect.mjs"

kbb -M:run compile \
  "$repo_dir/src/toshokan/ndl_parser.kotoba" \
  --target javascript \
  --output "$output_dir/ndl-parser.mjs"

kbb -M:run compile \
  "$repo_dir/src/toshokan/application.kotoba" \
  --target javascript \
  --output "$output_dir/application.mjs"

kbb -M:run host-profile \
  "$repo_dir/toshokan.host.edn" \
  --output-dir "$output_dir/host"
