#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
amu=${1:?usage: AIUEOS_AMU_SELFHOST_BIN=/native/amu AIUEOS_AMU_SELFHOST_SHA256=... build-kotoba-native-desktop.sh /amu/source}
if [ "${AIUEOS_AMU_BOOTSTRAP:-0}" != 0 ]; then
  echo 'error: hosted bootstrap is retired; use the pinned native compiler' >&2
  exit 1
fi
distribution=${AIUEOS_DISTRIBUTION:-aiueos}
out=${AIUEOS_NATIVE_DESKTOP_OUT:-"$repo/build/$distribution-native-desktop-$(date -u +%Y%m%dT%H%M%S)"}
exec python3 "$repo/os/aiueos/scripts/build-native-desktop.py" --amu-source "$amu" --output "$out" --distribution "$distribution"
