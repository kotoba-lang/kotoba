#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: build-kotoba-native-kernel.sh /path/to/compiler}
expected=5cec919625e4c5069950637ddf989e1acbfb3b0d
actual=$(git -C "$compiler" rev-parse HEAD)
[ "$actual" = "$expected" ] || {
  echo "error: compiler HEAD is $actual; expected $expected" >&2; exit 1;
}
out=${AIUEOS_NATIVE_OUT:-"$repo/build/aiueos-native"}
kernel="$out/KERNEL.ELF"
source=${AIUEOS_NATIVE_KERNEL_SOURCE:-"$aiueos/native/kernel.kotoba"}
second="$out/KERNEL.reproduced.ELF"
receipt="$out/receipt.json"
link_frame_source=${AIUEOS_LINK_FRAME_SOURCE_PATH:-"$repo/../capability-link-frame/kotoba"}
dma_map_source=${AIUEOS_DMA_MAP_SOURCE_PATH:-"$repo/../capability-dma-map/kotoba"}
mmio_map_source=${AIUEOS_MMIO_MAP_SOURCE_PATH:-"$repo/../capability-mmio-map/kotoba"}
net_transport_source=${AIUEOS_NET_TRANSPORT_SOURCE_PATH:-"$repo/../capability-net-transport/kotoba"}
org_ietf_tcp_source=${AIUEOS_ORG_IETF_TCP_SOURCE_PATH:-"$repo/../org-ietf-tcp/kotoba"}
link_frame_commit=8e859f5d1817374a1b1de8447961ac223ffd538c
dma_map_commit=b3590c605a7c189b67a86c28aaae31ec7cdcb8bf
mmio_map_commit=cbbf4ec59f7ca010cec44be2dd84e310faadccee
net_transport_commit=583a9f7c3f517a30a65cf9db3f2dcd19289cbef0
org_ietf_tcp_commit=d8c15e23b6c169a4ed044cd7764923ecbb789be4
require_source_commit() {
  label=$1
  source_root=$2
  expected_commit=$3
  [ -d "$source_root" ] || {
    echo "error: $label source root not found: $source_root" >&2
    exit 1
  }
  source_repo=$(git -C "$source_root" rev-parse --show-toplevel)
  source_commit=$(git -C "$source_repo" rev-parse HEAD)
  [ "$source_commit" = "$expected_commit" ] || {
    echo "error: $label HEAD is $source_commit; expected $expected_commit" >&2
    exit 1
  }
  git -C "$source_repo" diff --quiet HEAD -- "$source_root" || {
    echo "error: $label native source differs from committed $expected_commit" >&2
    exit 1
  }
}
require_source_commit link/frame "$link_frame_source" "$link_frame_commit"
require_source_commit dma/map "$dma_map_source" "$dma_map_commit"
require_source_commit mmio/map "$mmio_map_source" "$mmio_map_commit"
require_source_commit net/transport "$net_transport_source" "$net_transport_commit"
require_source_commit org-ietf-tcp "$org_ietf_tcp_source" "$org_ietf_tcp_commit"
mkdir -p "$out"
"$compiler/bin/kotoba-compiler" compile "$source" \
  --source-path "$aiueos" \
  --source-path "$link_frame_source" \
  --source-path "$dma_map_source" \
  --source-path "$mmio_map_source" \
  --source-path "$net_transport_source" \
  --source-path "$org_ietf_tcp_source" --unpinned \
  --policy "$aiueos/scripts/native-kernel-fuel-policy.edn" \
  --target x86_64-aiueos-kernel-v1 --artifact image --fuel 1048576 --output "$kernel"
"$compiler/bin/kotoba-compiler" compile "$source" \
  --source-path "$aiueos" \
  --source-path "$link_frame_source" \
  --source-path "$dma_map_source" \
  --source-path "$mmio_map_source" \
  --source-path "$net_transport_source" \
  --source-path "$org_ietf_tcp_source" --unpinned \
  --policy "$aiueos/scripts/native-kernel-fuel-policy.edn" \
  --target x86_64-aiueos-kernel-v1 --artifact image --fuel 1048576 --output "$second"
cmp "$kernel" "$second"
rm -f "$second"
python3 "$aiueos/scripts/verify-kotoba-native-kernel.py" \
  "$kernel" "$source" "$expected" "$receipt" \
  "$link_frame_source/capability/link/frame.kotoba" "$link_frame_commit" \
  "$dma_map_source/capability/dma/map.kotoba" "$dma_map_commit" \
  "$mmio_map_source/capability/mmio/map.kotoba" "$mmio_map_commit" \
  "$net_transport_source/capability/net/transport.kotoba" "$net_transport_commit"
foreign=$(find "$out" -type f \( -name '*.c' -o -name '*.o' -o -name '*.obj' -o -name '*.a' -o -name '*.so' \) \
  -print -quit)
[ -z "$foreign" ] || {
  echo "error: foreign/C artifact entered native output: $foreign" >&2; exit 1;
}
