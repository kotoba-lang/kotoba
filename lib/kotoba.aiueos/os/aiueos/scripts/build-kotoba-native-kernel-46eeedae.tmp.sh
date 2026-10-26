#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
compiler=${1:?usage: build-kotoba-native-kernel.sh /path/to/compiler}
expected=49a9efdf97a5f2a18ffb099faa3389532a58628d
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
# 2^26. Was 1048576 = 2^20 -- which was not a chosen budget but exactly the
# `max-native-fuel` the compiler admitted until 2026-09-03; the ceiling is now
# 2^53-1 and the number outlived its reason. At 2^20 the run had to stop after
# four cycles, and the board was ALIVE FOR 12 MILLISECONDS PER 19.7 SECONDS.
# Fuel here is per BOOT and non-replenishable, and its guard is `ud2` with no
# handler -- the board halts and a person presses the power button -- so the
# budget is raised BEFORE the run is lengthened and by more (64x fuel for 16x
# cycles = 4x the per-cycle margin). ADR-0203.
# 2^30 since 2026-09-08. 2^26 replaced 2^20 (which was the compiler's old
# admission ceiling, not a choice); 2^30 is a further precaution, NOT a
# diagnosis -- fuel was briefly and wrongly blamed for a wedge, and ADR-0203
# records the retraction.
#
# Why a large budget is the right direction here and not a lazy one: when this
# guard fires it does not fail a run, it halts the machine with no handler and
# nothing to reset it, so recovery is a person at the power button. Catching a
# runaway SOONER buys nothing, because the outcome is the same halt either way.
# The budget stays large until a dying kernel can say so and leave (ADR-0199
# applied to this kernel); then it can come back down.
native_fuel=${AIUEOS_NATIVE_FUEL:-1073741824}
# The budget is written down in the policy EDN, the --fuel flag, the sealed
# context check, the receipt and the OK line. The policy is the authority --
# --fuel alone is silently not enough -- so generate the policy from the same
# variable everything else reads, instead of keeping five copies in step by
# hand. Default is the shipped 1048576, so an unset environment builds exactly
# what it built before.
fuel_policy="$out/native-kernel-fuel-policy.edn"
mkdir -p "$out"
printf '{:budgets {:fuel %s}}\n' "$native_fuel" >"$fuel_policy"
"$compiler/bin/kotoba-compiler" compile "$source" \
  --source-path "$aiueos" \
  --source-path "$link_frame_source" \
  --source-path "$dma_map_source" \
  --source-path "$mmio_map_source" \
  --source-path "$net_transport_source" \
  --source-path "$org_ietf_tcp_source" --unpinned \
  --policy "$fuel_policy" \
  --target x86_64-aiueos-kernel-v1 --artifact image --fuel "$native_fuel" --output "$kernel"
"$compiler/bin/kotoba-compiler" compile "$source" \
  --source-path "$aiueos" \
  --source-path "$link_frame_source" \
  --source-path "$dma_map_source" \
  --source-path "$mmio_map_source" \
  --source-path "$net_transport_source" \
  --source-path "$org_ietf_tcp_source" --unpinned \
  --policy "$fuel_policy" \
  --target x86_64-aiueos-kernel-v1 --artifact image --fuel "$native_fuel" --output "$second"
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
