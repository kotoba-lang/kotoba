#!/usr/bin/env bash
set -euo pipefail

repo_dir=$(cd "$(dirname "$0")/.." && pwd)
amu_dir=${AMU_DIR:-"$repo_dir/../amu"}
output_dir=${1:-"$repo_dir/target/native-vllm-cli"}
target=${KOTOBA_NATIVE_TARGET:-x86_64}
isa=${KOTOBA_NATIVE_ISA:-x86_64}
cc=${CC:-cc}

mkdir -p "$output_dir"
output_dir=$(cd "$output_dir" && pwd)

compile_report=$(
  cd "$amu_dir"
  ./bin/amu compile ../inference/kotoba/vllm_infer_core.kotoba \
    --target "$target" --output "$output_dir/vllm-infer-core.kexe"
)
printf '%s\n' "$compile_report"

extract_report=$(
  cd "$amu_dir"
  ./bin/amu extract-native "$output_dir/vllm-infer-core.kexe" \
    --symbol max-output-tokens --output "$output_dir/vllm-infer-core.bin"
)
printf '%s\n' "$extract_report"
policy_offset=$(printf '%s\n' "$extract_report" | sed -n 's/.*:offset \([0-9][0-9]*\).*/\1/p')
test -n "$policy_offset"

"$cc" -std=c11 -O2 -Wall -Wextra -Werror \
  "$amu_dir/tools/kexe_loader.c" -o "$output_dir/kotoba-loader"
"$cc" -std=c11 -O2 -Wall -Wextra -Werror \
  -DKOTOBA_POLICY_OFFSET="$policy_offset" \
  -DKOTOBA_POLICY_ISA="\"$isa\"" \
  "$repo_dir/native/kotoba_vllm_cli.c" -o "$output_dir/kotoba-vllm-infer"

printf '{:ok true :output "%s" :target %s :isa %s :policy-offset %s}\n' \
  "$output_dir" "$target" "$isa" "$policy_offset"
