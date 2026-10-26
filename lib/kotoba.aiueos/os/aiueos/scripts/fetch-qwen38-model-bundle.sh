#!/bin/sh
set -eu

artifact=${AIUEOS_MODEL_ARTIFACT:-Qwen3.8-27B-UD-IQ3_XXS.gguf}
artifact_bytes=${AIUEOS_MODEL_TOTAL_BYTES:-10934860704}
artifact_sha256=${AIUEOS_MODEL_SHA256:-c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee}
revision=${AIUEOS_MODEL_REVISION:-4ca720788d1e01f1bff70c033e0d0028fd02e502}
part0_bytes=${AIUEOS_MODEL_PART0_BYTES:-4000000000}
part1_bytes=${AIUEOS_MODEL_PART1_BYTES:-4000000000}
part2_bytes=${AIUEOS_MODEL_PART2_BYTES:-2934860704}
chunk_bytes=${AIUEOS_MODEL_CHUNK_BYTES:-99614720}
model_url=${AIUEOS_MODEL_URL:-"https://huggingface.co/unsloth/Qwen3.8-27B-GGUF/resolve/$revision/$artifact"}

[ "$#" -eq 1 ] || {
  echo "usage: $0 DESTINATION-VOLUME" >&2
  exit 64
}
destination=$1
[ -d "$destination" ] || {
  echo "error: destination volume is not mounted: $destination" >&2
  exit 1
}
case "$destination" in
  /|/System|/System/*|/Users|/Users/*/System*)
    echo "error: refusing a system destination: $destination" >&2
    exit 64 ;;
esac

if [ "${AIUEOS_MODEL_TEST_FIXTURE:-0}" != 1 ]; then
  [ "$artifact" = Qwen3.8-27B-UD-IQ3_XXS.gguf ] &&
  [ "$artifact_bytes" = 10934860704 ] &&
  [ "$artifact_sha256" = c0b7c3038681ed2e3040456c1dd45f9858b6c2290bed172c70388a94874f3eee ] &&
  [ "$revision" = 4ca720788d1e01f1bff70c033e0d0028fd02e502 ] &&
  [ "$part0_bytes" = 4000000000 ] &&
  [ "$part1_bytes" = 4000000000 ] &&
  [ "$part2_bytes" = 2934860704 ] || {
    echo "error: production model identity is pinned; overrides require AIUEOS_MODEL_TEST_FIXTURE=1" >&2
    exit 1
  }
fi
for value in "$artifact_bytes" "$part0_bytes" "$part1_bytes" "$part2_bytes" "$chunk_bytes"; do
  case "$value" in ''|*[!0-9]*) echo "error: model byte values must be decimal integers" >&2; exit 1 ;; esac
done
[ "$chunk_bytes" -gt 0 ] || { echo "error: chunk size must be positive" >&2; exit 1; }
[ $((part0_bytes + part1_bytes + part2_bytes)) -eq "$artifact_bytes" ] || {
  echo "error: part byte counts do not reconstruct the artifact" >&2
  exit 1
}
case "$artifact_sha256" in
  *[!0-9a-f]*|'') echo "error: model SHA-256 must be lowercase hexadecimal" >&2; exit 1 ;;
esac
[ "${#artifact_sha256}" -eq 64 ] || {
  echo "error: model SHA-256 must contain 64 hexadecimal digits" >&2
  exit 1
}

digest_stream() {
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum | awk '{print $1}'
  else
    shasum -a 256 | awk '{print $1}'
  fi
}

file_bytes() {
  if [ -f "$1" ]; then wc -c < "$1" | tr -d ' '
  else printf '0\n'; fi
}

model_dir="$destination/EFI/AIUEOS"
mkdir -p "$model_dir"
part0="$model_dir/Q38P0.BIN"
part1="$model_dir/Q38P1.BIN"
part2="$model_dir/Q38P2.BIN"

present=0
for pair in "$part0:$part0_bytes" "$part1:$part1_bytes" "$part2:$part2_bytes"; do
  path=${pair%:*}
  expected=${pair##*:}
  if [ -f "$path" ]; then
    actual=$(file_bytes "$path")
    [ "$actual" -eq "$expected" ] || {
      echo "error: existing final part has wrong byte count: $path" >&2
      exit 1
    }
    present=$((present + actual))
  elif [ -f "$path.partial" ]; then
    actual=$(file_bytes "$path.partial")
    [ "$actual" -le "$expected" ] || {
      echo "error: partial part exceeds its pinned byte count: $path.partial" >&2
      exit 1
    }
    present=$((present + actual))
  fi
done

free_kib=$(df -Pk "$destination" | awk 'NR==2 {print $4}')
remaining=$((artifact_bytes - present))
required_kib=$(( (remaining + chunk_bytes + 67108863) / 1024 ))
[ "$free_kib" -ge "$required_kib" ] || {
  echo "error: destination needs remaining model bytes plus one verified chunk and 64 MiB headroom" >&2
  echo "required-kib=$required_kib available-kib=$free_kib destination=$destination" >&2
  exit 1
}

fetch_part() {
  path=$1
  part_start=$2
  expected=$3
  if [ -f "$path" ]; then return 0; fi
  partial="$path.partial"
  chunk="$path.chunk"
  current=$(file_bytes "$partial")
  while [ "$current" -lt "$expected" ]; do
    absolute_from=$((part_start + current))
    remaining_part=$((expected - current))
    request_bytes=$chunk_bytes
    [ "$request_bytes" -le "$remaining_part" ] || request_bytes=$remaining_part
    absolute_to=$((absolute_from + request_bytes - 1))
    if [ -e "$chunk" ]; then unlink "$chunk"; fi

    attempt=1
    downloaded=0
    while [ "$attempt" -le 12 ]; do
      if [ -e "$chunk" ]; then unlink "$chunk"; fi
      http_code=$(curl --http1.1 -fsSL --connect-timeout 30 \
        --range "$absolute_from-$absolute_to" --max-filesize "$request_bytes" \
        --output "$chunk" --write-out '%{http_code}' "$model_url" || true)
      actual=$(file_bytes "$chunk")
      if [ "$http_code" = 206 ] && [ "$actual" -eq "$request_bytes" ]; then
        downloaded=1
        break
      fi
      echo "retry: range=$absolute_from-$absolute_to http=$http_code bytes=$actual attempt=$attempt" >&2
      attempt=$((attempt + 1))
      [ "$attempt" -gt 12 ] || sleep 2
    done
    [ "$downloaded" -eq 1 ] || {
      echo "error: server did not return the exact admitted range $absolute_from-$absolute_to" >&2
      exit 1
    }
    cat "$chunk" >> "$partial"
    unlink "$chunk"
    current=$(file_bytes "$partial")
    [ "$current" -le "$expected" ] || {
      echo "error: appended part exceeds its pinned byte count: $partial" >&2
      exit 1
    }
    printf 'AIUEOS_QWEN38_RANGE_OK file=%s bytes=%s/%s source-range=%s-%s\n' \
      "$(basename "$path")" "$current" "$expected" "$absolute_from" "$absolute_to"
  done
  mv "$partial" "$path"
}

fetch_part "$part0" 0 "$part0_bytes"
fetch_part "$part1" "$part0_bytes" "$part1_bytes"
fetch_part "$part2" $((part0_bytes + part1_bytes)) "$part2_bytes"

[ "$(cat "$part0" "$part1" "$part2" | digest_stream)" = "$artifact_sha256" ] || {
  echo "error: ranged bundle does not reconstruct the pinned artifact SHA-256" >&2
  exit 1
}

python3 - "$model_dir/model-bundle-v1.json" "$model_url" "$artifact_sha256" \
  "$part0" "$part1" "$part2" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

out, source_url, artifact_sha256 = Path(sys.argv[1]), sys.argv[2], sys.argv[3]
parts = []
for name in sys.argv[4:]:
    path = Path(name)
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        while chunk := stream.read(16 * 1024 * 1024):
            digest.update(chunk)
    parts.append({"file": path.name, "bytes": path.stat().st_size,
                  "sha256": digest.hexdigest()})
out.write_text(json.dumps({
    "schema": "aiueos.qwen38-model-bundle.v1",
    "artifact": {"bytes": sum(part["bytes"] for part in parts),
                 "sha256": artifact_sha256},
    "parts": parts,
    "source": {"transport": "https-range", "url": source_url},
    "internal_disk_writes": False,
}, indent=2, sort_keys=True) + "\n", encoding="ascii")
PY

printf 'AIUEOS_QWEN38_BUNDLE_OK destination=%s bytes=%s sha256=%s transport=https-range\n' \
  "$model_dir" "$artifact_bytes" "$artifact_sha256"
