#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
out=${AIUEOS_OUT:-"$repo/build/aiueos-hw-probe"}
esp="$out/esp/EFI/BOOT"
object="$out/hw-probe.obj"
efi="$esp/BOOTX64.EFI"
image="$out/aiueos-x86_64-gpt.img"
receipt="$out/aiueos-x86_64-build-receipt.json"

command -v zig >/dev/null 2>&1 || { echo "error: Zig is required" >&2; exit 1; }
mkdir -p "$esp"
probe_delay_cflags=
gop_discovery_cflags=
if [ -n "${AIUEOS_HW_PROBE_DELAY_US:-}" ]; then
  case "$AIUEOS_HW_PROBE_DELAY_US" in
    *[!0-9]*|'') echo "error: AIUEOS_HW_PROBE_DELAY_US must be decimal microseconds" >&2; exit 1 ;;
  esac
  probe_delay_cflags="-DAIUEOS_HW_PROBE_DELAY_US=${AIUEOS_HW_PROBE_DELAY_US}ULL"
fi
if [ "${AIUEOS_GOP_FORCE_PROTOCOL_SCAN:-0}" = 1 ]; then
  gop_discovery_cflags="-DAIUEOS_GOP_FORCE_PROTOCOL_SCAN=1"
fi
zig cc -target x86_64-windows-gnu -std=c11 -O2 -ffreestanding -fshort-wchar \
  -fno-stack-protector -mno-red-zone -Wall -Wextra -Werror \
  $probe_delay_cflags $gop_discovery_cflags \
  -c -o "$object" "$aiueos/hw-probe/main.c"
zig lld-link /subsystem:efi_application /entry:efi_main /nodefaultlib /timestamp:0 \
  /fixed:no "/out:$efi" "$object"
SOURCE_DATE_EPOCH=${SOURCE_DATE_EPOCH:-0} python3 "$aiueos/scripts/make-hw-probe-image.py" \
  --efi "$efi" --output "$image" --receipt "$receipt"
printf '%s\n' "$image"
