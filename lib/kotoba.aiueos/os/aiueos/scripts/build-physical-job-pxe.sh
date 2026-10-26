#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
out=${AIUEOS_OUT:-"$repo/build/aiueos-physical-job-pxe"}

AIUEOS_OUT="$out" \
AIUEOS_PHYSICAL_JOB_QUALIFICATION=1 \
  "$repo/os/aiueos/scripts/build-physical-relay-pxe.sh"
