#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-device-result-v2.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

${CC:-cc} -std=c11 -O2 -Wall -Wextra -Werror \
  -DAIUEOS_DEVICE_RESULT_TESTING=1 \
  -o "$work/device-result-v2" \
  "$repo/os/aiueos/kernel/device_result.c" \
  "$repo/os/aiueos/tests/device_result_v2_model.c"
"$work/device-result-v2"
