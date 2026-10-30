#!/bin/sh
set -eu

# The ARP helpers this smoke covers are kotoba/rtl8125-arp.o behind kernel/rtl8125.c's wrappers (JUN-553), an
# x86_64-aiueos-kernel-v1 object a host compiler cannot link on an arm64 machine, so tests/rtl8125_handoff_model.c and the
# differential against the C they replaced run in a QEMU image (needs zig and qemu-system-x86_64).
repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"
work=$(mktemp -d "${TMPDIR:-/tmp}/aiueos-rtl8125.XXXXXX")
trap 'rm -rf "$work"' EXIT HUP INT TERM

sh "$aiueos/scripts/rtl8125-arp-diff/run.sh" "$work"
echo "AIUEOS_RTL8125_MODEL_OK arp=peer-bound-reply driver=kotoba-objects-see-NIC-PARITY-under-qemu"
