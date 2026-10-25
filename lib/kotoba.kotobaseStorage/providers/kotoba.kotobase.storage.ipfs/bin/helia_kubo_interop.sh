#!/usr/bin/env bash
set -euo pipefail

TEST_REPO="$(mktemp -d /tmp/kotobase-helia-kubo.XXXXXX)"
export IPFS_PATH="$TEST_REPO"
BASE_PORT=$((20000 + $$ % 20000))
KUBO_LOG="$TEST_REPO/kubo.log"
KUBO_PID=""

cleanup() {
  if [[ -n "$KUBO_PID" ]]; then
    kill "$KUBO_PID" 2>/dev/null || true
    wait "$KUBO_PID" 2>/dev/null || true
  fi
  rm -rf "$TEST_REPO"
}
trap cleanup EXIT

ipfs init --profile=test >/dev/null
ipfs config Addresses.API "/ip4/127.0.0.1/tcp/$((BASE_PORT + 1))"
ipfs config Addresses.Gateway "/ip4/127.0.0.1/tcp/$((BASE_PORT + 2))"
ipfs config --json Addresses.Swarm "[\"/ip4/127.0.0.1/tcp/$((BASE_PORT + 3))\"]"
ipfs daemon --offline=false >"$KUBO_LOG" 2>&1 &
KUBO_PID=$!

for _ in $(seq 1 60); do
  if ipfs id >/dev/null 2>&1; then break; fi
  sleep 0.25
done
ipfs id >/dev/null

KUBO_ID="$(ipfs id -f='<id>')"
export KUBO_PEER="/ip4/127.0.0.1/tcp/$((BASE_PORT + 3))/p2p/$KUBO_ID"
KUBO_INPUT="$TEST_REPO/kubo-block.bin"
printf '%s' 'kubo-to-helia-standard-bitswap' >"$KUBO_INPUT"
export KUBO_BLOCK_CID="$(ipfs block put --cid-codec=raw --mhtype=sha2-256 "$KUBO_INPUT")"

kbb --backend sci --classpath "$(kbb -Spath -M:cljs-test)" test/ipfs_helia_kubo_interop.cljk
