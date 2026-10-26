#!/bin/sh
set -eu

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
current=${1:?usage: reproduce-plc-rt-policy-objects.sh CURRENT_AMU PINNED_AMU}
pinned=${2:?usage: reproduce-plc-rt-policy-objects.sh CURRENT_AMU PINNED_AMU}
objcopy=${LLVM_OBJCOPY:-/opt/homebrew/opt/llvm/bin/llvm-objcopy}
[ -x "$objcopy" ] || { echo "error: set LLVM_OBJCOPY" >&2; exit 1; }
[ "$(git -C "$current" rev-parse HEAD)" = 043945d5e13dc94b85ae2797c877bdce628f3f56 ] || {
  echo "error: current Amu revision is not the measured RT policy compiler" >&2; exit 1;
}
[ "$(git -C "$pinned" rev-parse HEAD)" = 9cf3a0ac07a1fb0d735a460230a7e5e9c97bc6a7 ] || {
  echo "error: pinned Amu revision is not the kernel-compatible validator compiler" >&2; exit 1;
}
out=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-plc-rt-policy.XXXXXX")
trap 'rm -rf "$out"' EXIT HUP INT TERM
"$current/bin/kotoba-compiler" compile \
  "$aiueos/kotoba/rt-scheduler-dispatch-plan.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$out/rt-source.o"
"$objcopy" --redefine-sym \
  kotoba_aiueos_scheduler_dispatch_plan=kotoba_aiueos_rt_scheduler_plan \
  "$out/rt-source.o" "$out/rt-linked.o"
cmp "$out/rt-linked.o" "$aiueos/kotoba/rt-scheduler-dispatch-plan.o"
"$pinned/bin/kotoba-compiler" compile \
  "$aiueos/kotoba/plc-user-elf-valid.kotoba" \
  --target x86_64-aiueos-kernel-v1 --output "$out/plc-validator.o"
cmp "$out/plc-validator.o" "$aiueos/kotoba/plc-user-elf-valid.o"
echo "AIUEOS_PLC_RT_POLICY_REPRODUCE_OK scheduler=5ca14a79 validator=77c5e791"
