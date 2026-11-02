#!/usr/bin/env bash
# Build the diagnostic runnable-layout producer from its exact project graph.
# The caller supplies an Amu native compiler, its matching runner source, an
# unused output directory and the compiler's required filesystem capabilities.
set -euo pipefail
if [ "$#" -ne 3 ]; then
  printf 'usage: %s ARM64_AMU RUNNER_SOURCE NEW_OUTPUT_DIR\n' "$0" >&2
  exit 2
fi
compiler=$(realpath "$1")
runner=$(realpath "$2")
parent=$(realpath "$(dirname "$3")")
out="$parent/$(basename "$3")"
mkdir "$out"
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")/../../../.." && pwd -P)
test_root="$repo/lib/kotoba.fune/test"
fune_root="$repo/lib/kotoba.fune/kotoba"
jcs_root="$repo/lib/org.ietf.jcs/kotoba"
sha_root="$repo/lib/gov.nist.sha2/kotoba"
entry="$test_root/fune/runnable_layout_stream_runner.kotoba"
lock="$out/producer.ksl"
files=("$entry")
for name in layout_stream layout_check image_manifest image_config layer_tar \
  snapshot_archive snapshot rootfs_plan rootfs_snapshot_plan rootfs_stream process_rootfs; do
  files+=("$fune_root/fune/$name.kotoba")
done
files+=("$jcs_root/jcs/reader.kotoba" "$sha_root/sha2/core.kotoba")
{
  printf 'KSL1\nentry %s\n' "$entry"
  printf 'root %s\n' "$test_root" "$fune_root" "$jcs_root" "$sha_root"
  for file in "${files[@]}"; do
    printf 'file %s %s\n' "$(sha256sum "$file" | cut -d ' ' -f 1)" "$file"
  done | LC_ALL=C sort -k 3
} > "$lock"
lock_sha=$(sha256sum "$lock" | cut -d ' ' -f 1)
"$compiler" compile "$entry" --target aarch64-macos --output "$out/producer.kseed" \
  --source-path "$test_root" --source-path "$fune_root" --source-path "$jcs_root" --source-path "$sha_root" \
  --source-lock "$lock" --source-lock-sha256 "$lock_sha"
"$compiler" compile "$runner" --target aarch64-linux --output "$out/producer.elf" \
  --format packed --payload "$out/producer.kseed"
chmod 755 "$out/producer.elf"
sha256sum "$compiler" "$runner" "$lock" "$out/producer.kseed" "$out/producer.elf" > "$out/sha256sums.txt"
