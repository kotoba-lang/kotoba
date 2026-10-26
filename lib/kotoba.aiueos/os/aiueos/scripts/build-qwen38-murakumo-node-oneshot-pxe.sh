#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-qwen38-murakumo-node-oneshot-pxe"}

# A real 10.9 GB USB model admission exceeded the generic 90-second recovery
# timer on K16 and returned progress code 210.  Keep recovery bounded, but give
# this exact model enough time to hash, load, execute and post its signed result.
AIUEOS_OUT="$out" \
AIUEOS_PHYSICAL_NETWORK_QUALIFICATION=1 \
AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION=1 \
AIUEOS_MURAKUMO_DEVICE_RESULT=1 \
AIUEOS_QWEN38_MODEL_HANDOFF=1 \
AIUEOS_PERSISTENT_BOOT=0 \
AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS=${AIUEOS_QUALIFICATION_LOADER_WATCHDOG_SECONDS:-1800} \
  exec "$repo/os/aiueos/scripts/build-physical-qualification-pxe.sh"
