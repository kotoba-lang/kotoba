#!/bin/sh
set -eu

bundle_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
runtime_dir=$(mktemp -d /tmp/aiueos-installer.XXXXXX)
trap 'rm -rf "$runtime_dir"' EXIT HUP INT TERM

cp "$bundle_dir/node-linux-x64" "$runtime_dir/node"
cp "$bundle_dir"/*.mjs "$runtime_dir/"
chmod 700 "$runtime_dir/node"

exec "$runtime_dir/node" "$runtime_dir/install.mjs" \
  --image "$bundle_dir/aiueos-release-usb.img" \
  --receipt "$bundle_dir/aiueos-release-receipt.json" \
  "$@"
