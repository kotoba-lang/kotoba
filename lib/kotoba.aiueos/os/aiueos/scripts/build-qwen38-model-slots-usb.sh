#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-qwen38-model-slots-usb"}

AIUEOS_OUT="$out" \
AIUEOS_MODEL_NVME_SLOTS=1 \
AIUEOS_MODEL_NVME_TARGET_OPTIONAL=1 \
AIUEOS_PHYSICAL_NETWORK_QUALIFICATION=1 \
AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION=1 \
AIUEOS_PERSISTENT_BOOT=1 \
  exec "$repo/os/aiueos/scripts/build-physical-qualification-pxe.sh"
