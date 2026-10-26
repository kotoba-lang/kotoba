#!/bin/sh
# Boot the same image under more than one firmware build and boot path, and
# require the evidence to be identical.
#
# WHY THIS IS NOT ADR-0019's A1 (and must not be read as it)
#
# ADR-0019 records that "produces a bootable image" and "boots from a stick on
# someone else's machine" are different claims, and that no physical machine
# has ever booted this image. This script does NOT close that. Every firmware
# it can reach is EDK2 -- the same upstream codebase in two build
# configurations -- so it buys *build* diversity, not the vendor diversity
# (AMI, Insyde, Phoenix) that a real PC ships. Real hardware also brings real
# USB controllers, real ACPI tables from a real board, and real timing, none of
# which appear here.
#
# What it does buy: the image is no longer proven against exactly one firmware
# binary and exactly one boot path.
#
# SECURE BOOT IS NOT ENFORCED HERE, AND A PASS SAYS NOTHING ABOUT IT
#
# The `secure` firmware is a Secure Boot *capable* build. Enforcement needs
# enrolled PK/KEK/db in the variable store, and the store this script hands it
# is the empty template -- which leaves the firmware in setup mode, where it
# will load anything. So a pass here is NOT evidence that a Secure-Boot-enabled
# machine would accept the image.
#
# That question is now ANSWERED, and the answer is no. Measured 2026-08-17 with
# PK/KEK/db enrolled into a copy of this same template (virt-fw-vars
# --enroll-generate ... --secure-boot), booting the same ESP under the same
# `secure` firmware:
#
#   setup mode  BdsDxe: starting Boot0002 ...        71 markers, exit 97
#   enforcing   BdsDxe: failed to load Boot0002 ...: Access Denied
#                                                     0 markers, timed out
#
# Same image, same firmware build, same boot entry; the only difference is the
# variable store. EFI_ACCESS_DENIED is the Secure Boot rejection itself, so
# this names the mechanism rather than inferring it from a failure to boot.
#
# It matters: business PCs ship with Secure Boot on by default, so an unsigned
# image means the customer must turn it off in firmware before the stick will
# boot -- which is the "power it on" promise, contradicted. Signing (shim via
# the Microsoft UEFI CA, or the customer enrolling a key into db) is a
# prerequisite for shipping, not a later refinement.
#
# THE ORDERING ARTIFACT THIS SCRIPT CONTROLS FOR
#
# The journal replay markers (AIUEOS_JOURNAL_RECOVERY_OK,
# AIUEOS_KOTOBA_OBJECT_REPLAY_OK, AIUEOS_OBJECT_TXN_REPLAY_OK,
# AIUEOS_PERSISTENT_SERVICE_BOOTSTRAP_OK) only appear when the block image
# already carries a committed journal, so the FIRST boot after a build emits
# four fewer markers than every later one. Measured 2026-08-15: comparing a
# cold first run against a warm one shows a 4-marker delta that looks exactly
# like a firmware difference and is not one. Every configuration therefore gets
# a warm-up boot that is discarded before the compared run.
#
# Usage: ./os/aiueos/scripts/smoke-qemu-firmware-matrix.sh
#   AIUEOS_FIRMWARE_DIR=<dir>   where to look for edk2-x86_64*-code.fd
set -eu

here=$(cd -- "$(dirname -- "$0")" && pwd)
aiueos=$(cd -- "$here/.." && pwd)
root=$(cd -- "$aiueos/../.." && pwd)
build="$root/build/aiueos"
esp="$build/esp"
blk="$build/virtio-blk-smoke.img"

[ -d "$esp" ] || {
  echo "COULD-NOT-RUN esp-missing: $esp -- run build-uefi.sh first" >&2
  exit 3
}
# --- freshness floor (ADR-0155) ---------------------------------------------
#
# This harness does NOT build. It boots whatever is in `$esp`, and until
# 2026-09-02 the only precondition was that the directory EXISTS. Measured on
# c9f7506: editing `kernel/main.c` so that the string `AIUEOS_PCI_OK
# bounded-scan virtio-vendor=1af4` no longer appears anywhere in the tree, and
# then running this script unchanged, produced
#
#   RUN     default-nonvram exit=97 evidence-lines=98 distinct-markers=85
#   ...
#   AIUEOS_FIRMWARE_MATRIX_OK configurations=3 byte-identical-evidence-lines
#   EXIT=0
#
# -- a full pass, three ways, over a kernel that was not in the tree, still
# printing a marker the tree no longer contains.
#
# The receipt `build-uefi.sh` writes beside the image is what closes it: the
# artifacts must be byte-for-byte the ones that build produced, AND the
# `os/aiueos` subtree must still be the one they were produced from.
command -v python3 >/dev/null 2>&1 || {
  echo "COULD-NOT-RUN python3-missing: the image freshness receipt cannot be checked" >&2
  exit 3
}
freshness_status=0
python3 "$aiueos/scripts/image-freshness.py" assert \
  --receipt "$build/image-receipt.edn" --root "$root" || freshness_status=$?
[ "$freshness_status" = 0 ] || exit "$freshness_status"
# build-uefi.sh does NOT make this one -- smoke-qemu-uefi.sh does, and only
# keeps it with AIUEOS_PRESERVE_BLK_IMAGE=1. Pointing at the wrong script cost
# a measurement: two QEMU runs came back with zero markers and looked like a
# firmware rejection, when both had simply been handed a missing block file.
[ -f "$blk" ] || {
  echo "COULD-NOT-RUN blk-missing: $blk -- run AIUEOS_PRESERVE_BLK_IMAGE=1 smoke-qemu-uefi.sh first" >&2
  exit 3
}

fwdir="${AIUEOS_FIRMWARE_DIR:-}"
if [ -z "$fwdir" ]; then
  for candidate in /opt/homebrew/share/qemu /opt/homebrew/Cellar/qemu/*/share/qemu \
                   /usr/share/OVMF /usr/share/edk2/x64; do
    if [ -f "$candidate/edk2-x86_64-code.fd" ] || [ -f "$candidate/OVMF_CODE.fd" ]; then
      fwdir=$candidate; break
    fi
  done
fi
[ -n "$fwdir" ] || { echo "error: no firmware directory found; set AIUEOS_FIRMWARE_DIR" >&2; exit 2; }

vars_template=""
for v in "$fwdir/edk2-i386-vars.fd" "$fwdir/OVMF_VARS_4M.fd" "$fwdir/OVMF_VARS.fd"; do
  [ -f "$v" ] && { vars_template=$v; break; }
done

work=$(mktemp -d)
trap 'rm -rf "$work"' EXIT

# boot <code.fd> <vars|none> <serial-out>; echoes the qemu exit status
boot() {
  _code=$1; _vars=$2; _out=$3
  _pflash=""
  if [ "$_vars" != "none" ]; then
    cp "$vars_template" "$_vars"
    _pflash="-drive if=pflash,format=raw,file=$_vars"
  fi
  set +e
  qemu-system-x86_64 -machine q35,accel=tcg -cpu max -m 128M -smp 2 \
    -drive if=pflash,format=raw,readonly=on,file="$_code" $_pflash \
    -drive format=raw,file=fat:rw:"$esp" \
    -device isa-debug-exit,iobase=0xf4,iosize=0x04 \
    -device virtio-rng-pci \
    -drive if=none,id=aiueosblk,format=raw,file="$blk" \
    -device virtio-blk-pci,drive=aiueosblk,disable-legacy=on \
    -device virtio-keyboard-pci,disable-legacy=on \
    -device virtio-vga,disable-legacy=on \
    -display none -serial file:"$_out" -monitor none -no-reboot >/dev/null 2>&1
  _rc=$?
  set -e
  echo "$_rc"
}

# Full evidence lines, in order, payloads included -- not a set of marker
# names. ADR-0019's USB gate compares byte-identical evidence for the same
# reason: a run that merely emitted the same marker NAMES could have differed
# in every value they carry (a vector number, an entry count, a digest) and
# still be called a match. Nothing is excluded here yet; if a line ever turns
# out to vary legitimately across configurations, exclude it BY NAME with the
# reason stated, the way ADR-0019 excludes the firmware banner and the AP
# liveness characters -- never by widening the comparison.
markers() { grep -o '^AIUEOS_.*' "$1" 2>/dev/null; }
marker_names() { grep -o '^AIUEOS_[A-Z_0-9]*' "$1" 2>/dev/null | sort -u; }

# Each configuration: label, firmware file, whether it gets a variable store.
# A configuration whose firmware is absent is SKIPPED BY NAME. It is never
# silently dropped: a matrix that quietly shrinks to one row reports the same
# "identical" it would report for a real match.
run_config() {
  _label=$1; _code=$2; _vars_wanted=$3
  if [ ! -f "$_code" ]; then
    echo "SKIP    $_label -- $(basename "$_code") not present"
    return 1
  fi
  if [ "$_vars_wanted" = "vars" ] && [ -z "$vars_template" ]; then
    echo "SKIP    $_label -- no variable-store template found"
    return 1
  fi
  _v=none
  [ "$_vars_wanted" = "vars" ] && _v="$work/$_label.vars.fd"
  # warm-up boot, discarded: see the ordering artifact note above.
  boot "$_code" "$_v" "$work/$_label.warm.log" >/dev/null
  [ "$_v" != none ] && _v="$work/$_label.vars2.fd"
  _rc=$(boot "$_code" "$_v" "$work/$_label.log")
  _n=$(markers "$work/$_label.log" | wc -l | tr -d ' ')
  _u=$(marker_names "$work/$_label.log" | wc -l | tr -d ' ')
  echo "RUN     $_label exit=$_rc evidence-lines=$_n distinct-markers=$_u"
  echo "$_label" >> "$work/ran"
  [ "$_rc" = 97 ] || { echo "FAIL    $_label did not reach the debug-exit success code" >&2; exit 1; }
  return 0
}

echo "firmware dir: $fwdir"
: > "$work/ran"
run_config default-nonvram "$fwdir/edk2-x86_64-code.fd" novars || true
run_config default-nvram   "$fwdir/edk2-x86_64-code.fd" vars || true
run_config secure-nvram    "$fwdir/edk2-x86_64-secure-code.fd" vars || true

ran=$(wc -l < "$work/ran" | tr -d ' ')
if [ "$ran" -lt 2 ]; then
  echo "AIUEOS_FIRMWARE_MATRIX_UNDECIDED configurations=$ran -- fewer than two ran," >&2
  echo "  so nothing was compared. This is not a pass." >&2
  exit 3
fi

first=$(head -1 "$work/ran")
status=0
for label in $(cat "$work/ran"); do
  [ "$label" = "$first" ] && continue
  markers "$work/$first.log" > "$work/a.markers"
  markers "$work/$label.log" > "$work/b.markers"
  if diff -q "$work/a.markers" "$work/b.markers" >/dev/null; then
    echo "MATCH   $first == $label"
  else
    echo "DIFFER  $first vs $label:"
    diff "$work/a.markers" "$work/b.markers" || true
    status=1
  fi
done

if [ "$status" = 0 ]; then
  echo "AIUEOS_FIRMWARE_MATRIX_OK configurations=$ran byte-identical-evidence-lines"
  echo "  NOT vendor firmware diversity: every build here is EDK2."
  echo "  NOT a Secure Boot verdict: the variable store is empty, so the"
  echo "  firmware is in setup mode and enforces nothing."
else
  echo "AIUEOS_FIRMWARE_MATRIX_FAIL evidence differs across configurations" >&2
fi
exit "$status"
