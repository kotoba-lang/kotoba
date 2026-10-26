#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-qwen38-murakumo-node-pxe"}

AIUEOS_OUT="$out" \
AIUEOS_PHYSICAL_NETWORK_QUALIFICATION=1 \
AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION=1 \
AIUEOS_MURAKUMO_DEVICE_RESULT=1 \
AIUEOS_QWEN38_MODEL_HANDOFF=1 \
AIUEOS_PERSISTENT_BOOT=1 \
  exec "$repo/os/aiueos/scripts/build-physical-qualification-pxe.sh"
