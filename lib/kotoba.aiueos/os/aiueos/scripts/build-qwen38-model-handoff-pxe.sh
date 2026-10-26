#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-qwen38-model-handoff-pxe"}

AIUEOS_OUT="$out" \
AIUEOS_QWEN38_MODEL_HANDOFF=1 \
AIUEOS_PERSISTENT_BOOT=1 \
  exec "$repo/os/aiueos/scripts/build-physical-qualification-pxe.sh"
