#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-dbc-receiver"}
binary="$out/aiueos-dbc-receiver"

command -v clang >/dev/null 2>&1 || { echo "error: Clang is required" >&2; exit 1; }
mkdir -p "$out"
if command -v pkg-config >/dev/null 2>&1 && pkg-config --exists libusb-1.0; then
  # shellcheck disable=SC2046
  clang -std=c11 -O2 -Wall -Wextra -Werror \
    $(pkg-config --cflags libusb-1.0) "$aiueos/tools/dbc-receiver.c" \
    $(pkg-config --libs libusb-1.0) -o "$binary"
elif [ -d /opt/homebrew/opt/libusb/include ] && [ -d /opt/homebrew/opt/libusb/lib ]; then
  clang -std=c11 -O2 -Wall -Wextra -Werror \
    -I/opt/homebrew/opt/libusb/include "$aiueos/tools/dbc-receiver.c" \
    -L/opt/homebrew/opt/libusb/lib -lusb-1.0 -o "$binary"
else
  echo "error: libusb 1.0 is required (brew install libusb)" >&2
  exit 1
fi
"$binary" --selftest >/dev/null
printf '%s\n' "$binary"
