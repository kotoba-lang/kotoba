#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-qwen35-decode-math.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

${CC:-cc} -std=c11 -O3 -Wall -Wextra -Werror \
  -DAIUEOS_QWEN35_C_REFERENCE_MATVEC=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_NORM=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_ATTENTION=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_RECURRENT=1 \
  -DAIUEOS_QWEN35_C_REFERENCE_ROPE=1 \
  -DAIUEOS_QWEN35_SCALAR=1 -DAIUEOS_QWEN35_TESTING=1 \
  -I "$repo/os/aiueos/kernel" \
  "$repo/os/aiueos/kernel/qwen35_infer.c" \
  "$repo/os/aiueos/tests/qwen35_decode_math_model.c" \
  -lm -o "$work/qwen35-decode-math"
"$work/qwen35-decode-math"
