#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
AIUEOS_PHYSICAL_NETWORK_BUILDER="$repo/os/aiueos/scripts/build-physical-relay-pxe.sh" \
  "$repo/os/aiueos/scripts/smoke-qemu-rtl8125-qualification.sh"
