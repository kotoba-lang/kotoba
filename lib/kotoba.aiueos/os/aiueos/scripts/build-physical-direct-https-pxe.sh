#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-direct-https-pxe"}

AIUEOS_OUT="$out" \
AIUEOS_PHYSICAL_NETWORK_QUALIFICATION=1 \
AIUEOS_PHYSICAL_DIRECT_HTTPS_QUALIFICATION=1 \
  "$repo/os/aiueos/scripts/build-physical-qualification-pxe.sh"
