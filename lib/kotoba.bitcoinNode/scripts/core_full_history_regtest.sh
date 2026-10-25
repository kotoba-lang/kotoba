#!/usr/bin/env bash
set -euo pipefail

for command in bitcoind bitcoin-cli jq clojure; do
  if ! command -v "$command" >/dev/null; then
    echo "$command is required for the full-history regtest." >&2
    exit 77
  fi
done

block_count="${CONSENSUS_REGTEST_BLOCKS:-24}"
restart_interval="${CONSENSUS_RESTART_INTERVAL:-7}"
expected_core_subversion="${CONSENSUS_EXPECTED_CORE_SUBVERSION:-/Satoshi:31.1.0/}"
if (( block_count < 2 || restart_interval < 1 )); then
  echo "Regtest block count and restart interval are invalid." >&2
  exit 2
fi

temporary_root="${TMPDIR:-/tmp}"
workdir="$(mktemp -d "${temporary_root}/bitcoin-node-full-history.XXXXXX")"
case "$workdir" in
  "${temporary_root}"/bitcoin-node-full-history.*) ;;
  *) echo "Unexpected temporary path: $workdir" >&2; exit 2 ;;
esac
core_datadir="$workdir/core"
database="$workdir/kernel.sqlite"
first_evidence="$workdir/first.json"
resume_evidence="$workdir/resume.json"
rejected_evidence="$workdir/rejected.json"
mkdir -p "$core_datadir"

cleanup() {
  bitcoin-cli -regtest -datadir="$core_datadir" stop >/dev/null 2>&1 || true
  rm -rf -- "$workdir"
}
trap cleanup EXIT

bitcoind -regtest -datadir="$core_datadir" -daemonwait -server=1 \
  -fallbackfee=0.0001 >/dev/null
for _ in $(seq 1 30); do
  if bitcoin-cli -regtest -datadir="$core_datadir" \
      getblockchaininfo >/dev/null 2>&1; then
    break
  fi
  sleep 1
done
if ! bitcoin-cli -regtest -datadir="$core_datadir" \
    getblockchaininfo >/dev/null 2>&1; then
  echo "Temporary Bitcoin Core did not become ready." >&2
  exit 1
fi

bitcoin-cli -regtest -datadir="$core_datadir" \
  createwallet differential >/dev/null
address="$(bitcoin-cli -regtest -datadir="$core_datadir" getnewaddress)"
bitcoin-cli -regtest -datadir="$core_datadir" \
  generatetoaddress "$block_count" "$address" >/dev/null

run_differential() {
  local evidence="$1"
  CONSENSUS_HISTORY_NETWORK=regtest \
  CONSENSUS_CORE_DATADIR="$core_datadir" \
  CONSENSUS_DISK_CHAINSTATE="$database" \
  CONSENSUS_HISTORY_END="$block_count" \
  CONSENSUS_RESTART_INTERVAL="$restart_interval" \
  CONSENSUS_EVIDENCE_PATH="$evidence" \
    ./scripts/core_full_history_differential.sh
}

run_differential "$first_evidence"
first_tip="$(jq -r '.target.hash' "$first_evidence")"
first_utxo="$(jq -r '.hash_serialized_3' "$first_evidence")"
jq -e \
  --argjson height "$block_count" --arg core "$expected_core_subversion" \
  '(.schema == "kotoba.bitcoin.full-history-differential.v1") and
   (.network == "regtest") and (.core_version == $core) and
   (.target.height == $height) and
   (.resumed_from_height == 0) and (.verified_blocks == $height) and
   (.sqlite_integrity == "ok") and (.result == "match")' \
  "$first_evidence" >/dev/null

run_differential "$resume_evidence"
jq -e \
  --argjson height "$block_count" --arg tip "$first_tip" \
  --arg utxo "$first_utxo" \
  '(.target.height == $height) and (.target.hash == $tip) and
   (.resumed_from_height == $height) and (.verified_blocks == 0) and
   (.hash_serialized_3 == $utxo) and (.result == "match")' \
  "$resume_evidence" >/dev/null

# Replace the frozen tip with a competing block. A durable kernel resume must
# fail before accepting data or emitting evidence for the new Core branch.
bitcoin-cli -regtest -datadir="$core_datadir" invalidateblock "$first_tip"
replacement_address="$(bitcoin-cli -regtest -datadir="$core_datadir" getnewaddress)"
bitcoin-cli -regtest -datadir="$core_datadir" \
  generatetoaddress 1 "$replacement_address" >/dev/null
replacement_tip="$(bitcoin-cli -regtest -datadir="$core_datadir" \
  getblockhash "$block_count")"
if [[ "$replacement_tip" == "$first_tip" ]]; then
  echo "Core did not create a competing tip for the stale-resume test." >&2
  exit 1
fi
if run_differential "$rejected_evidence" >"$workdir/rejected.out" 2>&1; then
  echo "A stale durable resume tip was unexpectedly accepted." >&2
  exit 1
fi
if ! grep -q "resume tip is not on Core's selected chain" \
    "$workdir/rejected.out"; then
  echo "Stale resume failed without the expected typed boundary." >&2
  cat "$workdir/rejected.out" >&2
  exit 1
fi
if [[ -e "$rejected_evidence" ]]; then
  echo "A failed stale resume emitted success evidence." >&2
  exit 1
fi

echo "Core full-history regtest passed: initial, zero-work resume, stale-tip rejection"
