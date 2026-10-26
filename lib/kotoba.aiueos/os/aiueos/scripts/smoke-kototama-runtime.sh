#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-kototama-runtime.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

${CC:-cc} -std=c11 -O2 \
  -DAIUEOS_QWEN38_MODEL_HANDOFF=1 \
  -o "$work/kototama-runtime" \
  "$repo/os/aiueos/kernel/kototama_runtime.c" \
  "$repo/os/aiueos/scripts/kototama_runtime_model.c"
"$work/kototama-runtime"

printf '%s\n' \
  "AIUEOS_KOTOTAMA_RUNTIME_SMOKE_OK failure=runtime-only restart=workspace-zeroed kernel-reboot=false management=bounded"
