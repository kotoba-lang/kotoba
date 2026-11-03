#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-device-poll-scheduler.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

${CC:-cc} -std=c11 -O2 -Wall -Wextra -Werror \
  -o "$work/device-poll-scheduler" \
  "$repo/os/aiueos/kernel/device_poll_scheduler.c" \
  "$repo/os/aiueos/tests/device_poll_scheduler_test.c"
"$work/device-poll-scheduler"
