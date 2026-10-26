#!/usr/bin/env bash
# expose-xrpc.sh — actor-side libp2p mount for the
# /x/etzhayyim/xrpc/<version> protocol. Per ADR-2605241800.
#
# Usage:
#   ./expose-xrpc.sh <local-xrpc-tcp-port> [protocol-version]
#
# Effect: Kubo accepts incoming libp2p streams on the protocol id and
# forwards their bytes to 127.0.0.1:<port>. Any HTTP/XRPC handler bound
# to that port becomes reachable to any libp2p peer that dials this
# node's PeerId.

set -euo pipefail

PORT="${1:?usage: $0 <local-xrpc-tcp-port> [protocol-version]}"
VERSION="${2:-1.0}"
PROTOCOL="/x/etzhayyim/xrpc/${VERSION}"

if ! ipfs config Experimental.Libp2pStreamMounting >/dev/null 2>&1 \
   || [ "$(ipfs config Experimental.Libp2pStreamMounting)" != "true" ]; then
  echo "✘ Experimental.Libp2pStreamMounting is not enabled. Run:" >&2
  echo "    ipfs config --json Experimental.Libp2pStreamMounting true" >&2
  echo "  then restart the Kubo daemon." >&2
  exit 1
fi

# Idempotency: close any existing mount on this protocol first.
ipfs p2p close --protocol "${PROTOCOL}" >/dev/null 2>&1 || true

ipfs p2p listen "${PROTOCOL}" "/ip4/127.0.0.1/tcp/${PORT}" --allow-custom-protocol

echo "✓ Mounted ${PROTOCOL} → /ip4/127.0.0.1/tcp/${PORT}"
echo "  PeerId: $(ipfs id -f '<id>')"
echo "  Active mounts:"
ipfs p2p ls | sed 's/^/    /'
