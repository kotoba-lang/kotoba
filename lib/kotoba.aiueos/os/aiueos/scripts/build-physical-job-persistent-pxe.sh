#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-job-persistent-pxe"}

AIUEOS_OUT="$out" \
AIUEOS_PERSISTENT_BOOT=1 \
  exec "$repo/os/aiueos/scripts/build-physical-job-pxe.sh"
