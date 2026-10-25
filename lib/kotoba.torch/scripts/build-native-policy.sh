#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
amu_dir=${AMU_DIR:-"$repo_dir/../amu"}
output_dir=${1:-"$repo_dir/target/native-policy"}
target=${KOTOBA_NATIVE_TARGET:-x86_64}

mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)
cd "$amu_dir"
./bin/amu compile "$repo_dir/kotoba/infer_schedule_core.kotoba" \
  --target "$target" --output "$output_dir/infer-schedule-core.kexe"
./bin/amu extract-native "$output_dir/infer-schedule-core.kexe" \
  --symbol max-running --output "$output_dir/infer-schedule-core.bin" \
  | tee "$output_dir/extract-report.edn"
./bin/amu extract-native "$output_dir/infer-schedule-core.kexe" \
  --symbol mtp-admitted? --output "$output_dir/infer-schedule-mtp-admitted.bin" \
  | tee "$output_dir/extract-mtp-report.edn"
printf '{:ok true :output "%s" :target %s :format :kexe}\n' "$output_dir" "$target"
