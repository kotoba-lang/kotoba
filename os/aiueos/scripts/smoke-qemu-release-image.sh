#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}

"$aiueos/scripts/build-release-image.sh" >/dev/null
AIUEOS_DISK_IMAGE="$out/aiueos-x86_64-gpt.img" \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
