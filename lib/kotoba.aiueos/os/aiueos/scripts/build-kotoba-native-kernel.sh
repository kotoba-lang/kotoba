#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
exec python3 "$repo/os/aiueos/scripts/build-native-kernel.py" "${1:?usage: build-kotoba-native-kernel.sh /path/to/amu-source}"
