#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
model=${AIUEOS_QWEN35_MODEL:-}
[ -n "$model" ] && [ -f "$model" ] || {
  echo "error: AIUEOS_QWEN35_MODEL must name the exact admitted GGUF" >&2
  exit 2
}

expected_bytes=10934860704
expected_sha=c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee
actual_bytes=$(wc -c < "$model" | tr -d ' ')
[ "$actual_bytes" = "$expected_bytes" ] || {
  echo "error: Qwen artifact byte length differs" >&2
  exit 3
}
actual_sha=$(shasum -a 256 "$model" | awk '{print $1}')
[ "$actual_sha" = "$expected_sha" ] || {
  echo "error: Qwen artifact SHA-256 differs" >&2
  exit 4
}

work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-qwen35-first-token.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM
${CC:-cc} -std=c11 -O3 -Wall -Wextra -Werror \
  -DAIUEOS_QWEN35_C_REFERENCE_MATVEC=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_NORM=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_ATTENTION=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_RECURRENT=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_ROPE=1 \
  -I "$aiueos/kernel" \
  "$aiueos/tests/qwen35_first_token_model.c" \
  "$aiueos/kernel/qwen35_runtime.c" \
  "$aiueos/kernel/qwen35_quant.c" \
  "$aiueos/kernel/qwen35_infer.c" \
  -o "$work/qwen35-first-token-model"
"$work/qwen35-first-token-model" "$model"
