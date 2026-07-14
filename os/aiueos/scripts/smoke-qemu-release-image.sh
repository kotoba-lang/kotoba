#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos"}

# The release-image smoke uses the same explicitly test-only input event as the
# direct UEFI smoke. Normal release builds leave this compile gate disabled.
AIUEOS_INPUT_SMOKE_SYNTHETIC=1 "$aiueos/scripts/build-release-image.sh" >/dev/null
AIUEOS_DISK_IMAGE="$out/aiueos-x86_64-gpt.img" \
  "$aiueos/scripts/smoke-qemu-uefi.sh"
