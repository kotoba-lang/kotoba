#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-rtl8125.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

cc -std=c11 -O2 -Wall -Wextra -Werror \
  -I"$aiueos/kernel" -DAIUEOS_RTL8125_ARP_ONLY \
  "$aiueos/kernel/rtl8125.c" \
  "$aiueos/tests/rtl8125_handoff_model.c" \
  -o "$work/rtl8125-model"
"$work/rtl8125-model"
