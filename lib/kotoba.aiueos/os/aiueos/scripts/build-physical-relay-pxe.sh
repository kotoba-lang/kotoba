#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-relay-pxe"}

AIUEOS_OUT="$out" \
AIUEOS_PHYSICAL_RELAY_QUALIFICATION=1 \
  "$repo/os/aiueos/scripts/build-physical-network-pxe.sh"
