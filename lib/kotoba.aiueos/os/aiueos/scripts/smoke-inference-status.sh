#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-inference-status"}
mkdir -p "$out"

cc -std=c11 -O2 -Wall -Wextra -Werror \
  -I"$repo/os/aiueos/kernel" \
  -o "$out/inference-status-screen" \
  "$repo/os/aiueos/tests/inference_status_screen_model.c" \
  "$repo/os/aiueos/kernel/inference_status.c" \
  "$repo/os/aiueos/kernel/framebuffer.c"
"$out/inference-status-screen" "$out/inference-status.ppm"
printf 'AIUEOS_INFERENCE_STATUS_ARTIFACT=%s\n' "$out/inference-status.ppm"
