#!/usr/bin/env bash
# kotoba-server local run with IrohBlockStore (IPFS) persistence
# Usage:
#   ./scripts/run-local.sh              # start server
#   KOTOBA_PIN_TOKEN=<jwt> ./scripts/run-local.sh  # + kotobase remote pin

set -euo pipefail

STORE_DIR="${KOTOBA_STORE_DIR:-$HOME/.local/kotoba-gftdcojp}"
mkdir -p "$STORE_DIR"

echo "=== kotoba-server (local) ==="
echo "  KOTOBA_STORE_PATH : ${STORE_DIR}/sled"
echo "  IrohBlockStore    : ${STORE_DIR}/sled-iroh  (IPFS cold tier)"
echo "  MCP endpoint      : http://localhost:8080/mcp"
echo "  XRPC endpoint     : http://localhost:8080/xrpc/..."
if [[ -n "${KOTOBA_PIN_TOKEN:-}" ]]; then
  echo "  kotobase pin      : enabled (KOTOBA_PIN_TOKEN set)"
else
  echo "  kotobase pin      : disabled (set KOTOBA_PIN_TOKEN to enable)"
fi
echo ""

KOTOBA_STORE_PATH="${STORE_DIR}/sled" \
KOTOBA_HOT_CACHE_BYTES="268435456" \
KOTOBA_PORT="8080" \
RUST_LOG="info,kotoba_server=debug" \
  cargo run -p kotoba-server --release
