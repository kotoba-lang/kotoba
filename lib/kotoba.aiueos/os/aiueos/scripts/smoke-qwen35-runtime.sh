#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-qwen35-runtime.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

python3 "$aiueos/tests/make_qwen35_header_fixture.py" "$work/header.gguf"

# Two translation units from one source file. The first is the C reference
# parser; the second is ONLY the workspace -> struct translation of the Kotoba
# admission (ADR-0145), which is what lets this gate compare the two structs on
# an aarch64 workstation that cannot execute the x86-64 objects themselves.
${CC:-cc} -std=c11 -O2 -Wall -Wextra -Werror \
  -c -o "$work/qwen35_runtime_reference.o" "$aiueos/kernel/qwen35_runtime.c"
${CC:-cc} -std=c11 -O2 -Wall -Wextra -Werror \
  -DAIUEOS_QWEN35_KOTOBA_ADMISSION -DAIUEOS_QWEN35_TRANSLATION_ONLY \
  -c -o "$work/qwen35_runtime_translation.o" "$aiueos/kernel/qwen35_runtime.c"
${CC:-cc} -std=c11 -O2 -Wall -Wextra -Werror \
  "$aiueos/tests/qwen35_runtime_model.c" \
  "$work/qwen35_runtime_reference.o" "$work/qwen35_runtime_translation.o" \
  -o "$work/qwen35-runtime-model"
"$work/qwen35-runtime-model" "$work/header.gguf" \
  "$aiueos/tests/fixtures/qwen35-kv-plan.bin" \
  "$aiueos/tests/fixtures/qwen35-tensor-plan.bin"
