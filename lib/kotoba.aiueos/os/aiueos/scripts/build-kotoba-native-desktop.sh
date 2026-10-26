#!/bin/sh
set -eu
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
amu=${1:?usage: AIUEOS_NATIVE_DESKTOP_OUT=/new/output build-kotoba-native-desktop.sh /amu/source}
if [ "${AIUEOS_AMU_BOOTSTRAP:-0}" != 0 ]; then
  echo 'error: hosted bootstrap is retired; use the pinned native compiler' >&2
  exit 1
fi
distribution=${AIUEOS_DISTRIBUTION:-aiueos}
if [ "$(uname -s)" = Darwin ]; then
  set --
  if [ -n "${AIUEOS_AMU_SELFHOST_BIN:-}" ] ||
     [ -n "${AIUEOS_AMU_SELFHOST_SHA256:-}" ] ||
     [ -n "${AIUEOS_KOTOBA_PACKAGER_BIN:-}" ] ||
     [ -n "${AIUEOS_KOTOBA_PACKAGER_SHA256:-}" ]; then
    : "${AIUEOS_AMU_SELFHOST_BIN:?set signed Mac Amu compiler path}"
    : "${AIUEOS_AMU_SELFHOST_SHA256:?set immutable Mac compiler SHA-256}"
    : "${AIUEOS_KOTOBA_PACKAGER_BIN:?set signed Kotoba Mac packager path}"
    : "${AIUEOS_KOTOBA_PACKAGER_SHA256:?set immutable packager SHA-256}"
    set -- --compiler-image "$AIUEOS_AMU_SELFHOST_BIN" \
      --compiler-sha256 "$AIUEOS_AMU_SELFHOST_SHA256" \
      --packager-image "$AIUEOS_KOTOBA_PACKAGER_BIN" \
      --packager-sha256 "$AIUEOS_KOTOBA_PACKAGER_SHA256"
  fi
  : "${AIUEOS_NATIVE_DESKTOP_OUT:?set a new output under github/workspaces}"
  owner_root=${AIUEOS_OWNER_REPO_ROOT:-"$repo/.."}
  qemu=${AIUEOS_QEMU_BIN:-$(command -v qemu-system-x86_64)}
  : "${qemu:?install or select QEMU for the diagnostic boot gate}"
  firmware=${AIUEOS_QEMU_FIRMWARE:-$(python3 -c 'import pathlib,sys; print(pathlib.Path(sys.argv[1]).resolve().parent.parent/"share/qemu/edk2-x86_64-code.fd")' "$qemu")}
  qemu_sha=$(shasum -a 256 "$qemu" | awk '{print $1}')
  firmware_sha=$(shasum -a 256 "$firmware" | awk '{print $1}')
  exec python3 "$repo/os/aiueos/scripts/build-native-desktop-macos.py" \
    --amu-source "$amu" --owner-repo-root "$owner_root" \
    "$@" \
    --qemu "$qemu" --qemu-sha256 "$qemu_sha" \
    --firmware "$firmware" --firmware-sha256 "$firmware_sha" \
    --output "$AIUEOS_NATIVE_DESKTOP_OUT" \
    --profile "${AIUEOS_NATIVE_DESKTOP_PROFILE:-desktop}" \
    --distribution "$distribution"
fi
out=${AIUEOS_NATIVE_DESKTOP_OUT:-"$repo/build/$distribution-native-desktop-$(date -u +%Y%m%dT%H%M%S)"}
exec python3 "$repo/os/aiueos/scripts/build-native-desktop.py" --amu-source "$amu" --output "$out" --profile "${AIUEOS_NATIVE_DESKTOP_PROFILE:-desktop}" --distribution "$distribution"
