#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
state_home=${AIUEOS_STATE_HOME:-"$HOME/.gftd"}
boot=${AIUEOS_PXE_BOOT:-"$repo/build/aiueos-physical-job-pxe/aiueos-k16-native-pxe.efi"}
did_file=${AIUEOS_MURAKUMO_NODE_DID_FILE:-"$state_home/aiueos-k16-node-did"}
token_file=${AIUEOS_MURAKUMO_SERVICE_TOKEN_FILE:-"$state_home/aiueos-k16-murakumo-service-token"}

[ -r "$boot" ] || {
  echo "error: missing K16 PXE image: $boot" >&2
  exit 2
}
[ -r "$did_file" ] || {
  echo "error: missing K16 node DID file: $did_file" >&2
  exit 2
}
[ -r "$token_file" ] || {
  echo "error: missing K16 Murakumo service-token file: $token_file" >&2
  exit 2
}

AIUEOS_PXE_BOOT="$boot" \
AIUEOS_MURAKUMO_NODE_DID_FILE="$did_file" \
AIUEOS_MURAKUMO_SERVICE_TOKEN_FILE="$token_file" \
AIUEOS_MURAKUMO_JOB_QUALIFICATION=1 \
  exec python3 "$repo/os/aiueos/tools/k16-pxe-server.py" "$@"
