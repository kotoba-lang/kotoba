#!/bin/sh
set -eu

# Build the downloadable OS release bundle: one signed release per
# aiueos.distribution.v1 descriptor in AIUEOS_DISTRIBUTIONS_DIR.
#
#   AIUEOS_DISTRIBUTIONS_DIR=/path/kotoba-lang/aiueos/distributions \
#     os/aiueos/scripts/build-os-release-bundle.sh \
#       --out OUT --key release-signing-key.pem \
#       --signing-note "qualification key; QEMU/OVMF evidence only" \
#       --download-base-url https://github.com/kotoba-lang/aiueos/releases/download/<tag>
#
# Writes flat assets <asset-base>-x86_64.{iso,gpt.img},
# <asset-base>-x86_64-build-receipt.{json,sig}, release-catalog.json and
# SHA256SUMS. The asset base is the descriptor's name slug ("AIUEOS" ->
# aiueos, "Itonami OS" -> itonami-os). The descriptor binds identity and
# metadata only: distribution selection does not change kernel/UI bytes, and
# the descriptor grants no authority and qualifies nothing.
#
# The signing key never enters the image builder (sbom.cljk split); this
# script is the caller that signs. Production keys stay offline. Signing uses
# openssl (RSASSA-PKCS1-v1_5 over SHA-256), the same route as
# smoke-qemu-release-image.sh's release-signing proof and the scheme
# verify-release-signature.py checks; sign-release-image.py stays the
# cryptography-based caller for environments that have it.

repo=$(CDPATH= cd -- "$(dirname -- "$0")/../../.." && pwd)
aiueos="$repo/os/aiueos"

out=""
key=""
public_key=""
signing_note=""
download_base=""
while [ $# -gt 0 ]; do
  case "$1" in
    --out) out=$2; shift 2;;
    --key) key=$2; shift 2;;
    --public-key) public_key=$2; shift 2;;
    --signing-note) signing_note=$2; shift 2;;
    --download-base-url) download_base=$2; shift 2;;
    *) echo "unknown argument: $1" >&2; exit 2;;
  esac
done

[ -n "$out" ] || { echo "--out is required" >&2; exit 2; }
[ -n "$key" ] || { echo "--key is required (production keys stay offline)" >&2; exit 2; }
if [ -z "$public_key" ]; then
  public_key="${key%.*}.pub"
fi
[ -f "$public_key" ] || { echo "no such public key: $public_key" >&2; exit 2; }
[ -n "$signing_note" ] || { echo "--signing-note is required" >&2; exit 2; }
[ -n "$download_base" ] || { echo "--download-base-url is required" >&2; exit 2; }
dist_dir=${AIUEOS_DISTRIBUTIONS_DIR:-}
[ -n "$dist_dir" ] || { echo "AIUEOS_DISTRIBUTIONS_DIR is required" >&2; exit 2; }
[ -d "$dist_dir" ] || { echo "no such distributions dir: $dist_dir" >&2; exit 2; }

work="$out/work"
mkdir -p "$out" "$work"

AIUEOS_OUT="$work" "$aiueos/scripts/build-release-image.sh" >/dev/null

efi="$work/esp/EFI/BOOT/BOOTX64.EFI"
kernel="$work/esp/EFI/AIUEOS/KERNEL.ELF"
initramfs="$work/esp/EFI/AIUEOS/INITRD.IMG"
data="$work/aiueos-x86_64-data.img"

kotoba_rev=$(git -C "$repo" rev-parse HEAD 2>/dev/null || echo unversioned)
shell_rev=$(git -C "$dist_dir" rev-parse HEAD 2>/dev/null || echo unversioned)

for descriptor in "$dist_dir"/*/distribution.json; do
  base=$(python3 -c 'import json,re,sys
name = json.load(open(sys.argv[1]))["name"]
print(re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-"))' "$descriptor")
  stem="$base-x86_64"
  python3 "$aiueos/scripts/make-release-image.py" build \
    --efi "$efi" --kernel "$kernel" --initramfs "$initramfs" --data "$data" \
    --output "$out/$stem-gpt.img" --iso "$out/$stem.iso" \
    --receipt "$out/$stem-build-receipt.json" --distribution-json "$descriptor"
  python3 "$aiueos/scripts/make-release-image.py" verify \
    --image "$out/$stem-gpt.img" --iso "$out/$stem.iso" \
    --efi "$efi" --kernel "$kernel" --initramfs "$initramfs"
  openssl dgst -sha256 -sign "$key" \
    -out "$out/$stem-build-receipt.sig" "$out/$stem-build-receipt.json"
  python3 "$aiueos/scripts/verify-release-signature.py" \
    --receipt "$out/$stem-build-receipt.json" \
    --signature "$out/$stem-build-receipt.sig" --public-key "$public_key"
  echo "built $stem from $(basename "$(dirname "$descriptor")")/distribution.json"
done

python3 "$aiueos/scripts/make-release-catalog.py" \
  --release-dir "$out" --distributions-dir "$dist_dir" --public-key "$public_key" \
  --signing-note "$signing_note" --download-base-url "$download_base" \
  --source "kotoba=$kotoba_rev" --source "aiueos=$shell_rev" \
  --out "$out/release-catalog.json"

rm -rf "$work"
echo "AIUEOS_RELEASE_BUNDLE_OK out=$out"
