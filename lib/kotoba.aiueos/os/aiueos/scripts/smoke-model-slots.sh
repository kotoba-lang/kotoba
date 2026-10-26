#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-model-slots.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

cc=${CC:-clang}
"$cc" -std=c11 -O2 -Wall -Wextra -Werror \
  -I "$repo/os/aiueos/uefi" \
  "$repo/os/aiueos/uefi/model_slots.c" \
  "$repo/os/aiueos/tests/model_slots_model.c" \
  -o "$work/model-slots-model"
"$work/model-slots-model"
