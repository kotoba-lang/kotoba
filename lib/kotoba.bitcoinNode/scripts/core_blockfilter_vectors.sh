#!/usr/bin/env bash
set -euo pipefail

core_tag="v31.1"
expected_sha256="d9049756f744e561b882a8eff507582fb7cd74ed9cf5542bdac58257449ee2a2"
temporary_directory="$(mktemp -d)"
vector_file="${temporary_directory}/blockfilters.json"

cleanup() {
  rm -rf "${temporary_directory}"
}
trap cleanup EXIT

curl --fail --silent --show-error --location \
  "https://raw.githubusercontent.com/bitcoin/bitcoin/${core_tag}/src/test/data/blockfilters.json" \
  --output "${vector_file}"

actual_sha256="$(shasum -a 256 "${vector_file}" | awk '{print $1}')"
if [[ "${actual_sha256}" != "${expected_sha256}" ]]; then
  echo "Bitcoin Core blockfilters.json checksum mismatch." >&2
  exit 1
fi

result="$(kbb -M:core-blockfilter-vectors "${vector_file}")"
expected="{:vectors 10, :passed 10, :failed 0}"
if [[ "${result}" != "${expected}" ]]; then
  echo "Bitcoin Core ${core_tag} block-filter coverage changed: ${result}" >&2
  exit 1
fi

echo "Bitcoin Core ${core_tag} block-filter outcomes conform: ${result}"
