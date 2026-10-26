#!/bin/sh
set -eu

artifact=Qwen3.8-27B-UD-IQ3_XXS.gguf
bytes=10934860704
sha256=c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee
revision=4ca720788d1e01f1bff70c033e0d0028fd02e502
url="https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/$revision/$artifact"
headroom_kib=2097152

[ "$#" -eq 1 ] || {
  echo "usage: $0 DESTINATION-DIRECTORY" >&2
  exit 64
}
destination=$1
case "$destination" in
  /|/System|/System/*) echo "error: refusing system destination" >&2; exit 64 ;;
esac
mkdir -p "$destination"
final="$destination/$artifact"
partial="$destination/$artifact.partial"

digest() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}

if [ -f "$final" ]; then
  [ "$(wc -c < "$final" | tr -d ' ')" = "$bytes" ] &&
  [ "$(digest "$final")" = "$sha256" ] || {
    echo "error: existing artifact does not match the pinned bytes and SHA-256" >&2
    exit 1
  }
  printf 'AIUEOS_QWEN38_ARTIFACT_OK path=%s bytes=%s sha256=%s\n' \
    "$final" "$bytes" "$sha256"
  exit 0
fi

free_kib=$(df -Pk "$destination" | awk 'NR==2 {print $4}')
required_kib=$(( (bytes + 1023) / 1024 + headroom_kib ))
[ "$free_kib" -ge "$required_kib" ] || {
  echo "error: insufficient free space: need artifact plus 2 GiB headroom" >&2
  echo "required-kib=$required_kib available-kib=$free_kib destination=$destination" >&2
  exit 1
}

curl --http1.1 -fL --continue-at - --retry 12 --retry-all-errors \
  --retry-delay 2 -o "$partial" "$url"
[ "$(wc -c < "$partial" | tr -d ' ')" = "$bytes" ] || {
  echo "error: downloaded artifact byte count does not match the pin" >&2
  exit 1
}
[ "$(digest "$partial")" = "$sha256" ] || {
  echo "error: downloaded artifact SHA-256 does not match the pin" >&2
  exit 1
}
mv "$partial" "$final"
printf 'AIUEOS_QWEN38_ARTIFACT_OK path=%s bytes=%s sha256=%s\n' \
  "$final" "$bytes" "$sha256"
