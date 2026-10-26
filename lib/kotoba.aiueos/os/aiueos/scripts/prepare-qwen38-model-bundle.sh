#!/bin/sh
set -eu

artifact_bytes=10934860704
artifact_sha256=c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee
part_bytes=4000000000

[ "$#" -eq 2 ] || {
  echo "usage: $0 QWEN3.8-27B-UD-IQ3_XXS.GGUF DESTINATION-VOLUME" >&2
  exit 64
}
source_model=$1
destination=$2
[ -f "$source_model" ] || { echo "error: model artifact not found: $source_model" >&2; exit 1; }
[ -d "$destination" ] || { echo "error: destination volume is not mounted: $destination" >&2; exit 1; }
case "$destination" in
  /|/System|/System/*|/Users|/Users/*/System*)
    echo "error: refusing a system destination: $destination" >&2; exit 64 ;;
esac

digest_file() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "$1" | awk '{print $1}'
  else
    shasum -a 256 "$1" | awk '{print $1}'
  fi
}
digest_stream() {
  if command -v sha256sum >/dev/null 2>&1; then sha256sum | awk '{print $1}'
  else shasum -a 256 | awk '{print $1}'; fi
}

[ "$(wc -c < "$source_model" | tr -d ' ')" = "$artifact_bytes" ] &&
[ "$(digest_file "$source_model")" = "$artifact_sha256" ] || {
  echo "error: source model does not match the pinned artifact" >&2; exit 1;
}

model_dir="$destination/EFI/AIUEOS"
part0="$model_dir/Q38P0.BIN"
part1="$model_dir/Q38P1.BIN"
part2="$model_dir/Q38P2.BIN"
if [ -f "$part0" ] || [ -f "$part1" ] || [ -f "$part2" ]; then
  [ -f "$part0" ] && [ -f "$part1" ] && [ -f "$part2" ] &&
  [ "$(wc -c < "$part0" | tr -d ' ')" = 4000000000 ] &&
  [ "$(wc -c < "$part1" | tr -d ' ')" = 4000000000 ] &&
  [ "$(wc -c < "$part2" | tr -d ' ')" = 2934860704 ] &&
  [ "$(cat "$part0" "$part1" "$part2" | digest_stream)" = "$artifact_sha256" ] || {
    echo "error: existing model bundle is incomplete or has the wrong identity" >&2; exit 1;
  }
  printf 'AIUEOS_QWEN38_BUNDLE_OK destination=%s bytes=%s sha256=%s\n' \
    "$model_dir" "$artifact_bytes" "$artifact_sha256"
  exit 0
fi

free_kib=$(df -Pk "$destination" | awk 'NR==2 {print $4}')
required_kib=$(( (artifact_bytes + 1023) / 1024 + 65536 ))
[ "$free_kib" -ge "$required_kib" ] || {
  echo "error: destination needs the model plus 64 MiB staging headroom" >&2
  echo "required-kib=$required_kib available-kib=$free_kib destination=$destination" >&2
  exit 1
}

mkdir -p "$model_dir"
stage=$(mktemp -d "$destination/.qwen38-stage.XXXXXX")
trap 'rm -rf "$stage"' EXIT HUP INT TERM
split -b "$part_bytes" "$source_model" "$stage/part-"
[ -f "$stage/part-aa" ] && [ -f "$stage/part-ab" ] &&
[ -f "$stage/part-ac" ] && [ ! -e "$stage/part-ad" ] || {
  echo "error: split did not produce the exact three-part bundle" >&2; exit 1;
}
[ "$(wc -c < "$stage/part-aa" | tr -d ' ')" = 4000000000 ] &&
[ "$(wc -c < "$stage/part-ab" | tr -d ' ')" = 4000000000 ] &&
[ "$(wc -c < "$stage/part-ac" | tr -d ' ')" = 2934860704 ] || {
  echo "error: split part lengths do not match the boot ABI" >&2; exit 1;
}
[ "$(cat "$stage/part-aa" "$stage/part-ab" "$stage/part-ac" | digest_stream)" = "$artifact_sha256" ] || {
  echo "error: split bundle no longer reconstructs the pinned artifact" >&2; exit 1;
}
mv "$stage/part-aa" "$part0"
mv "$stage/part-ab" "$part1"
mv "$stage/part-ac" "$part2"
python3 - "$model_dir/model-bundle-v1.json" "$part0" "$part1" "$part2" <<'PY'
import hashlib, json, sys
from pathlib import Path
out = Path(sys.argv[1])
parts = []
for name in sys.argv[2:]:
    path = Path(name)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(16 * 1024 * 1024):
            digest.update(chunk)
    parts.append({"file": path.name, "bytes": path.stat().st_size,
                  "sha256": digest.hexdigest()})
out.write_text(json.dumps({
    "schema": "aiueos.qwen38-model-bundle.v1",
    "artifact": {"bytes": 10934860704,
                 "sha256": "c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee"},
    "parts": parts,
    "internal_disk_writes": False,
}, indent=2, sort_keys=True) + "\n", encoding="ascii")
PY
printf 'AIUEOS_QWEN38_BUNDLE_OK destination=%s bytes=%s sha256=%s\n' \
  "$model_dir" "$artifact_bytes" "$artifact_sha256"
