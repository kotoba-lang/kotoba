#!/bin/sh
# Atomic PXE deploy. The server read_bytes() the artifact at request time, and
# `cp` onto the live path truncates and rewrites in place -- so a transfer that
# overlaps a deploy can read a full-LENGTH file whose head and tail come from
# different builds. Both artifacts are the same size, so nothing downstream can
# see it: the panel showed one build's banner while the kernel came from
# another, and the machine died silently. rename(2) on the same filesystem is
# atomic: a reader gets the old file or the new one, never a seam.
set -eu
src=${1:?usage: k16-deploy.sh <BOOTX64.EFI>}
# The serve directory. /tmp is the historical default and stays the default so
# an unset environment behaves exactly as before -- but a node that is meant to
# come back after a reboot cannot keep its artifact there, so the resident
# LaunchAgent (os/aiueos/deploy/com.gftd.k16-murakumo-node.plist) points both
# this and the server at ~/.gftd/k16.
dir=${AIUEOS_PXE_SERVE_DIR:-/tmp/aiueos-k16-pxe}
tmp="$dir/.BOOTX64.EFI.incoming.$$"
cp "$src" "$tmp"
chmod 600 "$tmp"
mv -f "$tmp" "$dir/BOOTX64.EFI"
shasum -a 256 "$dir/BOOTX64.EFI"
