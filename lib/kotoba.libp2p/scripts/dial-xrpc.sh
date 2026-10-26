#!/usr/bin/env bash
# dial-xrpc.sh — consumer-side libp2p dialer for the
# /x/etzhayyim/xrpc/<version> protocol. Per ADR-2605241800.
#
# Usage:
#   ./dial-xrpc.sh <remote-peer-id> <local-tcp-port> [protocol-version]
#
# Effect: Kubo opens local TCP socket on 127.0.0.1:<port>; every
# incoming TCP connection is multiplexed onto a libp2p stream to
# /p2p/<remote-peer-id> on the protocol id. Any HTTP/XRPC client can
# then point at http://127.0.0.1:<port>/... and traffic flows over
# libp2p to the remote actor.

set -euo pipefail

PEER_ID="${1:?usage: $0 <remote-peer-id> <local-tcp-port> [protocol-version]}"
PORT="${2:?usage: $0 <remote-peer-id> <local-tcp-port> [protocol-version]}"
VERSION="${3:-1.0}"
PROTOCOL="/x/etzhayyim/xrpc/${VERSION}"

if ! ipfs config Experimental.Libp2pStreamMounting >/dev/null 2>&1 \
   || [ "$(ipfs config Experimental.Libp2pStreamMounting)" != "true" ]; then
  echo "✘ Experimental.Libp2pStreamMounting is not enabled. Run:" >&2
  echo "    ipfs config --json Experimental.Libp2pStreamMounting true" >&2
  echo "  then restart the Kubo daemon." >&2
  exit 1
fi

# Try to ensure connectivity (mDNS / DHT / explicit). Non-fatal.
ipfs swarm connect "/p2p/${PEER_ID}" >/dev/null 2>&1 || true

# Idempotency: close any existing mount on this protocol first.
ipfs p2p close --protocol "${PROTOCOL}" >/dev/null 2>&1 || true

ipfs p2p forward "${PROTOCOL}" "/ip4/127.0.0.1/tcp/${PORT}" "/p2p/${PEER_ID}" --allow-custom-protocol

echo "✓ Dialed ${PROTOCOL} via /p2p/${PEER_ID}; local socket 127.0.0.1:${PORT}"
echo "  Test:    curl http://127.0.0.1:${PORT}/..."
echo "  Active mounts:"
ipfs p2p ls | sed 's/^/    /'
