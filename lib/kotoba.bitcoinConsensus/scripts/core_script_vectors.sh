#!/usr/bin/env bash
set -euo pipefail

core_tag="v31.1"
script_sha256="bc23cb1dfa760d50042f534da23cbbe4b6fbb03d7def0b64f8de049453d6ead5"
tx_valid_sha256="f8a9e275c581aa24650695bd2b1c718d30f948452934accee83cb32331a9a7a0"
tx_invalid_sha256="0c02ce44ff3a880458f9569a25589315a07f924fcaadac828613d4615776ca52"
sighash_sha256="52cf23c2076e7f129c71d5508631d3e5ae3be1b1cb0585c0e23bbb4bb373e924"

script_file="$(mktemp "${TMPDIR:-/tmp}/bitcoin-core-script-tests.XXXXXX")"
tx_valid_file="$(mktemp "${TMPDIR:-/tmp}/bitcoin-core-tx-valid.XXXXXX")"
tx_invalid_file="$(mktemp "${TMPDIR:-/tmp}/bitcoin-core-tx-invalid.XXXXXX")"
sighash_file="$(mktemp "${TMPDIR:-/tmp}/bitcoin-core-sighash.XXXXXX")"
cleanup() {
  rm -f "$script_file" "$tx_valid_file" "$tx_invalid_file" "$sighash_file"
}
trap cleanup EXIT

download_vector() {
  local name="$1"
  local expected_sha256="$2"
  local destination="$3"
  curl -fsSL \
    "https://raw.githubusercontent.com/bitcoin/bitcoin/${core_tag}/src/test/data/${name}" \
    -o "$destination"
  local actual_sha256
  actual_sha256="$(shasum -a 256 "$destination" | awk '{print $1}')"
  if [[ "$actual_sha256" != "$expected_sha256" ]]; then
    echo "Bitcoin Core ${name} checksum mismatch." >&2
    exit 1
  fi
}

assert_result() {
  local label="$1"
  local actual="$2"
  local expected="$3"
  if [[ "$actual" != "$expected" ]]; then
    echo "Bitcoin Core ${label} coverage changed: ${actual}" >&2
    exit 1
  fi
  echo "Bitcoin Core ${core_tag} ${label} outcomes conform: ${actual}"
}

download_vector "script_tests.json" "$script_sha256" "$script_file"
download_vector "tx_valid.json" "$tx_valid_sha256" "$tx_valid_file"
download_vector "tx_invalid.json" "$tx_invalid_sha256" "$tx_invalid_file"
download_vector "sighash.json" "$sighash_sha256" "$sighash_file"

script_result="$(kbb -M:core-vectors "$script_file")"
assert_result \
  "Script" "$script_result" \
  "{:vectors 1222, :passed 1222, :skipped 0, :failed 0}"

tx_result="$(kbb -M:core-tx-vectors "$tx_valid_file" "$tx_invalid_file")"
assert_result \
  "transaction" "$tx_result" \
  "{:vectors 214, :passed 214, :skipped 0, :failed 0}"

sighash_result="$(kbb -M:core-sighash-vectors "$sighash_file")"
assert_result \
  "legacy sighash" "$sighash_result" \
  "{:vectors 500, :passed 500, :failed 0}"
