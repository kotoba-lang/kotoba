#!/usr/bin/env bash
# kotoba-server local run with IrohBlockStore (IPFS) persistence
# Usage:
#   ./scripts/run-local.sh                                         # start server (self-pin via local Kubo)
#   KOTOBA_IPFS_API=http://localhost:5001 ./scripts/run-local.sh   # explicit Kubo endpoint
#   KOTOBA_PIN_TOKEN=<jwt> ./scripts/run-local.sh                  # + kotobase extended pin (>1GB)

set -euo pipefail

STORE_DIR="${KOTOBA_STORE_DIR:-$HOME/.local/kotoba-gftdcojp}"
mkdir -p "$STORE_DIR"

echo "=== kotoba-server (local) ==="
echo "  KOTOBA_STORE_PATH : ${STORE_DIR}/sled"
echo "  IrohBlockStore    : ${STORE_DIR}/sled-iroh  (IPFS cold tier)"
echo "  MCP endpoint      : http://localhost:8080/mcp"
echo "  XRPC endpoint     : http://localhost:8080/xrpc/..."
echo "  IPFS self-pin     : ${KOTOBA_IPFS_API:-http://localhost:5001} (IpfsPinClient)"
if [[ -n "${KOTOBA_PIN_TOKEN:-}" ]]; then
  echo "  kotobase ext-pin  : enabled (KOTOBA_PIN_TOKEN set, >1GB blobs)"
else
  echo "  kotobase ext-pin  : disabled (set KOTOBA_PIN_TOKEN to enable)"
fi
echo ""

KOTOBA_STORE_PATH="${STORE_DIR}/sled" \
KOTOBA_HOT_CACHE_BYTES="268435456" \
KOTOBA_PORT="8080" \
RUST_LOG="info,kotoba_server=debug" \
  cargo run -p kotoba-server --release
